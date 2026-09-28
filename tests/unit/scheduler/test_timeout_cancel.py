"""调度器 attempt 超时的协作取消（上轮遗漏 #2 回归钉死）。

复现口径：超时弃跑的线程若继续执行后续 step,会与重试并发重复发请求
（下单类接口 = 重复下单）。协作取消后,被弃线程在 step 边界自行终止。
"""
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.auth.registry import AuthRegistry
from gimbal.compiler.pipeline import compile_target
from gimbal.config.models import BootstrapConfig
from gimbal.context.archive import InMemoryArchive
from gimbal.context.manager import ContextManager
from gimbal.core.runner import Engine, Configuration
from gimbal.events.bus import InMemoryEventBus
from gimbal.plugins import PluginRegistry
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor
from gimbal.protocols.result import CallResult
from gimbal.schema.scenario import Config as SC, Meta, Scenario, SuiteGraph
from gimbal.schema.step import Step
from gimbal.schema.call import Call
from gimbal.scheduler.plan import PlanScheduler
from gimbal.core.hooks import HookRegistry
from gimbal.strategy.dispatcher import build_default_dispatcher

calls = {"n": 0}
lock = threading.Lock()
# 并发观测:发送中 concurrently 计数与历史峰值（锁语义回归用）
conc = {"cur": 0, "max": 0}
SLOW_SECONDS = {"slow": 0.5, "firstslow": None}   # firstslow: 首次 0.35 之后秒回


@dataclass
class SlowSpec:
    kind: str = "call:slow"
    message: str = ""
    name: Optional[str] = "slow_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = field(default_factory=list)
    pctx: Optional[ProtocolCallContext] = None


class TimedProtocolExecutor(ProtocolExecutor):
    """按 message 决定耗时（slow=0.5s / firstslow=首次 0.35s 后秒回）,
    并发计数观测。"""

    protocol = "timed"

    def build_spec(self, call, pctx):
        return SlowSpec(message=getattr(call, "message", ""), pctx=pctx)

    def send(self, spec, view):
        with lock:
            calls["n"] += 1
            conc["cur"] += 1
            conc["max"] = max(conc["max"], conc["cur"])
            n = calls["n"]
        msg = spec.message
        if msg == "slow":
            time.sleep(0.5)
        elif msg == "firstslow":
            time.sleep(0.35 if n == 1 else 0.0)
        try:
            return CallResult.build(
                protocol=self.protocol, request={"message": msg},
                status=0, body={"ok": True})
        finally:
            with lock:
                conc["cur"] -= 1


class SlowProtocolExecutor(ProtocolExecutor):
    """每 step 发送耗时 0.25s 的慢协议；计数全局共享。"""

    protocol = "slow"

    def build_spec(self, call, pctx):
        return SlowSpec(message=getattr(call, "message", ""), pctx=pctx)

    def send(self, spec, view):
        with lock:
            calls["n"] += 1
        time.sleep(0.25)
        return CallResult.build(
            protocol=self.protocol, request={"message": spec.message},
            status=0, body={"ok": True},
        )


def _make_configuration():
    bus = InMemoryEventBus()
    archive = InMemoryArchive()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks, event_bus=bus)
    dispatcher.protocols.register(SlowProtocolExecutor())
    return Configuration(
        cfg=BootstrapConfig(env="test", mode="local", log_level="error"),
        auth_registry=AuthRegistry(),
        ctx_manager=ContextManager(archive=archive, event_bus=bus),
        dispatcher=dispatcher, event_bus=bus, archive=archive,
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )


def _scenario(sid: str, n_steps: int = 2) -> Scenario:
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=sid, description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=SC(),
        resource={},
        steps=[Step(call=Call(protocol="slow", message=f"{sid}-{i}"), strategy=[])
               for i in range(n_steps)],
    )


class TestTimeoutCooperativeCancel:

    def test_abandoned_attempt_stops_at_step_boundary(self):
        """timeout=0.15 + 2 步慢场景（发送各 0.25s）:超时确定落在 step1
        发送中（step1 于 ~0.02s 起发、0.27s 后才到边界）,被弃线程发完
        step1 后必须停在边界,不得继续发 step2（修复前 sends==2,修复后 ==1）。"""
        conf = _make_configuration()
        engine = Engine(conf)
        sc = _scenario("cancel-sc", n_steps=2)
        plan = compile_target(sc)
        plan.units[0].policy.timeout = 0.15  # 落在 step1 发送中(step1 ~0.02s 起发)

        sched = PlanScheduler(event_bus=conf.event_bus)
        from gimbal.core.runner import Engine as _E   # noqa: F401

        def _run_unit(unit, inputs, cancel=None):
            from gimbal.core.scenario_runner import RuntimeControl
            rc = RuntimeControl(cancel_event=cancel)
            return _direct_run(conf, unit.scenario, rc)

        outcome = sched.run(plan, _run_unit)
        result = outcome.results.get("cancel-sc")
        # attempt 收口为 timeout 失败
        assert result is not None
        # 等被弃线程的 step1 发送结束 + 边界检查
        time.sleep(0.8)
        with lock:
            sent = calls["n"]
        assert sent == 1, (
            f"被弃线程越过了 step 边界（sends={sent}）——协作取消未生效"
        )


