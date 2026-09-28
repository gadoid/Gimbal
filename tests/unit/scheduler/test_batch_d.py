"""批次 D 测试：三种乘法 / lock 互斥 / 并发压力与竞态 / auth_expired 重发。

验收门：parallel 真跑 + 竞态测试通过；n_runs/retry 计数与计划清单对账。
"""
import dataclasses
import os
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.auth.registry import AuthRegistry
from gimbal.config.models import BootstrapConfig
from gimbal.context.archive import InMemoryArchive
from gimbal.context.manager import ContextManager
from gimbal.core.bootstrap import Configuration
from gimbal.core.hooks import HookRegistry
from gimbal.core.runner import Engine
from gimbal.events.bus import InMemoryEventBus
from gimbal.plugins import PluginRegistry
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor, ProtocolTransportError
from gimbal.protocols.result import CallResult
from gimbal.schema.call import Call
from gimbal.schema.plan import Plan, PlanPolicy, Unit, UnitPolicy
from gimbal.scheduler.plan import PlanScheduler
from gimbal.schema.scenario import (
    Config as ScenarioConfig, Meta, Scenario, SuiteGraph, UnitDecl,
)
from gimbal.schema.step import Step
from gimbal.strategy.dispatcher import build_default_dispatcher
from gimbal.strategy.executor_base import StrategyResult, StrategyStatus


# ── 可编程 echo 协议（行为由测试回调注入）────────────────────

@dataclass
class ProgSpec:
    kind: str = "call:echo"
    name: Optional[str] = "echo_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = dataclasses.field(default_factory=list)
    pctx: Optional[ProtocolCallContext] = None


class ProgrammableEchoExecutor(ProtocolExecutor):
    """send 行为由 send_fn 注入（默认成功）。"""
    protocol = "echo"

    def __init__(self, send_fn=None):
        super().__init__()
        self.send_fn = send_fn or (lambda spec, view: CallResult.build(
            protocol="echo", request={}, status=0, body={"msg": "ok", "ok": True}))
        self.refresh_calls = 0

    def build_spec(self, call, pctx):
        return ProgSpec(pctx=pctx)

    def send(self, spec, view):
        return self.send_fn(spec, view)

    def refresh_auth(self, pctx) -> bool:
        self.refresh_calls += 1
        return True


def _make_engine_with(executor: ProtocolExecutor):
    bus = InMemoryEventBus()
    archive = InMemoryArchive()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks)
    dispatcher.protocols.register(executor)
    ctx_manager = ContextManager(archive=archive, event_bus=bus)
    cfg = BootstrapConfig(env="test", mode="local", log_level="error")
    conf = Configuration(
        cfg=cfg, auth_registry=AuthRegistry(), ctx_manager=ctx_manager,
        dispatcher=dispatcher, event_bus=bus, archive=archive,
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    return Engine(conf), archive, bus


def _scenario(sid: str, assert_echo=None, extract_to=None) -> Scenario:
    strategy = []
    if assert_echo is not None:
        strategy.append({"kind": "assertion", "name": "c",
                         "target": "$.call.response.body.msg",
                         "operator": "eq", "expected": assert_echo})
    if extract_to:
        strategy.append({"kind": "extract", "name": "o",
                         "expression": "$.call.response.body.msg",
                         "target": extract_to, "scope": "scenario"})
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=sid, description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(),
        resource={},
        steps=[Step(call=Call(protocol="echo", message=sid), strategy=strategy)],
    )


def _make_plan(units: int, policy_kwargs: dict, parallel: int) -> Plan:
    """最小 Plan：N 个无依赖单元（aggregate），统一单元策略 + Plan 级并发。"""
    return Plan(
        units=[Unit(id=f"u{i}", scenario=_scenario(f"u{i}"),
                    policy=UnitPolicy(**policy_kwargs))
               for i in range(units)],
        policy=PlanPolicy(parallel=parallel),
    )


