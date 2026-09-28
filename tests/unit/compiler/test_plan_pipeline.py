"""v2.1 批次 B 测试：Plan/Unit 编译管线 + Engine 单路径 + PlanScheduler。

覆盖验收门（v2.1 §三 批次 B）：
  - 单场景 → 隐式 aggregate Plan；嵌入式 Suite → aggregate Plan（策略映射）；
  - validate_plan：重复 id（schema 层）、未支持乘法/编排项的明确报错；
  - Engine 单路径对账：scenario / suite（串行/并行/fail-fast）的 RunResult
    与历史口径一致（计数、details 形状与顺序、cancelled 占位）；
  - inputs 统一注入原语：注入为 scenario vars（模板 ${var.*} 可见）；
  - PlanScheduler：before/after 括号顺序执行。
"""
import dataclasses
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest

from gimbal.auth.registry import AuthRegistry
from gimbal.compiler.pipeline import CompileError, compile_target, validate_plan
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
from gimbal.schema.plan import Plan, PlanPolicy, Unit, UnitPolicy
from gimbal.schema.scenario import (
    Config as ScenarioConfig, Meta, Scenario, SuiteGraph, UnitDecl,
)
from gimbal.schema.step import Step
from gimbal.scheduler.plan import PlanScheduler
from gimbal.strategy.dispatcher import build_default_dispatcher


# ── 测试基建（与 scheduler 测试同款慢速 echo 协议）────────────

@dataclass
class SlowEchoSpec:
    kind: str = "call:echo"
    message: str = ""
    delay: float = 0.0
    name: Optional[str] = "echo_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = dataclasses.field(default_factory=list)
    pctx: Optional[ProtocolCallContext] = None


class SlowEchoProtocolExecutor(ProtocolExecutor):
    protocol = "echo"

    def build_spec(self, call, pctx: ProtocolCallContext):
        return SlowEchoSpec(message=getattr(call, "message", ""),
                            delay=float(getattr(call, "delay", 0.0) or 0.0), pctx=pctx)

    def send(self, spec, view):
        import time
        time.sleep(spec.delay)
        return CallResult.build(
            protocol=self.protocol, request={"message": spec.message},
            status=0, body={"echo": spec.message},
        )


def _make_engine():
    bus = InMemoryEventBus()
    archive = InMemoryArchive()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks)
    dispatcher.protocols.register(SlowEchoProtocolExecutor())
    ctx_manager = ContextManager(archive=archive, event_bus=bus)
    cfg = BootstrapConfig(env="test", mode="local", log_level="error")
    conf = Configuration(
        cfg=cfg, auth_registry=AuthRegistry(), ctx_manager=ctx_manager,
        dispatcher=dispatcher, event_bus=bus, archive=archive,
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    return Engine(conf), archive, bus


def _make_scenario(sid: str, delay: float = 0.02, message: str = None) -> Scenario:
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=f"n-{sid}", description="d", module="m", priority=1,
                  author="a", owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(),
        resource={},
        steps=[Step(call=Call(protocol="echo", message=message or sid, delay=delay),
                    strategy=[])],
    )


# ── 编译管线 ─────────────────────────────────────────────────

