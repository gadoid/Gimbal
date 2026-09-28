"""P1-02 事件信封盖标签 + P1-03 日志分类。

验收（Goals P1-02/P1-03）：
  - 总线发布时从 contextvar 取值填入尚未设置的标签字段，发布点显式值优先；
  - `-o jsonl` 输出：step/call 相关事件带 unit/attempt/step/module/service/
    protocol；未设置标签剥除（边界外事件保持旧行形状）；
  - repeat 与 n_runs 产生的事件可以相互区分；
  - 每行 JSON 日志都有 category，step 内的日志带 unit/step。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from gimbal.events.bus import InMemoryEventBus
from gimbal.events.types import CallExchangeEvent, StepStartEvent, StepEndEvent
from gimbal.log.category import categorize_logger, CATEGORIES
from gimbal.log.exec_context import exec_context


class TestBusStampsLabels:

    def test_publish_fills_unset_labels(self):
        bus = InMemoryEventBus()
        got: list = []
        bus.subscribe(got.append)
        with exec_context(run="r1", unit="u1", attempt="1.1", step="step-000",
                          service="fin", protocol="echo"):
            bus.publish(StepStartEvent(step_id="step-000", step_name="s"))
        ev = got[0]
        assert ev.run == "r1" and ev.unit == "u1" and ev.attempt == "1.1"
        assert ev.step == "step-000" and ev.service == "fin" and ev.protocol == "echo"

    def test_publisher_explicit_value_wins(self):
        bus = InMemoryEventBus()
        got: list = []
        bus.subscribe(got.append)
        with exec_context(step="step-001"):
            bus.publish(StepStartEvent(step_id="step-000", step_name="s"))
        # 发布点未给 step 标签显式值 → 盖 contextvar；step_id 是事件自有字段
        assert got[0].step == "step-001"
        assert got[0].step_id == "step-000"

    def test_explicit_label_not_overwritten(self):
        bus = InMemoryEventBus()
        got: list = []
        bus.subscribe(got.append)
        with exec_context(protocol="http"):
            bus.publish(CallExchangeEvent(step_id="s", protocol="echo", status="passed"))
        # CallExchangeEvent.protocol 是发布点必填字段（"echo"），盖章不覆盖
        assert got[0].protocol == "echo"

    def test_outside_boundary_labels_none(self):
        bus = InMemoryEventBus()
        got: list = []
        bus.subscribe(got.append)
        bus.publish(StepEndEvent(step_id="s", status="passed", duration_ms=1.0))
        ev = got[0]
        assert ev.unit is None and ev.scenario is None and ev.step is None


class TestJsonlSinkStripsNoneLabels:

    def test_jsonl_line_shape(self, capsys):
        from gimbal.cli.common import attach_jsonl_sink
        bus = InMemoryEventBus()
        attach_jsonl_sink(bus)
        with exec_context(run="r1", unit="u1", step="step-000", protocol="echo"):
            bus.publish(StepStartEvent(step_id="step-000", step_name="s"))
        bus.publish(StepEndEvent(step_id="s", status="passed", duration_ms=1.0))
        out = capsys.readouterr().out.strip().splitlines()
        assert len(out) == 2
        line1 = json.loads(out[0])
        # 设置了的标签在行内
        assert line1["run"] == "r1" and line1["unit"] == "u1"
        assert line1["step"] == "step-000" and line1["protocol"] == "echo"
        # 未设置的标签剥除（旧行形状不变：没有 "scenario": null 这类噪声）
        assert "scenario" not in line1 and "attempt" not in line1
        line2 = json.loads(out[1])
        for label in ("run", "unit", "step", "scenario", "protocol", "endpoint"):
            assert label not in line2


# ── Engine 级集成（真 echo 协议，验收 P1-02）─────────────────────

@dataclass
class EchoSpec:
    kind: str = "call:echo"
    message: str = ""
    name: Optional[str] = "echo_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = dataclasses.field(default_factory=list)
    pctx: Optional[object] = None


class _EchoExecutor:
    protocol = "echo"

    def build_spec(self, call, pctx):
        spec = EchoSpec(message=str(getattr(call, "message", "")))
        object.__setattr__(spec, "pctx", pctx) if hasattr(spec, "__setattr__") else None
        return spec

    def send(self, spec, view):
        from gimbal.protocols.result import CallResult
        return CallResult.build(protocol=self.protocol,
                                request={"message": spec.message},
                                status=0, body={"echo": spec.message})


def _run_echo_plan(n_runs: int, repeat: int):
    """跑一个 echo graph（repeat 编译期展开为独立单元 + 单元 n_runs），收全部事件。"""
    from gimbal.auth.registry import AuthRegistry
    from gimbal.config.models import BootstrapConfig
    from gimbal.context.archive import InMemoryArchive
    from gimbal.context.manager import ContextManager
    from gimbal.core.bootstrap import Configuration
    from gimbal.core.hooks import HookRegistry
    from gimbal.core.runner import Engine
    from gimbal.plugins import PluginRegistry
    from gimbal.schema.call import Call
    from gimbal.schema.plan import PlanPolicy
    from gimbal.schema.scenario import Config as SC, Meta, Scenario, SuiteGraph, UnitDecl
    from gimbal.schema.step import Step
    from gimbal.strategy.dispatcher import build_default_dispatcher
    from gimbal.protocols.base import ProtocolExecutor

    class Echo(ProtocolExecutor):
        protocol = "echo"

        def build_spec(self, call, pctx):
            return EchoSpec(message=str(getattr(call, "message", "")), pctx=pctx)

        def send(self, spec, view):
            from gimbal.protocols.result import CallResult
            return CallResult.build(protocol=self.protocol,
                                    request={"message": spec.message},
                                    status=0, body={"echo": spec.message})

    def _scenario(sid):
        return Scenario(
            scenarioId=sid,
            meta=Meta(name=sid, description="d", module="echo-mod", priority=1,
                      author="a", owner="o", tags=[], version="1",
                      createTime=datetime.now(timezone.utc), expire=False,
                      requirementRef=[]),
            config=SC(), resource={},
            steps=[Step(call=Call(protocol="echo", message=sid), strategy=[])],
        )

    bus = InMemoryEventBus()
    events: list = []
    bus.subscribe(events.append)
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks, event_bus=bus)
    dispatcher.protocols.register(Echo())
    ctx_manager = ContextManager(archive=InMemoryArchive(), event_bus=bus)
    conf = Configuration(
        cfg=BootstrapConfig(env="test", mode="local", log_level="error"),
        auth_registry=AuthRegistry(), ctx_manager=ctx_manager,
        dispatcher=dispatcher, event_bus=bus, archive=InMemoryArchive(),
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )

    graph = SuiteGraph(
        kind="graph", mode="aggregate",
        units=[UnitDecl(ref="rep", scenario=_scenario("rep"), repeat=repeat,
                        policy_kwargs={"n_runs": n_runs})],
        policy=PlanPolicy(parallel=1),
    )
    Engine(conf).run(graph)
    return events


class TestEngineEventLabels:

    def test_step_and_call_events_carry_full_labels(self):
        events = _run_echo_plan(n_runs=1, repeat=1)
        starts = [e for e in events if e.event_type == "step.start"]
        exchanges = [e for e in events if e.event_type == "call.exchange"]
        assert len(starts) == 1 and len(exchanges) == 1
        # step 级事件：六标签（protocol/endpoint 属调用边界，step.start 时尚未进入）
        for ev in starts:
            assert ev.run and ev.unit == "rep"  # repeat=1 时无 #k 后缀
            assert ev.attempt == "1.1"
            assert ev.scenario == "rep"
            assert ev.step == "step-000"
            assert ev.module == "echo-mod"
            assert ev.protocol is None and ev.service is None
        # call 级事件：protocol 标签 + 事件自有 protocol 字段
        for ev in exchanges:
            assert ev.run and ev.unit == "rep" and ev.attempt == "1.1"
            assert ev.scenario == "rep" and ev.step == "step-000"
            assert ev.module == "echo-mod"
            assert ev.protocol == "echo"
            assert ev.service is None  # echo 协议无 service 字段 → 不设

    def test_repeat_and_n_runs_distinguishable(self):
        """repeat 2 × n_runs 2：unit 标签区分 repeat 变体，attempt 区分 n_runs。"""
        events = _run_echo_plan(n_runs=2, repeat=2)
        exchanges = [e for e in events if e.event_type == "call.exchange"]
        assert len(exchanges) == 4
        got = {(e.unit, e.attempt) for e in exchanges}
        assert got == {("rep#1", "1.1"), ("rep#1", "2.1"),
                       ("rep#2", "1.1"), ("rep#2", "2.1")}


class TestLogCategory:

    def test_mapping_table(self):
        assert categorize_logger("gimbal.strategy.builtin.call") == "call"
        assert categorize_logger("gimbal.protocols.base") == "call"
        assert categorize_logger("gimbal.auth.registry") == "auth"
        assert categorize_logger("gimbal.strategy.dispatcher") == "strategy"
        assert categorize_logger("gimbal.compiler.pipeline") == "compiler"
        assert categorize_logger("gimbal.scheduler.plan") == "scheduler"
        assert categorize_logger("gimbal.plugins.loader") == "plugin"
        assert categorize_logger("gimbal.core.debugger") == "debug"
        assert categorize_logger("gimbal.core.runner") == "core"
        assert categorize_logger("gimbal.statemachine.engine") == "core"
        assert categorize_logger(None) == "core"
        assert set(CATEGORIES) == {"call", "auth", "strategy", "compiler",
                                   "scheduler", "plugin", "debug", "core"}

    def test_json_sink_carries_category_and_labels(self):
        from gimbal.log.formatters import JsonSink
        sink = JsonSink()

        def _record(logger_name, message="m"):
            return {
                "time": datetime.now(timezone.utc),
                "level": type("L", (), {"name": "INFO"})(),
                "name": logger_name,
                "function": "f", "line": 1, "message": message,
                "extra": {"name": logger_name}, "exception": None,
            }

        with exec_context(run="r1", unit="u1", step="step-000"):
            line1 = json.loads(sink._serialize(_record("gimbal.scheduler.plan")))
        line2 = json.loads(sink._serialize(_record("gimbal.core.runner")))
        assert line1["category"] == "scheduler"
        assert line1["run"] == "r1" and line1["unit"] == "u1"
        assert line1["step"] == "step-000"
        assert line2["category"] == "core"
        assert "run" not in line2 and "step" not in line2
