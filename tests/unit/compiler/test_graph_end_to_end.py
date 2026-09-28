"""批次 C 端到端：编排图经 Engine 真跑（echo 协议）——数据流转/blocked/括号。

验收门：三模式端到端 + 三形态连线（数据真实流过：上游 extract 提升 →
调度器收集 outputs → 连线注入下游 vars → 模板解析 → 断言验证）。
"""
import dataclasses
import os
import sys
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
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor
from gimbal.protocols.result import CallResult
from gimbal.schema.call import Call
from gimbal.schema.scenario import (
    Config as ScenarioConfig, Meta, Scenario, SuiteGraph, UnitDecl,
)
from gimbal.schema.step import Step
from gimbal.scheduler.plan import PlanScheduler
from gimbal.strategy.dispatcher import build_default_dispatcher


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
    pctx: Optional[ProtocolCallContext] = None


class EchoExecutor(ProtocolExecutor):
    protocol = "echo"

    def build_spec(self, call, pctx):
        return EchoSpec(message=str(getattr(call, "message", "")), pctx=pctx)

    def send(self, spec, view):
        return CallResult.build(protocol=self.protocol,
                                request={"message": spec.message},
                                status=0, body={"echo": spec.message})


def _make_engine():
    bus = InMemoryEventBus()
    archive = InMemoryArchive()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks)
    dispatcher.protocols.register(EchoExecutor())
    ctx_manager = ContextManager(archive=archive, event_bus=bus)
    cfg = BootstrapConfig(env="test", mode="local", log_level="error")
    conf = Configuration(
        cfg=cfg, auth_registry=AuthRegistry(), ctx_manager=ctx_manager,
        dispatcher=dispatcher, event_bus=bus, archive=archive,
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    return Engine(conf)


def _scenario(sid: str, *, message=None, extract_to=None, assert_echo=None, vars=None):
    strategy = []
    if extract_to:
        strategy.append({"kind": "extract", "name": "out",
                         "expression": "$.call.response.body.echo",
                         "target": extract_to, "scope": "scenario"})
    if assert_echo is not None:
        strategy.append({"kind": "assertion", "name": "chk",
                         "target": "$.call.response.body.echo",
                         "operator": "eq", "expected": assert_echo})
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=sid, description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(vars=vars or {}),
        resource={},
        steps=[Step(call=Call(protocol="echo", message=message or sid),
                    strategy=strategy)],
    )


class TestDataFlow:

    def test_chain_real_variable_flow(self):
        """chain：a 产出 greeting → b 模板消费并断言（数据真实流过）。"""
        engine = _make_engine()
        graph = SuiteGraph(
            mode="chain",
            units=[
                UnitDecl(ref="a", scenario=_scenario(
                    "a", message="hello-from-a", extract_to="greeting")),
                UnitDecl(ref="b", scenario=_scenario(
                    "b", message="${var.greeting}", extract_to="heard",
                    assert_echo="hello-from-a")),
            ],
        )
        result = engine.run(graph)
        assert result.exit_code == 0, [d for d in result.details]
        assert result.passed == 2
        rows = {d["scenario_id"]: d for d in result.details}
        assert rows["b"]["status"] == "passed"   # b 断言收到的就是 a 的输出

    def test_compose_parallel_with_shared_upstream(self):
        """compose 并行：一源两汇，两个汇都拿到源的输出。"""
        engine = _make_engine()
        graph = SuiteGraph(
            mode="compose",
            policy={"parallel": 2},
            units=[
                UnitDecl(ref="src", scenario=_scenario(
                    "src", message="TOKEN-1", extract_to="token")),
                UnitDecl(ref="u1", scenario=_scenario(
                    "u1", message="${var.token}", assert_echo="TOKEN-1"),
                    needs=["src"]),
                UnitDecl(ref="u2", scenario=_scenario(
                    "u2", message="${var.token}", assert_echo="TOKEN-1"),
                    needs=["src"]),
            ],
        )
        result = engine.run(graph)
        assert result.passed == 3 and result.exit_code == 0

    def test_fanout_end_to_end(self):
        engine = _make_engine()
        graph = SuiteGraph(
            mode="fanout",
            units=[
                UnitDecl(ref="s", scenario=_scenario("s", message="FAN",
                                                     extract_to="v")),
                UnitDecl(ref="x", scenario=_scenario("x", message="${var.v}",
                                                     assert_echo="FAN")),
                UnitDecl(ref="y", scenario=_scenario("y", message="${var.v}",
                                                     assert_echo="FAN")),
            ],
        )
        result = engine.run(graph)
        assert result.passed == 3