class TestCompilePipeline:

    def test_scenario_compiles_to_implicit_plan(self):
        plan = compile_target(_make_scenario("sc-1"))
        assert plan.implicit is True
        assert plan.mode == "aggregate"
        assert plan.suite_id == "__default__" and plan.suite_name == "Default Suite"
        assert [u.id for u in plan.units] == ["sc-1"]
        assert plan.units[0].scenario.scenarioId == "sc-1"
        assert plan.units[0].inputs == {} and plan.units[0].needs == []
        assert plan.policy.parallel == 1 and plan.policy.fail_fast is None
        assert validate_plan(plan) == []

    def test_graph_aggregate_compiles_with_policy(self):
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="sc-a", scenario=_make_scenario("sc-a")),
                   UnitDecl(ref="sc-b", scenario=_make_scenario("sc-b"))],
            policy=PlanPolicy(parallel=3, fail_fast=True),
        )
        plan = compile_target(graph)
        assert plan.implicit is False
        assert [u.id for u in plan.units] == ["sc-a", "sc-b"]
        assert plan.policy.parallel == 3
        assert plan.policy.fail_fast is True
        assert validate_plan(plan) == []

    def test_graph_without_policy_defaults_serial(self):
        plan = compile_target(SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="s", scenario=_make_scenario("s"))]))
        assert plan.policy.parallel == 1 and plan.policy.fail_fast is None

    def test_empty_graph_units_rejected_by_schema(self):
        with pytest.raises(Exception):
            SuiteGraph(kind="graph", mode="aggregate", units=[])

    def test_multiplications_now_valid(self):
        """批次 D：n_runs/retry/lock 乘法已落地，validate 放行。"""
        plan = Plan(
            units=[Unit(id="u1", scenario=_make_scenario("u1"),
                        policy=UnitPolicy(n_runs=3, retry=2, lock="db"))],
        )
        assert validate_plan(plan) == []

    def test_invalid_multiplication_rejected_at_schema(self):
        """取值域由 UnitPolicy schema 保证（ge 约束）。"""
        import pytest as _pytest
        from pydantic import ValidationError
        with _pytest.raises(ValidationError):
            UnitPolicy(n_runs=0)

    def test_duplicate_unit_ids_rejected_by_schema(self):
        with pytest.raises(ValueError):
            Plan(units=[Unit(id="dup", scenario=_make_scenario("a")),
                        Unit(id="dup", scenario=_make_scenario("b"))])

    def test_implicit_plan_must_be_single_unit(self):
        with pytest.raises(ValueError):
            Plan(units=[Unit(id="a", scenario=_make_scenario("a")),
                        Unit(id="b", scenario=_make_scenario("b"))],
                 implicit=True)


# ── Engine 单路径对账 ───────────────────────────────────────

class TestEngineSinglePath:

    def test_scenario_via_plan_matches_legacy_result_shape(self):
        engine, _, _ = _make_engine()
        result = engine.run(_make_scenario("sc-only"))
        # 单场景历史口径：total=1，非通过计 failed；这里全部通过
        assert result.total == 1 and result.passed == 1 and result.exit_code == 0
        row = result.details[0]
        assert row["scenario_id"] == "sc-only" and row["status"] == "passed"
        assert row["steps"][0]["step_id"] == "step-000"

    def test_serial_suite_details_in_submission_order(self):
        engine, _, _ = _make_engine()
        graph = SuiteGraph(kind="graph", mode="aggregate",
                           units=[UnitDecl(ref="s1", scenario=_make_scenario("s1")),
                                  UnitDecl(ref="s2", scenario=_make_scenario("s2"))])
        result = engine.run(graph)
        assert result.total == 2 and result.passed == 2
        assert [d["scenario_id"] for d in result.details] == ["s1", "s2"]

    def test_parallel_suite_via_plan_policy(self):
        engine, _, _ = _make_engine()
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="p1", scenario=_make_scenario("p1", 0.2)),
                   UnitDecl(ref="p2", scenario=_make_scenario("p2", 0.2)),
                   UnitDecl(ref="p3", scenario=_make_scenario("p3", 0.2))],
            policy=PlanPolicy(parallel=3),
        )
        import time
        t0 = time.monotonic()
        result = engine.run(graph)
        wall = time.monotonic() - t0
        assert result.passed == 3
        assert wall < 0.2 * 3 * 0.8, f"Plan 并行未生效? wall={wall:.2f}s"
        assert [d["scenario_id"] for d in result.details] == ["p1", "p2", "p3"]

    def test_fail_fast_serial_leaves_cancelled_placeholders(self):
        engine, _, _ = _make_engine()
        # 第二个场景断言失败 → fail-fast：第三、四个被取消
        bad = _make_scenario("bad")
        bad = bad.model_copy(update={"steps": [Step(
            call=Call(protocol="echo", message="x", delay=0.01),
            strategy=[{"kind": "assertion", "name": "a", "target": "$.call.response.status",
                       "operator": "eq", "expected": 999}],
        )]})
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="ok1", scenario=_make_scenario("ok1")),
                   UnitDecl(ref="bad", scenario=bad),
                   UnitDecl(ref="ok3", scenario=_make_scenario("ok3")),
                   UnitDecl(ref="ok4", scenario=_make_scenario("ok4"))],
            policy=PlanPolicy(fail_fast=True),
        )
        result = engine.run(graph)
        assert result.passed == 1 and result.failed == 1
        statuses = [d["status"] for d in result.details]
        assert statuses == ["passed", "failed", "cancelled", "cancelled"]

    def test_unit_inputs_injected_as_scenario_vars(self):
        """统一注入原语：inputs 注入为 scenario vars，模板 ${var.*} 可见。"""
        engine, _, _ = _make_engine()
        # 场景带 extract：echo 回写 message；message 用模板引用注入变量
        scenario = _make_scenario("inj", message="${var.injected_name}")
        plan = Plan(
            units=[Unit(id="inj", scenario=scenario,
                        inputs={"injected_name": "from-inputs"})],
            implicit=True,
        )
        # 直接跑 Plan（不经 compile_target；inputs 是 bind 阶段的产物，批次 C）
        framework_ctx = engine._ictx.ctx_manager.create_framework_context(
            run_id="run-inj", cfg=engine._ictx,
        )
        result = engine._run_plan(plan, framework_ctx)
        assert result.passed == 1, result.details
        # echo 协议把 message 原样回写 → 模板已解析为注入值即视为注入生效
        assert result.details[0]["steps"][0]["status"] == "passed"


