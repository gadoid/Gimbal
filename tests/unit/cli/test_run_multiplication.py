"""N4：CLI 乘法参数入口（--n-runs/--retry/--parallel → 目标形态变换）。

P2-05（乘法下沉）的前置：平台经 launcher 传参即可让执行器执行乘法，
自身不再循环 nRuns。Engine 级乘法语义（attempts 计数/事件标签）已由
tests/unit/observability 覆盖；此处钉 CLI 变换面。
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.cli.commands.run_launch import apply_multiplication
from gimbal.schema.call import Call
from gimbal.schema.plan import PlanPolicy
from gimbal.schema.scenario import Config as SC, Meta, Scenario, SuiteGraph, UnitDecl
from gimbal.schema.step import Step


def _scenario(sid: str = "sc-n4") -> Scenario:
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=sid, description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=SC(), resource={},
        steps=[Step(call=Call(protocol="http", service="s",
                              method="GET", path="/x"), strategy=[])],
    )


class TestApplyMultiplication:

    def test_defaults_passthrough(self):
        sc = _scenario()
        assert apply_multiplication(sc) is sc

    def test_scenario_wraps_graph_with_policy(self):
        out = apply_multiplication(_scenario(), n_runs=3, retry=1)
        assert isinstance(out, SuiteGraph) and out.mode == "aggregate"
        assert len(out.units) == 1
        assert out.units[0].policy_kwargs == {"n_runs": 3, "retry": 1}

    def test_graph_unit_policy_overrides(self):
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="a", scenario=_scenario("a")),
                   UnitDecl(ref="b", scenario=_scenario("b"),
                            policy_kwargs={"retry": 2})])
        out = apply_multiplication(graph, n_runs=2)
        assert [u.policy_kwargs for u in out.units] == [
            {"n_runs": 2}, {"retry": 2, "n_runs": 2}]
        # 原对象不被改写
        assert graph.units[0].policy_kwargs == {}

    def test_graph_parallel_override(self):
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="a", scenario=_scenario("a"))],
            policy=PlanPolicy(parallel=2, fail_fast=True))
        out = apply_multiplication(graph, parallel=8)
        assert out.policy.parallel == 8 and out.policy.fail_fast is True

    def test_scenario_ignores_parallel(self):
        sc = _scenario()
        out = apply_multiplication(sc, parallel=4)
        assert out is sc    # 单单元无并发面,原样返回

    def test_compiled_plan_carries_multiplication(self):
        """变换产物经 compile_target 落到 UnitPolicy（端到端链）。"""
        from gimbal.compiler.pipeline import compile_target
        out = apply_multiplication(_scenario(), n_runs=2, retry=1)
        plan = compile_target(out)
        assert plan.units[0].policy.n_runs == 2
        assert plan.units[0].policy.retry == 1
        assert plan.implicit is False
