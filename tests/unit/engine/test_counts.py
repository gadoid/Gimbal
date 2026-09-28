"""P1-11 计数口径统一 + P1-12 timeout/retry 全链路（v2.1 review task-10）。

口径（成文，与 core/runner.py RunResult 注释一致）：
  - total / passed / failed / error / halted / blocked 一律**按单元计数**
    （一个 unit 恰计一次，与 details 行数对账）；
  - n_runs / retry 的执行展开不计 total，单列 RunResult.attempts
    = 总执行次数（每次真实调用 run_unit 计 1）。

覆盖：
  (a) n_runs=3 全通过 → (total, passed, attempts) == (1, 1, 3)；
  (b) 单元 timeout=0.5 + retry=2、step 睡 1.0s → attempts==3、failed==1，
      且 step 级留痕 error_phase="timeout"；
  (c) plan timeout=1.0、4 单元各睡 2.0s、parallel=1 → 未启动单元 cancelled；
  (d) scenario config.retry(maxAttempts=3) → 编译产物 UnitPolicy.retry == 2
      （backoffSeconds / retryOn 同步映射；policy_kwargs 显式覆盖优先）；
  (e) 退避期间不持 lock（Review Focus #5）——行为证明：退避窗口内
      其他线程可获取同标签锁；
  (f) retryOn 语义：空 = 任何失败都重试；非空 = 失败签名子串命中才重试。
"""
import dataclasses
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.auth.registry import AuthRegistry
from gimbal.config.models import BootstrapConfig
from gimbal.context.archive import InMemoryArchive
from gimbal.context.manager import ContextManager
from gimbal.core.bootstrap import Configuration
from gimbal.core.hooks import HookRegistry
from gimbal.core.runner import Engine, RunResult
from gimbal.events.bus import InMemoryEventBus
from gimbal.plugins import PluginRegistry
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor
from gimbal.protocols.result import CallResult
from gimbal.schema.call import Call
from gimbal.schema.plan import Plan, PlanPolicy, Unit, UnitPolicy
from gimbal.schema.retrypolicy import RetryPolicy
from gimbal.schema.scenario import (
    Config as ScenarioConfig, Meta, Scenario, SuiteGraph, UnitDecl,
)
from gimbal.schema.step import Step
from gimbal.scheduler.plan import PlanScheduler
from gimbal.strategy.dispatcher import build_default_dispatcher


# ── 可编程 echo 协议（可注入 sleep / send_fn）────────────────────

@dataclasses.dataclass
class EchoSpec:
    kind: str = "_call:echo"
    message: str = ""
    name: Optional[str] = "echo_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = dataclasses.field(default_factory=list)
    pctx: Optional[ProtocolCallContext] = None


class ProgrammableEchoExecutor(ProtocolExecutor):
    """send 行为由 send_fn 注入；默认睡 sleep_seconds 后返回 msg=ok。"""

    protocol = "echo"

    def __init__(self, send_fn=None, sleep_seconds: float = 0.0):
        super().__init__()
        self.sent: list[str] = []
        self.sleep_seconds = sleep_seconds
        self.send_fn = send_fn or (lambda spec, view: CallResult.build(
            protocol="echo", request={}, status=0, body={"msg": "ok"}))

    def build_spec(self, call, pctx):
        return EchoSpec(message=str(getattr(call, "message", "")), pctx=pctx)

    def send(self, spec, view):
        self.sent.append(spec.message)
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        return self.send_fn(spec, view)


def _make_engine_with(executor: ProtocolExecutor) -> Engine:
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
    return Engine(conf)


def _scenario(sid: str, assert_echo=None, retry: Optional[RetryPolicy] = None) -> Scenario:
    strategy = []
    if assert_echo is not None:
        strategy.append({"kind": "assertion", "name": "c",
                         "target": "$.call.response.body.msg",
                         "operator": "eq", "expected": assert_echo})
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=sid, description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(retry=retry),
        resource={},
        steps=[Step(call=Call(protocol="echo", message=sid), strategy=strategy)],
    )


