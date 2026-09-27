"""P0-4 判定语义：before/after 括号失败计入判定，before 失败阻断主体。

验收值（来自评审修复案 task-3，逐字对齐）：
  - before 失败 → 主体全部 blocked（不执行），exit_code=1，
    blocked=2 / failed=1 / total=4（2 main + before + after）；after 仍总是执行；
  - after 失败 → failed += 1，exit_code=1（不影响其他行，主体照常）；
  - 括号行计入 total（before/after 各占一行，与主体统一行组装）；
  - exit_code = 0 iff failed == error == halted == blocked == 0。

两层覆盖：
  - Engine 层（真 echo 协议经 _run_plan → _assemble_aggregate）：计数/exit_code/details；
  - Scheduler 层（fake run_unit，仿 test_batch_d 的替身模式）：串行/并行两条路径
    的 blocked 置位与"主体不提交执行；after 必达"。
"""
import dataclasses
import os
import sys
from dataclasses import dataclass
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
from gimbal.schema.plan import Plan, PlanPolicy, Unit
from gimbal.schema.scenario import (
    Config as ScenarioConfig, Meta, Scenario,
)
from gimbal.schema.step import Step
from gimbal.scheduler.plan import PlanScheduler
from gimbal.strategy.dispatcher import build_default_dispatcher


# ── 真 echo 协议（message → body.echo；记录执行过的 message）────

@dataclass
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


class EchoExecutor(ProtocolExecutor):
    protocol = "echo"

    def __init__(self):
        super().__init__()
        self.sent: list[str] = []

    def build_spec(self, call, pctx):
        return EchoSpec(message=str(getattr(call, "message", "")), pctx=pctx)

    def send(self, spec, view):
        self.sent.append(spec.message)
        return CallResult.build(protocol=self.protocol,
                                request={"message": spec.message},
                                status=0, body={"echo": spec.message})


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


def _scenario(sid: str, *, passed: bool = True) -> Scenario:
    """单步 echo 场景：断言 echo == message（passed=False 时刻意不匹配 → 失败）。"""
    strategy = [{
        "kind": "assertion", "name": "chk",
        "target": "$.call.response.body.echo",
        "operator": "eq",
        "expected": sid if passed else "definitely-not-matching",
    }]
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


# ── brief 里的 make_plan_with_brackets / run_plan（此前不存在，此处落地）──

def make_plan_with_brackets(*, before_status: str = "passed",
                            after_status: str = "passed",
                            parallel: int = 1) -> Plan:
    """2 主体 + before + after 的最小 Plan（aggregate，单元 id = scenarioId）。"""
    return Plan(
        before=[Unit(id="pre", scenario=_scenario("pre", passed=(before_status == "passed")))],
        units=[Unit(id="main-1", scenario=_scenario("main-1")),
               Unit(id="main-2", scenario=_scenario("main-2"))],
        after=[Unit(id="post", scenario=_scenario("post", passed=(after_status == "passed")))],
        policy=PlanPolicy(parallel=parallel),
    )


def run_plan(plan: Plan) -> tuple[RunResult, list[str]]:
    """经 Engine._run_plan 真跑（真调度器 + 真 echo 协议）。

    返回 (RunResult, 已执行单元的 message 清单)——后者用于证明
    "主体未提交执行 / after 必达"。
    """
    ex = EchoExecutor()
    engine = _make_engine_with(ex)
    framework_ctx = engine._ictx.ctx_manager.create_framework_context(
        run_id="run-brackets", cfg=engine._ictx,
    )
    result = engine._run_plan(plan, framework_ctx)
    return result, ex.sent


# ── Engine 层：判定计数（brief Step 1 用例，断言值逐字对齐）────

