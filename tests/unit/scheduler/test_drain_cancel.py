"""graph 单元级取消（方案 2026-11-02 E2/E3/A0）：跑完当前单元再停。

PlanScheduler.run(stop_requested=...)：信号置位后不再提交新主体单元，在飞
单元跑完（含 n_runs × retry）照常计数，未启动主体记 cancelled，after 括号
照常执行。A0：外层 cancel_event（scope=step）置位时 after 括号仍执行且不在
步骤边界被截断（修复前 after 被单元短路为 halted）。
"""
from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.auth.registry import AuthRegistry
from gimbal.config.models import BootstrapConfig
from gimbal.context.archive import InMemoryArchive
from gimbal.context.manager import ContextManager
from gimbal.core.hooks import HookRegistry
from gimbal.core.runner import Configuration, Engine
from gimbal.core.scenario_runner import RuntimeControl, ScenarioRunResult
from gimbal.events.bus import InMemoryEventBus
from gimbal.plugins import PluginRegistry
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor
from gimbal.protocols.result import CallResult
from gimbal.schema import Call, Config as SC, Meta, Scenario, Step, SuiteGraph, UnitDecl
from gimbal.schema.plan import Plan, PlanPolicy, Unit, UnitPolicy
from gimbal.scheduler.plan import PlanScheduler
from gimbal.strategy.dispatcher import build_default_dispatcher


def _meta(name: str) -> Meta:
    return Meta(name=name, description="d", module="m", priority=1, author="a",
                owner="o", tags=[], version="1",
                createTime=datetime.now(timezone.utc), expire=False,
                requirementRef=[])


def _scenario(sid: str, protocol: str = "echo", n_steps: int = 1) -> Scenario:
    return Scenario(
        scenarioId=sid, meta=_meta(sid), config=SC(), resource={},
        steps=[Step(call=Call(protocol=protocol, message=f"{sid}-{i}"), strategy=[])
               for i in range(n_steps)],
    )


def _ok(unit_id: str) -> ScenarioRunResult:
    now = datetime.now(timezone.utc)
    return ScenarioRunResult(scenario_id=unit_id, status="passed",
                             started_at=now, ended_at=now)


def _plan(n_units: int, *, parallel: int = 1, before: int = 0, after: int = 1,
          n_runs: int = 1) -> Plan:
    return Plan(
        before=[Unit(id=f"b{i}", scenario=_scenario(f"b{i}")) for i in range(before)],
        units=[Unit(id=f"u{i}", scenario=_scenario(f"u{i}"),
                    policy=UnitPolicy(n_runs=n_runs)) for i in range(n_units)],
        after=[Unit(id=f"z{i}", scenario=_scenario(f"z{i}")) for i in range(after)],
        policy=PlanPolicy(parallel=parallel),
    )


class _Recorder:
    """fake run_unit：记录启动顺序；按 unit id 可配置「启动时置位信号」与耗时。"""

    def __init__(self, drain: threading.Event, *, set_on: set[str] = frozenset(),
                 set_when_started: int | None = None, sleep: float = 0.15):
        self.drain = drain
        self.set_on = set(set_on)
        self.set_when_started = set_when_started
        self.sleep = sleep
        self.started: list[str] = []
        self.lock = threading.Lock()

    def __call__(self, unit, inputs, cancel=None):
        with self.lock:
            self.started.append(unit.id)
            n_started = len(self.started)
        if unit.id in self.set_on or n_started == self.set_when_started:
            self.drain.set()
        time.sleep(self.sleep)
        return _ok(unit.id)


class TestSchedulerDrain:
    def test_parallel_inflight_finish_rest_cancelled_after_runs(self) -> None:
        """parallel=2：u0/u1 都已在飞时置位 → 两者跑完有结果；u2/u3 cancelled；after 执行。
        （首批提交前逐单元读信号,所以要等第二个单元启动后再置位,否则 u1 也会被拦）"""
        drain = threading.Event()
        rec = _Recorder(drain, set_when_started=2)
        outcome = PlanScheduler().run(
            _plan(4, parallel=2), rec, stop_requested=drain.is_set)
        assert outcome.results["u0"].status == "passed"
        assert outcome.results["u1"].status == "passed"
        assert outcome.cancelled == {"u2", "u3"}
        assert "z0" in outcome.results and outcome.results["z0"].status == "passed"
        assert set(rec.started) == {"u0", "u1", "z0"}

    def test_serial_first_finishes_rest_cancelled(self) -> None:
        drain = threading.Event()
        rec = _Recorder(drain, set_on={"u0"})
        outcome = PlanScheduler().run(
            _plan(3, parallel=1), rec, stop_requested=drain.is_set)
        assert outcome.results["u0"].status == "passed"
        assert outcome.cancelled == {"u1", "u2"}
        assert outcome.results["z0"].status == "passed"
        assert rec.started == ["u0", "z0"]

    def test_signal_during_before_cancels_all_units(self) -> None:
        drain = threading.Event()
        rec = _Recorder(drain, set_on={"b0"})
        outcome = PlanScheduler().run(
            _plan(2, before=1), rec, stop_requested=drain.is_set)
        assert outcome.results["b0"].status == "passed"
        assert outcome.cancelled == {"u0", "u1"}
        assert outcome.results["z0"].status == "passed"
        assert rec.started == ["b0", "z0"]

    def test_unit_boundary_includes_remaining_n_runs(self) -> None:
        """n_runs=3 的单元第 1 个 run 时置位 → 3 个 run 全部跑完（单元边界 = _run_one）。"""
        drain = threading.Event()
        rec = _Recorder(drain, set_on={"u0"}, sleep=0.01)
        outcome = PlanScheduler().run(
            _plan(2, n_runs=3), rec, stop_requested=drain.is_set)
        assert rec.started.count("u0") == 3
        assert outcome.cancelled == {"u1"}
        assert "z0" in outcome.results

    def test_no_signal_keeps_legacy_behaviour(self) -> None:
        rec = _Recorder(threading.Event(), sleep=0.0)
        outcome = PlanScheduler().run(_plan(3, parallel=2), rec)
        assert not outcome.cancelled and len(outcome.results) == 4