def _make_plan(units: int = 1, policy_kwargs: dict | None = None,
               parallel: int = 1, plan_timeout: float | None = None) -> Plan:
    """最小 Plan：N 个无依赖单元（aggregate），统一单元策略 + Plan 级策略。

    单元场景带断言 msg == "ok"：send 返回别的值即失败（retryOn/失败
    计数测试依赖真实失败路径）。
    """
    return Plan(
        units=[Unit(id=f"u{i}", scenario=_scenario(f"u{i}", assert_echo="ok"),
                    policy=UnitPolicy(**(policy_kwargs or {})))
               for i in range(units)],
        policy=PlanPolicy(parallel=parallel, timeout=plan_timeout),
    )


def _run_plan_with(plan: Plan, executor: ProtocolExecutor) -> RunResult:
    """经 Engine._run_plan 真跑（真调度器 + 真 echo 协议；aggregate 判定路径）。"""
    engine = _make_engine_with(executor)
    framework_ctx = engine._ictx.ctx_manager.create_framework_context(
        run_id="run-counts", cfg=engine._ictx,
    )
    return engine._run_plan(plan, framework_ctx)


# ── (a) P1-11：计数按单元口径 + attempts 单列 ──────────────────

class TestCountsByUnit:

    def test_n_runs_counts_by_unit(self):
        """n_runs=3 全通过 → total=1 passed=1 attempts=3（旧口径 total=3 不一致）。"""
        ex = ProgrammableEchoExecutor(send_fn=lambda s, v: CallResult.build(
            protocol="echo", request={}, status=0, body={"msg": "ok"}))
        result = _run_plan_with(_make_plan(units=1, policy_kwargs={"n_runs": 3}), ex)
        assert (result.total, result.passed, result.attempts) == (1, 1, 3)
        assert result.failed == 0 and result.exit_code == 0
        assert len(ex.sent) == 3          # 3 次真实执行都在 attempts 里

    def test_n_runs_failure_stops_remaining_counts_unit(self):
        """n_runs=3 第 2 次失败 → 单元口径 total=1 failed=1，attempts=2（1 过 + 1 败）。"""
        counter = {"n": 0}

        def flaky(spec, view):
            counter["n"] += 1
            msg = "ok" if counter["n"] != 2 else "bad"
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": msg})

        ex = ProgrammableEchoExecutor(send_fn=flaky)
        result = _run_plan_with(
            _make_plan(units=1, policy_kwargs={"n_runs": 3}), ex)
        assert result.total == 1 and result.failed == 1
        assert result.attempts == 2       # 第 3 次未跑
        assert counter["n"] == 2

    def test_multi_unit_total_matches_details_rows(self):
        """3 单元各 1 次 → total=3 = details 行数；attempts 同为 3。"""
        ex = ProgrammableEchoExecutor(send_fn=lambda s, v: CallResult.build(
            protocol="echo", request={}, status=0, body={"msg": "ok"}))
        result = _run_plan_with(_make_plan(units=3), ex)
        assert result.total == len(result.details) == 3
        assert result.attempts == 3


# ── (b) P1-12：UnitPolicy.timeout 每次 attempt 包裹 + 触发 retry ──

class TestUnitTimeout:

    def test_unit_timeout_triggers_retry(self):
        """timeout=0.5 + retry=2、step 睡 1.0s → 3 次 attempt 全超时，failed=1。"""
        ex = ProgrammableEchoExecutor(send_fn=lambda s, v: CallResult.build(
            protocol="echo", request={}, status=0, body={"msg": "ok"}),
            sleep_seconds=1.0)
        plan = _make_plan(units=1, policy_kwargs={"timeout": 0.5, "retry": 2})
        result = _run_plan_with(plan, ex)
        assert result.attempts == 3 and result.failed == 1
        assert result.error == 0 and result.passed == 0
        # step 级留痕：超时的 attempt 带 error_phase="timeout"
        steps = result.details[0]["steps"]
        assert steps and any(s.get("error_phase") == "timeout" for s in steps)

    def test_unit_timeout_recovers_if_retry_passes(self):
        """首 attempt 超时、重试变快 → 单元最终通过，attempts=2。"""
        counter = {"n": 0}

        def slow_then_fast(spec, view):
            counter["n"] += 1
            if counter["n"] == 1:
                time.sleep(1.0)
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": "ok"})

        ex = ProgrammableEchoExecutor(send_fn=slow_then_fast)
        plan = _make_plan(units=1, policy_kwargs={"timeout": 0.4, "retry": 1})
        result = _run_plan_with(plan, ex)
        assert result.passed == 1 and result.attempts == 2

    def test_unit_timeout_not_set_runs_to_completion(self):
        """timeout=None：慢单元（0.6s）不被打断（历史行为保留）。"""
        ex = ProgrammableEchoExecutor(send_fn=lambda s, v: CallResult.build(
            protocol="echo", request={}, status=0, body={"msg": "ok"}),
            sleep_seconds=0.6)
        result = _run_plan_with(_make_plan(units=1), ex)
        assert result.passed == 1 and result.attempts == 1