class TestBracketVerdictSemantics:

    def test_before_failure_blocks_main_units(self):
        plan = make_plan_with_brackets(before_status="failed")   # before 单元断言失败
        result, sent = run_plan(plan)
        assert result.exit_code == 1
        statuses = {d["scenario_id"]: d["status"] for d in result.details}
        assert statuses["main-1"] == "blocked"
        assert result.blocked == 2 and result.failed == 1 and result.total == 4  # 2 main + before + after
        # 主体确未提交执行；after 必达仍执行且通过
        assert "main-1" not in sent and "main-2" not in sent
        assert "pre" in sent and "post" in sent
        assert statuses["main-2"] == "blocked"
        assert statuses["pre"] == "failed" and statuses["post"] == "passed"
        assert result.passed == 1

    def test_after_failure_counts(self):
        plan = make_plan_with_brackets(after_status="failed")
        result, sent = run_plan(plan)
        assert result.exit_code == 1 and result.failed == 1
        # after 失败不影响其他行：before/主体照常执行并通过
        assert result.passed == 3 and result.blocked == 0
        assert result.total == 4
        assert set(sent) == {"pre", "main-1", "main-2", "post"}

    def test_all_pass_brackets_count_into_total(self):
        """括号行计入 total：全过 → total=4 / passed=4 / exit_code=0。"""
        plan = make_plan_with_brackets()
        result, sent = run_plan(plan)
        assert result.exit_code == 0
        assert result.total == 4 and result.passed == 4
        assert result.failed == 0 and result.blocked == 0
        assert set(sent) == {"pre", "main-1", "main-2", "post"}

    def test_before_failure_blocks_main_units_parallel(self):
        """并行路径（parallel=2）同样阻断：主体不提交执行，after 必达。"""
        plan = make_plan_with_brackets(before_status="failed", parallel=2)
        result, sent = run_plan(plan)
        assert result.exit_code == 1
        statuses = {d["scenario_id"]: d["status"] for d in result.details}
        assert statuses["main-1"] == "blocked" and statuses["main-2"] == "blocked"
        assert result.blocked == 2 and result.failed == 1 and result.total == 4
        assert "main-1" not in sent and "main-2" not in sent
        assert "pre" in sent and "post" in sent


# ── Scheduler 层：before 判定门（串行/并行两路径；仿 test_batch_d 替身）──

class _FakeResult:
    """替身结果：补齐 _assemble_aggregate / 调度器读取的全部字段。"""

    def __init__(self, uid: str, passed: bool = True):
        self.scenario_id = uid
        self.passed = passed
        self.status = "passed" if passed else "failed"
        self.attempts = [{"run": 1, "status": self.status, "passed": passed}]
        self.duration_ms = 0.0
        self.halted = False
        self.halt_reason = None
        self.step_results = []
        self.outputs = {}


def _unit(uid: str) -> Unit:
    return Unit(id=uid, scenario=_scenario(uid))


def _bracket_plan(parallel: int) -> Plan:
    return Plan(
        before=[_unit("pre")],
        units=[_unit("main-1"), _unit("main-2")],
        after=[_unit("post")],
        policy=PlanPolicy(parallel=parallel),
    )


class TestSchedulerBeforeGate:

    def test_serial_before_failure_blocks_mains(self):
        """串行路径：before 异常 → 主体置 blocked 不提交；after 必达。"""
        plan = _bracket_plan(parallel=1)
        ran = []

        def fake(unit, inputs):
            ran.append(unit.id)
            if unit.id == "pre":
                raise RuntimeError("before boom")
            return _FakeResult(unit.id)

        outcome = PlanScheduler().run(plan, fake)
        assert ran == ["pre", "post"]        # 主体未提交执行
        assert outcome.status_of("main-1") == "blocked"
        assert outcome.status_of("main-2") == "blocked"
        assert "main-1" not in outcome.results and "main-2" not in outcome.results
        assert "post" in outcome.results     # after 仍执行

    def test_parallel_before_failure_blocks_mains(self):
        """并行路径（parallel=2）：同一判定门生效。"""
        plan = _bracket_plan(parallel=2)
        ran = []

        def fake(unit, inputs):
            ran.append(unit.id)
            if unit.id == "pre":
                raise RuntimeError("before boom")
            return _FakeResult(unit.id)

        outcome = PlanScheduler().run(plan, fake)
        assert ran == ["pre", "post"]
        assert {"main-1", "main-2"} <= outcome.blocked
        assert "main-1" not in outcome.results and "main-2" not in outcome.results

    def test_before_not_passed_result_blocks_mains(self):
        """before 返回 failed 结果（非异常）→ 同样阻断主体。"""
        plan = _bracket_plan(parallel=1)
        ran = []

        def fake(unit, inputs):
            ran.append(unit.id)
            return _FakeResult(unit.id, passed=(unit.id != "pre"))

        outcome = PlanScheduler().run(plan, fake)
        assert ran == ["pre", "post"]
        assert outcome.status_of("main-1") == "blocked"
        assert outcome.status_of("main-2") == "blocked"

    def test_before_passed_mains_execute_normally(self):
        """对照：before 通过 → 主体正常执行，无 blocked/cancelled。"""
        plan = _bracket_plan(parallel=1)
        ran = []
        outcome = PlanScheduler().run(
            plan, lambda u, i: ran.append(u.id) or _FakeResult(u.id),
        )
        assert ran == ["pre", "main-1", "main-2", "post"]
        assert not outcome.blocked and not outcome.cancelled