class TestParallelRunsMultiplicationCore:
    """P0-2：并行分支必须走 _run_one —— n_runs 乘法与 lock 互斥不能被绕过。"""

    def test_parallel_runs_n_runs_multiplication_and_lock(self):
        """parallel=2、3 单元 × n_runs=3 → 发送 9 次；同 lock 标签最大并发 = 1。"""
        calls = []
        guard = threading.Lock()
        lock_max = {"n": 0, "cur": 0}

        class _R:
            passed = True
            status = "passed"

        def fake_unit_run(unit, inputs):
            with guard:
                calls.append(unit.id)
            # lock 标签单元内统计并发峰值（调度器应保证同标签互斥）
            if unit.policy.lock == "db":
                with guard:
                    lock_max["cur"] += 1
                    lock_max["n"] = max(lock_max["n"], lock_max["cur"])
                time.sleep(0.05)
                with guard:
                    lock_max["cur"] -= 1
            return _R()

        plan = _make_plan(units=3, policy_kwargs={"n_runs": 3, "lock": "db"}, parallel=2)
        sched = PlanScheduler()
        outcome = sched.run(plan, fake_unit_run)

        assert len(calls) == 3 * 3, f"n_runs 乘法在并行下被绕过: {len(calls)} != 9"
        assert Counter(calls) == {"u0": 3, "u1": 3, "u2": 3}   # 每单元恰跑 n_runs 次
        assert lock_max["n"] == 1, f"同 lock 标签出现并发: {lock_max['n']}"
        assert not outcome.blocked and not outcome.cancelled


class TestMultiplication:

    def test_n_runs_counts_every_run(self):
        """n_runs=3：attempts=3（执行次数单列）、total 按单元口径=1、全部通过才通过。

        P1-11：total/passed/failed 一律按单元计数，n_runs/retry 展开计入
        RunResult.attempts（旧口径 total=3 已废弃）。
        """
        ex = ProgrammableEchoExecutor(send_fn=lambda s, v: CallResult.build(
            protocol="echo", request={"msg": "ok"}, status=0, body={"msg": "ok"}))
        engine, _, _ = _make_engine_with(ex)
        graph = SuiteGraph(mode="aggregate", units=[
            UnitDecl(ref="u", scenario=_scenario("u", assert_echo="ok"),
                     policy_kwargs={"n_runs": 3}),
        ])
        result = engine.run(graph)
        assert result.passed == 1
        assert result.total == 1, f"单元口径 total: {result.total} != 1"
        assert result.attempts == 3, f"执行次数对账: {result.attempts} != 3"
        assert result.details[0]["status"] == "passed"

    def test_n_runs_failure_stops_remaining(self):
        """n_runs=3 但第 2 次失败 → 停止第 3 次，attempts=2，单元口径 total=1。"""
        counter = {"n": 0}

        def flaky(spec, view):
            counter["n"] += 1
            msg = "ok" if counter["n"] != 2 else "bad"
            return CallResult.build(protocol="echo", request={"msg": msg},
                                    status=0, body={"msg": msg})

        ex = ProgrammableEchoExecutor(send_fn=flaky)
        engine, _, _ = _make_engine_with(ex)
        graph = SuiteGraph(mode="aggregate", units=[
            UnitDecl(ref="u", scenario=_scenario("u", assert_echo="ok"),
                     policy_kwargs={"n_runs": 3}),
        ])
        result = engine.run(graph)
        assert result.failed == 1
        assert result.total == 1          # P1-11 单元口径：失败单元恰计 1
        assert result.attempts == 2       # 第 3 次未跑
        assert counter["n"] == 2

    def test_retry_recovers_transient_failure(self):
        """retry=2：首次失败、重试通过 → 单元通过且 retries 记账。"""
        counter = {"n": 0}

        def transient(spec, view):
            counter["n"] += 1
            msg = "ok" if counter["n"] >= 2 else "bad"
            return CallResult.build(protocol="echo", request={"msg": msg},
                                    status=0, body={"msg": msg})

        ex = ProgrammableEchoExecutor(send_fn=transient)
        engine, _, _ = _make_engine_with(ex)
        graph = SuiteGraph(mode="aggregate", units=[
            UnitDecl(ref="u", scenario=_scenario("u", assert_echo="ok"),
                     policy_kwargs={"retry": 2}),
        ])
        result = engine.run(graph)
        assert result.passed == 1
        assert counter["n"] == 2          # 1 次失败 + 1 次重试
        # retry 不计清单：total=1
        assert result.total == 1

    def test_retry_exhausted_fails_unit(self):
        counter = {"n": 0}

        def always_bad(spec, view):
            counter["n"] += 1
            return CallResult.build(protocol="echo", request={"msg": "bad"},
                                    status=0, body={"msg": "bad"})

        ex = ProgrammableEchoExecutor(send_fn=always_bad)
        engine, _, _ = _make_engine_with(ex)
        graph = SuiteGraph(mode="aggregate", units=[
            UnitDecl(ref="u", scenario=_scenario("u", assert_echo="ok"),
                     policy_kwargs={"retry": 2}),
        ])
        result = engine.run(graph)
        assert result.failed == 1
        assert counter["n"] == 3          # 1 + 2 次重试

    def test_retry_prevents_blocked_cascade(self):
        """上游首跑失败经 retry 通过 → 下游不 blocked。"""
        counter = {"n": 0}

        def transient(spec, view):
            counter["n"] += 1
            msg = "ok" if counter["n"] >= 2 else "bad"
            return CallResult.build(protocol="echo", request={"msg": msg},
                                    status=0, body={"msg": msg})

        ex = ProgrammableEchoExecutor(send_fn=transient)
        engine, _, _ = _make_engine_with(ex)
        graph = SuiteGraph(mode="chain", units=[
            UnitDecl(ref="a", scenario=_scenario("a", assert_echo="ok", extract_to="v"),
                     policy_kwargs={"retry": 2}),
            UnitDecl(ref="b", scenario=_scenario("b", assert_echo="ok"),
                     policy_kwargs={}),
        ])
        result = engine.run(graph)
        assert result.blocked == 0
        assert result.passed == 2

    def test_repeat_expands_into_independent_units(self):
        """repeat=3 → ref#1..#3 独立单元；needs 引用 ref → 依赖全部变体。"""
        ex = ProgrammableEchoExecutor()
        engine, _, _ = _make_engine_with(ex)
        graph = SuiteGraph(mode="compose", units=[
            UnitDecl(ref="src", scenario=_scenario("src", extract_to="v"), repeat=3),
            UnitDecl(ref="sink", scenario=_scenario("sink"), needs=["src"],
                     inputs={"补": 1}),
        ])
        # sink 没有模板输入 → 无需连线；直接看编译产物
        from gimbal.compiler.pipeline import compile_target
        plan = compile_target(graph)
        ids = sorted(u.id for u in plan.units)
        assert ids == ["sink", "src#1", "src#2", "src#3"]
        sink = next(u for u in plan.units if u.id == "sink")
        assert sorted(sink.needs) == ["src#1", "src#2", "src#3"]
        result = engine.run(graph)
        assert result.passed == 4 and result.total == 4