# ── (c) P1-12：PlanPolicy.timeout 全局 deadline → cancelled ────

class TestPlanTimeout:

    def test_plan_timeout_cancels_remaining(self):
        """plan timeout=1.0、4 单元各睡 2.0s、parallel=1 → 后续单元 cancelled。"""
        ex = ProgrammableEchoExecutor(send_fn=lambda s, v: CallResult.build(
            protocol="echo", request={}, status=0, body={"msg": "ok"}),
            sleep_seconds=2.0)
        plan = _make_plan(units=4, parallel=1, plan_timeout=1.0)
        result = _run_plan_with(plan, ex)
        statuses = [d["status"] for d in result.details]
        assert "cancelled" in statuses
        assert len(ex.sent) == 1           # 未启动的单元确实没提交执行
        assert statuses.count("cancelled") == 3


# ── (d) P1-12：config.retry（RetryPolicy）→ UnitPolicy 映射 ────

class TestConfigRetryMapping:

    def test_config_retry_maps_to_unit_policy(self):
        """maxAttempts=3 → retry=2；backoffSeconds/retryOn 同步映射。"""
        from gimbal.compiler.pipeline import compile_target
        sc = _scenario("sc-retry", retry=RetryPolicy(
            maxAttempts=3, backoffSeconds=5, retryOn=["timeout-xyz"]))
        plan = compile_target(sc)
        assert plan.units[0].policy.retry == 2
        assert plan.units[0].policy.backoff_seconds == 5
        assert plan.units[0].policy.retry_on == ["timeout-xyz"]

    def test_config_retry_maps_in_graph_and_kwargs_override(self):
        """graph 路径同样映射；UnitDecl policy_kwargs 显式项覆盖场景声明。"""
        from gimbal.compiler.pipeline import compile_target
        sc = _scenario("sc-retry", retry=RetryPolicy(
            maxAttempts=3, backoffSeconds=5, retryOn=[]))
        graph = SuiteGraph(mode="aggregate", units=[
            UnitDecl(ref="u", scenario=sc, policy_kwargs={"retry": 5}),
        ])
        plan = compile_target(graph)
        assert plan.units[0].policy.retry == 5        # 显式覆盖
        assert plan.units[0].policy.backoff_seconds == 5  # 未覆盖项保留映射

    def test_config_retry_absent_keeps_defaults(self):
        """无 config.retry → UnitPolicy 默认值（retry=0/backoff=0/retry_on=[]）。"""
        from gimbal.compiler.pipeline import compile_target
        plan = compile_target(_scenario("sc-plain"))
        p = plan.units[0].policy
        assert (p.retry, p.backoff_seconds, p.retry_on) == (0, 0.0, [])


# ── (e) P1-12：退避期间不持 lock（Review Focus #5）──────────────

class _FakeResult:
    def __init__(self, uid: str, passed: bool = True):
        self.scenario_id = uid
        self.passed = passed
        self.status = "passed" if passed else "failed"
        self.attempts = [{"run": 1, "status": self.status, "passed": passed,
                          "retries": 0}]
        self.duration_ms = 0.0
        self.halted = False
        self.halt_reason = None
        self.step_results = []
        self.outputs = {}