# ── A0：外层 cancel_event 置位，after 括号仍执行 ─────────────────────

@dataclass
class _EchoSpec:
    kind: str = "call:echo"
    message: str = ""
    name: Optional[str] = "echo_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = field(default_factory=list)
    pctx: Optional[ProtocolCallContext] = None


class _CountingEcho(ProtocolExecutor):
    protocol = "echo"

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[str] = []

    def build_spec(self, call, pctx):
        return _EchoSpec(message=getattr(call, "message", ""), pctx=pctx)

    def send(self, spec, view):
        self.sent.append(getattr(spec, "message", ""))
        return CallResult.build(protocol="echo", request={}, status=0, body={"ok": True})


def _engine() -> tuple[Engine, _CountingEcho]:
    bus = InMemoryEventBus()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks, event_bus=bus)
    echo = _CountingEcho()
    dispatcher.protocols.register(echo)
    conf = Configuration(
        cfg=BootstrapConfig(env="test", mode="local", log_level="error"),
        auth_registry=AuthRegistry(),
        ctx_manager=ContextManager(archive=InMemoryArchive(), event_bus=bus),
        dispatcher=dispatcher, event_bus=bus, archive=InMemoryArchive(),
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    return Engine(conf), echo


class TestAfterBracketSurvivesOuterCancel:
    def test_scope_step_cancel_still_runs_after_bracket_fully(self) -> None:
        """外层 cancel_event 已置位（scope=step）：主体单元短路为 halted，after
        单元仍执行且两步都发出（修复前 after 被短路、一步不发）。"""
        engine, echo = _engine()
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="a", scenario=_scenario("a", n_steps=2))],
            after=[UnitDecl(ref="z", scenario=_scenario("z", n_steps=2))],
        )
        cancel = threading.Event()
        cancel.set()
        result = engine.run(graph, runtime_control=RuntimeControl(cancel_event=cancel))
        by_id = {d["scenario_id"]: d for d in result.details}
        assert by_id["a"]["status"] == "halted"
        assert by_id["z"]["status"] == "passed"
        assert echo.sent == ["z-0", "z-1"]

    def test_drain_only_does_not_touch_inflight_scenario(self) -> None:
        """scope=unit（只置位 drain_event）：主体单元照常跑完，不被步骤边界截断。"""
        engine, echo = _engine()
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="a", scenario=_scenario("a", n_steps=2))],
        )
        drain = threading.Event()
        drain.set()   # 在 before 之前即置位 → 主体全部 cancelled、零发送
        result = engine.run(graph, runtime_control=RuntimeControl(drain_event=drain))
        by_id = {d["scenario_id"]: d for d in result.details}
        assert by_id["a"]["status"] == "cancelled"
        assert echo.sent == []


class TestCancelFileWatcher:
    """--cancel-file 轮询器(legacy 链跨进程单元级取消通道):文件出现 → 置
    drain;stop 停线程;drain → PlanScheduler 全链路与 server scope=unit 同义。"""

    def test_file_appears_sets_drain(self, tmp_path) -> None:
        from gimbal.cli.commands.run_launch import _watch_cancel_file
        drain, stop = _watch_cancel_file(str(tmp_path / "cancel-unit"))
        assert not drain.is_set()
        (tmp_path / "cancel-unit").write_text("", encoding="utf-8")
        deadline = time.time() + 2.0          # 0.5s 节拍,2s 足够
        while not drain.is_set() and time.time() < deadline:
            time.sleep(0.05)
        assert drain.is_set()
        stop.set()

    def test_stop_before_file_keeps_drain_unset(self, tmp_path) -> None:
        from gimbal.cli.commands.run_launch import _watch_cancel_file
        signal_file = tmp_path / "cancel-unit"
        drain, stop = _watch_cancel_file(str(signal_file))
        stop.set()
        time.sleep(0.7)                       # 跨过一个轮询节拍
        signal_file.write_text("", encoding="utf-8")
        time.sleep(0.7)
        assert not drain.is_set()             # 已停的轮询器不再消费信号

    def test_full_channel_cancels_rest_after_inflight(self, tmp_path) -> None:
        """u0 启动时编排方写 cancel 文件 → 轮询器置 drain → u0 跑完、u1/u2
        cancelled、after 照常(与 test_serial_first_finishes_rest_cancelled 同
        期望,信号源换成文件)。"""
        from gimbal.cli.commands.run_launch import _watch_cancel_file
        signal_file = tmp_path / "cancel-unit"
        drain, stop = _watch_cancel_file(str(signal_file))

        class _FileRecorder(_Recorder):
            def __call__(self, unit, inputs, cancel=None):
                if unit.id == "u0":
                    signal_file.write_text("", encoding="utf-8")
                    deadline = time.time() + 2.0
                    while not drain.is_set() and time.time() < deadline:
                        time.sleep(0.05)      # 等轮询器消费,确保在 u0 在飞时置位
                return super().__call__(unit, inputs, cancel=cancel)

        try:
            rec = _FileRecorder(drain, sleep=0.05)
            outcome = PlanScheduler().run(
                _plan(3, parallel=1), rec, stop_requested=drain.is_set)
        finally:
            stop.set()
        assert outcome.results["u0"].status == "passed"
        assert outcome.cancelled == {"u1", "u2"}
        assert outcome.results["z0"].status == "passed"
        assert rec.started == ["u0", "z0"]