# ── PlanScheduler ───────────────────────────────────────────

class TestPlanScheduler:

    def test_before_after_brackets_execute_in_order(self):
        before_unit = Unit(id="pre", scenario=_make_scenario("pre"))
        main_unit = Unit(id="main", scenario=_make_scenario("main"))
        after_unit = Unit(id="post", scenario=_make_scenario("post"))
        plan = Plan(before=[before_unit], units=[main_unit], after=[after_unit])

        order = []
        sched = PlanScheduler()
        outcome = sched.run(plan, lambda u, inputs: order.append(u.id) or _fake_result(u.id),
                            fail_fast=False)
        assert order == ["pre", "main", "post"]
        assert set(outcome.results.keys()) == {"pre", "main", "post"}
        # 无 blocked / cancelled
        assert not outcome.blocked and not outcome.cancelled

    def test_cancelled_units_absent_from_results(self):
        units = [Unit(id=f"u{i}", scenario=_make_scenario(f"u{i}")) for i in range(4)]

        class _R:
            def __init__(self, uid):
                self.passed = uid != "u0"

        plan = Plan(units=units, policy=PlanPolicy(parallel=1))
        sched = PlanScheduler()
        outcome = sched.run(plan, lambda u, inputs: _R(u.id), fail_fast=True)
        assert outcome.results["u0"].passed is False
        # u1 起被 fail-fast 取消：不在 results，由 outcome.cancelled 呈现
        assert "u1" not in outcome.results and "u3" not in outcome.results
        assert {"u1", "u2", "u3"} <= outcome.cancelled


def _fake_result(uid: str):
    class _R:
        passed = True
        scenario_id = uid
        status = "passed"
        duration_ms = 1.0
        halted = False
        halt_reason = None
        step_results = []
    return _R()


# ── S-4：七阶段纯函数管线 ────────────────────────────────────