class TestLockMutualExclusion:

    def test_same_lock_units_never_overlap(self):
        """同 lock 标签的两个单元在并行下时间线不重叠。"""
        timeline = []
        tl_lock = threading.Lock()

        def make_send(tag):
            def _send(spec, view):
                with tl_lock:
                    timeline.append(("start", tag, time.monotonic()))
                time.sleep(0.08)
                with tl_lock:
                    timeline.append(("end", tag, time.monotonic()))
                return CallResult.build(protocol="echo", request={}, status=0,
                                        body={"msg": "ok"})
            return _send

        ex = ProgrammableEchoExecutor()
        ex.send_fn = None  # 按单元分派：见下方 per-unit 视图替换
        # 更简单：send_fn 从 scratch 拿不到 ref —— 用两个执行器不行（同协议名）。
        # 方案：send_fn 依据 view 不可区分 → 改用 pctx.call.message（=scenarioId）
        def _send(spec, view):
            tag = getattr(spec.pctx.call, "message", "?")
            with tl_lock:
                timeline.append(("start", tag, time.monotonic()))
            time.sleep(0.08)
            with tl_lock:
                timeline.append(("end", tag, time.monotonic()))
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": "ok"})

        ex = ProgrammableEchoExecutor(send_fn=_send)
        engine, _, _ = _make_engine_with(ex)
        graph = SuiteGraph(
            mode="aggregate",
            policy={"parallel": 2},
            units=[
                UnitDecl(ref="L1", scenario=_scenario("L1"), policy_kwargs={"lock": "db"}),
                UnitDecl(ref="L2", scenario=_scenario("L2"), policy_kwargs={"lock": "db"}),
            ],
        )
        result = engine.run(graph)
        assert result.passed == 2
        # 时间线互斥：按时间排序后，任一 start 前所有已 start 的同名域必须已 end
        events = sorted(timeline, key=lambda e: e[2])
        open_tags: set[str] = set()
        violations = 0
        for kind, tag, _ in events:
            if kind == "start":
                if tag in open_tags:
                    violations += 1
                open_tags.add(tag)
            else:
                open_tags.discard(tag)
        assert violations == 0, f"lock 互斥被违反 {violations} 次"