class TestBlockedAndBrackets:

    def test_blocked_cascade_on_upstream_failure(self):
        """compose：中间单元失败 → 下游 blocked（不是 cancelled/failed）。"""
        engine = _make_engine()
        graph = SuiteGraph(
            mode="chain",
            units=[
                UnitDecl(ref="a", scenario=_scenario("a", message="v",
                                                     extract_to="tok")),
                UnitDecl(ref="bad", scenario=_scenario(
                    "bad", message="${var.tok}", extract_to="tok_bad",
                    assert_echo="definitely-not-matching")),   # 断言失败
                UnitDecl(ref="c", scenario=_scenario("c", message="${var.tok}",
                                                     assert_echo="v")),
            ],
        )
        result = engine.run(graph)
        statuses = [d["status"] for d in result.details]
        assert statuses == ["passed", "failed", "blocked"]
        assert result.blocked == 1
        assert result.exit_code == 1

    def test_after_bracket_always_runs_despite_failure(self):
        """after 必达：主体失败，清理单元仍执行。"""
        engine = _make_engine()
        after_ran = _scenario("cleanup", message="cleaned", extract_to="cleaned_at")
        graph = SuiteGraph(
            mode="aggregate",
            units=[UnitDecl(ref="boom", scenario=_scenario(
                "boom", message="x", assert_echo="never"))],
            after=[UnitDecl(ref="cleanup", scenario=after_ran)],
        )
        result = engine.run(graph)
        assert result.failed == 1
        rows = [d for d in result.details if d.get("bracket") == "after"]
        assert rows and rows[0]["status"] == "passed"
        assert rows[0]["scenario_id"] == "cleanup"

    def test_before_output_feeds_all_units(self):
        """before 全局前置：登录产出 token，主体单元消费。"""
        engine = _make_engine()
        graph = SuiteGraph(
            mode="aggregate",
            before=[UnitDecl(ref="login", scenario=_scenario(
                "login", message="SESSION-9", extract_to="token"))],
            units=[
                UnitDecl(ref="u1", scenario=_scenario(
                    "u1", message="${var.token}", assert_echo="SESSION-9")),
                UnitDecl(ref="u2", scenario=_scenario(
                    "u2", message="${var.token}", assert_echo="SESSION-9")),
            ],
        )
        result = engine.run(graph)
        # P0-4：括号行计入 total/passed —— login(before) + u1 + u2 各占一行
        assert result.passed == 3 and result.exit_code == 0
        assert result.total == 3


# ── P0-5：after 可见上游含全部主体单元（清理单元引用主体产出）──

def _scenario_extract_missing(sid: str, *, extract_to: str) -> Scenario:
    """响应缺字段的提取：extract 失败（required，无 default，不提升）→
    单元失败且输出面为空。

    编译期 extract 声明仍在（分析输出面含 extract_to，bind 据此连线），
    运行期却产不出该名——正是"主体未产出 → after 注入 None"的触发路径。
    """
    strategy = [
        {"kind": "extract", "name": "out",
         "expression": "$.call.response.body.absent_field",
         "target": extract_to, "scope": "scenario"},
    ]
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