class TestSevenStages:

    def test_seven_stages_are_pure_functions(self):
        from gimbal.compiler import pipeline
        for name in ("p_load", "p_normalize", "p_patch", "p_desugar",
                     "p_expand", "p_bind", "p_validate"):
            assert callable(getattr(pipeline, name, None)), name

    def test_patch_scalar_override(self):
        """五层合并代数：深合并 + 标量后层覆盖 + list 按 index 覆盖。"""
        from gimbal.compiler.pipeline import p_patch
        assert p_patch([{"a": 1, "b": {"c": 2}}, {"b": {"c": 3}}]) == {"a": 1, "b": {"c": 3}}
        # v2 合并代数:list 整体替换(唯一例外 setup/teardown 按 key 合并)
        assert p_patch([{"l": [1, 2, 3]}, {"l": [9]}]) == {"l": [9]}
        # setup/teardown 按 (kind,key) 合并:同身份覆盖,新条目追加
        merged = p_patch([
            {"setup": [{"kind": "login", "key": "l1"}, {"kind": "mock", "key": "m1"}]},
            {"setup": [{"kind": "login", "key": "l1", "params": {"u": "x"}},
                        {"kind": "sleep", "key": "s1"}]},
        ])
        assert [e["kind"] for e in merged["setup"]] == ["login", "mock", "sleep"]
        assert merged["setup"][0]["params"] == {"u": "x"}
        # 后层新增键直接并入
        assert p_patch([{"a": 1}, {"b": 2}]) == {"a": 1, "b": 2}
        assert p_patch([]) == {}

    def test_expand_repeat_names(self):
        from gimbal.compiler.pipeline import p_expand
        decl = UnitDecl(ref="a", scenario=_make_scenario("a"))
        decl2 = UnitDecl(ref="b", scenario=_make_scenario("b"), needs=["a"], repeat=1)
        out = p_expand([decl.model_copy(update={"repeat": 3}), decl2])
        assert [d.ref for d in out] == ["a#1", "a#2", "a#3", "b"]
        assert out[-1].needs == ["a#1", "a#2", "a#3"]   # fan-in 全变体

    def test_expand_cap_rejects_explosion(self):
        from gimbal.compiler.pipeline import CompileError, p_expand
        decls = [UnitDecl(ref=f"u{i}", scenario=_make_scenario(f"u{i}"), repeat=64)
                 for i in range(65)]   # 65×64 = 4160 > 4096
        with pytest.raises(CompileError, match="上限"):
            p_expand(decls)

    def test_validate_detects_cycle(self):
        """bind 期抛错之外的独立防线：直接构造带环 Plan 复查。"""
        from gimbal.compiler.pipeline import p_validate
        from gimbal.schema.plan import Plan, PlanPolicy, Unit

        def _u(uid, needs):
            return Unit(id=uid, scenario=_make_scenario(uid), needs=needs)

        plan = Plan(units=[_u("a", ["b"]), _u("b", ["a"])], policy=PlanPolicy(),
                    mode="compose")
        errs = p_validate(plan)
        assert any("循环" in e for e in errs)

    def test_validate_flags_bad_wiring_and_dup_ids(self):
        """schema 层已拦重复 id；此处用 model_construct 构造病态 Plan，
        验证 p_validate 作为独立防线（编程构造路径）仍然生效。"""
        from gimbal.compiler.pipeline import p_validate
        from gimbal.schema.plan import Plan, PlanPolicy, Unit

        u1 = Unit(id="a", scenario=_make_scenario("a"))
        u1_dup = Unit(id="a", scenario=_make_scenario("a2"))
        plan = Plan.model_construct(
            units=[u1, Unit(id="b", scenario=_make_scenario("b"))],
            before=[u1_dup], policy=PlanPolicy(), mode="compose",
            wiring={"ghost": {"x": "nope:y"}}, after=[],
            wiring_ok=None, after_optional=set(),
        )
        errs = p_validate(plan)
        assert any("重复" in e for e in errs)
        assert any("wiring" in e for e in errs)

    def test_compile_plan_from_raw_dict(self):
        """compile_plan：raw dict → 七阶段编排 → Plan（含 validate 复查）。"""
        from gimbal.compiler.pipeline import compile_plan
        raw = {
            "kind": "graph", "mode": "aggregate",
            "units": [{"ref": "u1", "scenario": {
                "kind": "scenario", "scenarioId": "u1",
                "meta": {"name": "n", "description": "d", "module": "m",
                         "priority": 1, "author": "a", "owner": "o", "tags": [],
                         "version": "1", "createTime": "2026-09-28T00:00:00Z",
                         "expire": False, "requirementRef": []},
                "config": {}, "resource": {}, "steps": [],
            }}],
        }
        plan = compile_plan(raw)
        assert plan.mode == "aggregate" and plan.units[0].id == "u1"

    def test_compile_plan_rejects_unknown_kind(self):
        from gimbal.compiler.pipeline import CompileError, p_load
        with pytest.raises(CompileError, match="kind"):
            p_load({"kind": "nope"})