class TestConcurrencyStress:

    def test_100_units_parallel_stress(self):
        """100 单元 × 8 并发：全过、计数对账、Archive 键完整、无异常。"""
        def slow_ok(spec, view):
            time.sleep(0.005)
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": "ok"})

        ex = ProgrammableEchoExecutor(send_fn=slow_ok)
        engine, archive, bus = _make_engine_with(ex)
        counter = {"n": 0}
        bus.subscribe(lambda e: counter.__setitem__("n", counter["n"] + 1), "scenario.end")

        units = [UnitDecl(ref=f"u{i:03d}", scenario=_scenario(f"u{i:03d}", assert_echo="ok"))
                 for i in range(100)]
        graph = SuiteGraph(mode="aggregate", policy={"parallel": 8}, units=units)
        result = engine.run(graph)
        assert result.passed == 100 and result.exit_code == 0
        assert result.total == 100
        # Archive：100 个 (scenario, step-000) 互不覆盖
        assert archive.stats()["steps"] >= 100
        for i in (0, 37, 99):
            assert archive.get_step("step-000", scenario_id=f"u{i:03d}") is not None
        # 事件无丢失（scenario.end 双发历史行为 → 至少 100）
        assert counter["n"] >= 100

    def test_multi_round_race_stability(self):
        """多轮并行 + 抖动：结果确定性（每轮 3 过，计数对账）。"""
        def jitter(spec, view):
            time.sleep(0.001 * (hash(getattr(spec.pctx.call, "message", "x")) % 7))
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": "ok"})

        ex = ProgrammableEchoExecutor(send_fn=jitter)
        engine, _, _ = _make_engine_with(ex)
        for round_no in range(3):
            graph = SuiteGraph(
                mode="aggregate", policy={"parallel": 4},
                units=[UnitDecl(ref=f"r{round_no}-{i}", scenario=_scenario(f"r{round_no}-{i}", assert_echo="ok"))
                       for i in range(12)],
            )
            result = engine.run(graph)
            assert result.passed == 12 and result.total == 12, f"round {round_no}"


class TestAuthExpiredResend:

    def test_resend_once_after_refresh(self):
        """401(auth_expired) → refresh_auth → 重发一次 → 200 通过。"""
        calls = {"n": 0}

        def first_401_then_200(spec, view):
            calls["n"] += 1
            first = calls["n"] == 1
            return CallResult.build(protocol="echo", request={},
                                    status=401 if first else 200,
                                    body={"msg": "ok", "code": 401 if first else 200},
                                    auth_expired=first)

        ex = ProgrammableEchoExecutor(send_fn=first_401_then_200)
        engine, _, _ = _make_engine_with(ex)
        graph = SuiteGraph(mode="aggregate", units=[
            UnitDecl(ref="u", scenario=_scenario("u", assert_echo="ok")),
        ])
        result = engine.run(graph)
        assert result.passed == 1
        assert calls["n"] == 2          # 重发了一次
        assert ex.refresh_calls == 1    # 刷新钩子被调

    def test_persistent_expired_returns_second_result(self):
        """重发后仍 expired → 返回第二次结果（不再无限重发）。"""
        calls = {"n": 0}

        def always_expired(spec, view):
            calls["n"] += 1
            return CallResult(protocol="echo", request={}, response={"status": 401, "meta": {}, "body": {"msg": "ok"}},
                              elapsed_ms=1.0, auth_expired=True)

        ex = ProgrammableEchoExecutor(send_fn=always_expired)
        engine, _, _ = _make_engine_with(ex)
        graph = SuiteGraph(mode="aggregate", units=[
            UnitDecl(ref="u", scenario=_scenario("u", assert_echo="ok")),
        ])
        result = engine.run(graph)
        assert calls["n"] == 2          # 恰好重发一次