class TestAfterConsumesMainOutputs:

    def _graph(self):
        """主体提取 orderId，after 引用 ${orderId}（清理总案的最小形态）。"""
        return SuiteGraph(
            mode="aggregate",
            units=[UnitDecl(ref="main-1", scenario=_scenario(
                "main-1", message="ORD-7", extract_to="orderId"))],
            after=[UnitDecl(ref="after-1", scenario=_scenario(
                "after-1", message="cancel-${var.orderId}"))],
        )

    def test_after_consumes_main_output(self):
        """主体提取 orderId，after 引用 ${orderId} → 编译通过且 wire 指向主体。"""
        from gimbal.compiler.pipeline import compile_target
        plan = compile_target(self._graph())
        assert plan.wiring.get("after-1", {}).get("orderId") == "main-1:orderId"
        assert not plan.after_optional            # 该输入有供给：不记 optional

    def test_after_receives_main_output_end_to_end(self):
        """数据真实流过：主体产出 orderId → after 取消单据断言收到的就是它。"""
        engine = _make_engine()
        graph = SuiteGraph(
            mode="aggregate",
            units=[UnitDecl(ref="main-1", scenario=_scenario(
                "main-1", message="ORD-7", extract_to="orderId"))],
            after=[UnitDecl(ref="after-1", scenario=_scenario(
                "after-1", message="cancel-${var.orderId}",
                assert_echo="cancel-ORD-7"))],
        )
        result = engine.run(graph)
        assert result.exit_code == 0, [d for d in result.details]
        assert result.passed == 2

    def test_after_unsupplied_input_no_compile_error(self):
        """after 引用无人产出的 refundId → 不 CompileError；有供给的照常连线。"""
        from gimbal.compiler.pipeline import compile_target
        graph = SuiteGraph(
            mode="aggregate",
            units=[UnitDecl(ref="main-1", scenario=_scenario(
                "main-1", message="ORD-7", extract_to="orderId"))],
            after=[UnitDecl(ref="after-1", scenario=_scenario(
                "after-1", message="cancel-${var.orderId}-${var.refundId}"))],
        )
        plan = compile_target(graph)
        assert plan.after_optional == {"after-1"}   # 缺供给的单元成文记录
        assert plan.wiring["after-1"] == {"orderId": "main-1:orderId"}  # 有供给的照常连

    def test_after_input_missing_at_runtime_injects_none(self):
        """主体失败未产出 orderId → after 输入注入 None（非跳过）+ debug 事件。"""
        from gimbal.compiler.pipeline import compile_target
        bus = InMemoryEventBus()
        events = []
        bus.subscribe(events.append, "debug.after_input_missing")

        class _FakeResult:
            def __init__(self, uid: str, *, passed: bool = True, outputs: dict | None = None):
                self.scenario_id = uid
                self.passed = passed
                self.status = "passed" if passed else "failed"
                self.outputs = outputs or {}

        seen: dict[str, dict] = {}

        def fake_unit_run(unit, inputs):
            seen[unit.id] = dict(inputs)
            if unit.id == "main-1":
                return _FakeResult(unit.id, passed=False)   # 失败且未产出 orderId
            return _FakeResult(unit.id)

        plan = compile_target(self._graph())
        outcome = PlanScheduler(event_bus=bus).run(plan, fake_unit_run)

        assert outcome.status_of("after-1") == "done"        # 必达执行完（非 blocked/crash）
        assert outcome.results["after-1"].passed is True
        assert "orderId" in seen["after-1"]                  # 注入（而非缺失跳过）
        assert seen["after-1"]["orderId"] is None
        assert len(events) == 1
        assert events[0].event_type == "debug.after_input_missing"
        assert events[0].unit_id == "after-1"
        assert events[0].input_name == "orderId"
        assert events[0].source == "main-1:orderId"

    def test_after_input_missing_end_to_end_still_runs(self):
        """端到端：主体失败（提取字段缺失、未产出 orderId）→ after 注入 None 跑完。"""
        engine = _make_engine()
        graph = SuiteGraph(
            mode="aggregate",
            units=[UnitDecl(ref="main-1", scenario=_scenario_extract_missing(
                "main-1", extract_to="orderId"))],
            after=[UnitDecl(ref="after-1", scenario=_scenario(
                "after-1", message="cancel-${var.orderId}",
                assert_echo="cancel-"))],   # None 渲染空串 → "cancel-"
        )
        result = engine.run(graph)
        rows = {d["scenario_id"]: d for d in result.details}
        assert rows["main-1"]["status"] == "failed"
        assert rows["after-1"]["status"] == "passed"        # 不 CompileError、不 Crash
        assert result.failed == 1 and result.exit_code == 1