def _direct_run(conf, scenario, rc):
    """直接经 ScenarioRunner 执行（模拟 Engine._run_unit 的场景路径）。"""
    from gimbal.core.scenario_runner import ScenarioRunner
    from gimbal.context.manager import ContextManager
    ctx_manager = conf.ctx_manager
    fctx = ctx_manager.create_framework_context(cfg=conf, run_id="cancel-test")   # 引擎口径:cfg 形参收 Configuration
    suite_ctx = ctx_manager.derive_suite_context(
        fctx, suite_id="__default__", suite_name="t", tags=[], plugins={})
    runner = ScenarioRunner(
        conf.dispatcher, ctx_manager,
        hook_registry=conf.hook_registry, event_bus=conf.event_bus,
        auth_registry=conf.auth_registry, protocol_registry=conf.protocols,
    )
    return runner.run(scenario, suite_ctx, runtime_control=rc)


class TestSharedRuntimeControlPollution:
    """上轮引入的回归:协作取消事件写入共享 RuntimeControl 后泄漏给全部单元。"""

    def test_shared_rc_not_polluted_chain_retry_recovers(self):
        """chain:a(timeout=0.2, retry=1, 首次慢) + b(快)。
        传入共享 RuntimeControl() —— 修复前 a 的重试被泄漏的取消事件
        立即取消(__scenario_cancelled__)、b 记 blocked、exit=1;
        修复后(每调用复制)a 重试通过、b 通过、exit=0。"""
        from gimbal.compiler.pipeline import compile_target
        from gimbal.core.runner import Engine
        from gimbal.core.scenario_runner import RuntimeControl
        from gimbal.schema.scenario import SuiteGraph, UnitDecl

        conf = _make_configuration()
        conf.dispatcher.protocols.register(TimedProtocolExecutor())
        engine = Engine(conf)

        from gimbal.schema.step import Step
        from gimbal.schema.call import Call

        def _timed_step(msg):
            return Step(call=Call(protocol="timed", message=msg), strategy=[])

        a = UnitDecl(ref="a", scenario=Scenario(
            scenarioId="a",
            meta=_scenario("a").meta,
            config=SC(),
            resource={},
            steps=[_timed_step("firstslow")],
        ), policy_kwargs={"timeout": 0.2, "retry": 1})
        b = UnitDecl(ref="b", scenario=Scenario(
            scenarioId="b",
            meta=_scenario("b").meta,
            config=SC(),
            resource={},
            steps=[_timed_step("fast")],
        ))
        graph = SuiteGraph(kind="graph", mode="chain", units=[a, b])
        result = engine.run(graph, runtime_control=RuntimeControl())
        assert result.exit_code == 0, (
            f"共享 RC 被污染(重试被取消/b blocked): exit={result.exit_code} "
            f"details={[d['status'] for d in result.details]}"
        )


class TestTimeoutJoinBeforeRetry:
    """超时后的 join:重试不与被弃请求并发,锁释放前弃请求已退出。"""

    def test_no_concurrent_overlap_under_lock(self):
        """请求 0.5s、timeout=0.2、retry=2、lock=db + 同锁快单元:
        修复前 4 次请求/同锁最多 3 并发;修复后 a 恰 3 次(attempt+2 retries)
        串行、b 1 次、全程同锁并发峰值 = 1。"""
        from gimbal.compiler.pipeline import compile_target
        from gimbal.core.runner import Engine
        from gimbal.schema.scenario import SuiteGraph, UnitDecl
        from gimbal.schema.step import Step
        from gimbal.schema.call import Call

        conf = _make_configuration()
        conf.dispatcher.protocols.register(TimedProtocolExecutor())
        engine = Engine(conf)
        calls["n"] = 0
        conc.update(cur=0, max=0)

        a = UnitDecl(ref="a", scenario=Scenario(
            scenarioId="a", meta=_scenario("a").meta, config=SC(),
            resource={}, steps=[Step(call=Call(protocol="timed", message="slow"),
                                     strategy=[])]),
            policy_kwargs={"timeout": 0.2, "retry": 2, "lock": "db"})
        b = UnitDecl(ref="b", scenario=Scenario(
            scenarioId="b", meta=_scenario("b").meta, config=SC(),
            resource={}, steps=[Step(call=Call(protocol="timed", message="fast"),
                                     strategy=[])]),
            policy_kwargs={"lock": "db"})
        graph = SuiteGraph(kind="graph", mode="aggregate", units=[a, b])
        result = engine.run(graph)
        # a 三次 attempt 全超时(失败收口),b 在锁释放后正常执行
        assert result.exit_code != 0
        with lock:
            total, peak = calls["n"], conc["max"]
        assert total == 4, f"a 应恰 3 次(attempt+2 retries)+b 1 次,得到 {total}"
        assert peak == 1, f"同锁下不应有并发重叠,峰值 {peak}"