class TestBackoffNotHoldingLock:

    def test_tag_lock_free_during_backoff(self):
        """行为证明：单元 timeout=0.3+retry=1+backoff=0.8+lock=db、step 睡 2.0s
        → 调度仍在跑（退避窗口 [0.3s,1.1s)）期间，外部线程能拿到同标签锁；
        若退避持锁，唯一放锁时刻是单元整体完成之后。"""
        calls = {"n": 0}

        def slow(unit, inputs):
            calls["n"] += 1
            time.sleep(2.0)
            return _FakeResult(unit.id)

        plan = _make_plan(units=1, policy_kwargs={
            "timeout": 0.3, "retry": 1, "backoff_seconds": 0.8, "lock": "db"})
        sched = PlanScheduler()
        tag_lock = sched._lock_for("db")
        acquired_at = {"at": None}
        finished_at = {"at": None}

        def _target():
            sched.run(plan, slow)
            finished_at["at"] = time.monotonic()

        t = threading.Thread(target=_target)
        t.start()
        try:
            # 先等第 1 次 attempt 真正开跑（calls>=1 ⟹ 调度线程已持有 db 锁），
            # 再开始探测——否则探测线程可能赶在调度线程拿锁之前空转成功，
            # 测试退化为恒真。持锁期间唯一放锁窗口 = 退避（Review Focus #5）。
            start_deadline = time.monotonic() + 8.0
            while calls["n"] < 1 and time.monotonic() < start_deadline:
                time.sleep(0.01)
            assert calls["n"] >= 1, "第 1 次 attempt 未启动（测试前置失败）"
            poll_deadline = time.monotonic() + 8.0
            while (time.monotonic() < poll_deadline
                   and acquired_at["at"] is None
                   and finished_at["at"] is None):
                if tag_lock.acquire(blocking=False):
                    acquired_at["at"] = time.monotonic()
                    tag_lock.release()
                time.sleep(0.02)
        finally:
            t.join(timeout=10.0)

        assert calls["n"] == 2                       # 两次 attempt 都真实发生
        assert finished_at["at"] is not None
        assert acquired_at["at"] is not None, "退避期间同标签锁完全不可获取（退避持锁）"
        assert acquired_at["at"] < finished_at["at"], "锁在单元完成后才可得，退避仍持锁"


# ── (f) P1-12：retryOn 匹配语义（子串简化，见任务报告）──────────

class TestRetryOnFilter:

    @staticmethod
    def _always_msg(msg: str):
        def _send(spec, view):
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": msg})
        return _send

    def test_retry_on_empty_retries_any_failure(self):
        """retryOn 空 → 任何失败都重试：retry=2 → attempts=3。"""
        ex = ProgrammableEchoExecutor(send_fn=self._always_msg("other-error"))
        plan = _make_plan(units=1, policy_kwargs={"retry": 2, "retry_on": []})
        result = _run_plan_with(plan, ex)
        assert result.attempts == 3 and result.failed == 1
        assert len(ex.sent) == 3

    def test_retry_on_nonempty_without_match_does_not_retry(self):
        """retryOn=["flaky-boom"] 而失败签名为 other-error → 不重试，attempts=1。"""
        ex = ProgrammableEchoExecutor(send_fn=self._always_msg("other-error"))
        plan = _make_plan(units=1,
                          policy_kwargs={"retry": 2, "retry_on": ["flaky-boom"]})
        result = _run_plan_with(plan, ex)
        assert result.attempts == 1 and result.failed == 1
        assert len(ex.sent) == 1

    def test_retry_on_match_retries(self):
        """retryOn 标签命中失败签名（断言错误文本含实际值）→ 重试至次数用尽。"""
        ex = ProgrammableEchoExecutor(send_fn=self._always_msg("flaky-boom"))
        plan = _make_plan(units=1,
                          policy_kwargs={"retry": 2, "retry_on": ["flaky-boom"]})
        result = _run_plan_with(plan, ex)
        assert result.attempts == 3 and result.failed == 1
        assert len(ex.sent) == 3
