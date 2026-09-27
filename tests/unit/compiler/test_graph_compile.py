"""批次 C 编排编译测试：四模式 desugar / shared 塌缩 / control / bind 连线。"""
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.compiler.errors import CompileError
from gimbal.compiler.pipeline import compile_target
from gimbal.schema.call import Call
from gimbal.schema.plan import Plan
from gimbal.schema.scenario import (
    Config as ScenarioConfig, Control, Meta, Scenario, SuiteGraph, UnitDecl,
)
from gimbal.schema.step import Step


def _scenario(sid: str, message: str = None, extract_to: str = None, vars=None) -> Scenario:
    strategy = []
    if extract_to:
        strategy.append({"kind": "extract", "name": "o",
                         "expression": "$.call.response.body.echo",
                         "target": extract_to, "scope": "scenario"})
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


def _producer(ref: str, out: str = "order_id", message: str = "v1") -> UnitDecl:
    """产出单元：echo + SCENARIO 提取。"""
    return UnitDecl(ref=ref, scenario=_scenario(ref, message=message, extract_to=out))


def _consumer(ref: str, var: str = "order_id", needs=None, **kw) -> UnitDecl:
    """消费单元：模板引用上游输出。"""
    return UnitDecl(ref=ref, scenario=_scenario(ref, message=f"${{var.{var}}}"),
                    needs=needs or [], **kw)


class TestModes:

    def test_compose_dag_with_binding(self):
        """compose：needs DAG + 按名连线。"""
        graph = SuiteGraph(
            mode="compose",
            units=[_producer("p"), _consumer("c", needs=["p"])],
        )
        plan = compile_target(graph)
        assert plan.mode == "compose"
        by_id = {u.id: u for u in plan.units}
        assert by_id["c"].needs == ["p"]
        assert plan.wiring == {"c": {"order_id": "p:order_id"}}

    def test_chain_linear_and_slice(self):
        """chain：顺序即依赖；from_node 切片后输入不满足要显式提供。"""
        graph = SuiteGraph(
            mode="chain",
            units=[_producer("a", out="tok", message="t0"),
                   _consumer("b", var="tok"),
                   _consumer("c", var="tok")],
        )
        plan = compile_target(graph)
        needs = {u.id: u.needs for u in plan.units}
        assert needs == {"a": [], "b": ["a"], "c": ["b"]}

        # 切片 b..c：a 被跳过 → b 的 tok 无上游 → CompileError 提示 --var
        graph2 = SuiteGraph(
            mode="chain",
            control=Control(from_node="b"),
            units=[_producer("a", out="tok", message="t0"),
                   _consumer("b", var="tok"), _consumer("c", var="tok")],
        )
        with pytest.raises(CompileError, match=r"--var|inputs"):
            compile_target(graph2)

        # 切片 + 字面量注入补齐 → 通过（b、c 各自的字面量补齐被跳过的上游输出）
        graph3 = SuiteGraph(
            mode="chain",
            control=Control(from_node="b"),
            units=[_producer("a", out="tok", message="t0"),
                   UnitDecl(ref="b", scenario=_scenario("b", message="${var.tok}"),
                            inputs={"tok": "injected"}),
                   _consumer("c", var="tok", inputs={"tok": "injected2"})],
        )
        plan3 = compile_target(graph3)
        assert [u.id for u in plan3.units] == ["b", "c"]

    def test_fanout_single_source(self):
        graph = SuiteGraph(
            mode="fanout",
            units=[_producer("src", out="tok"), _consumer("s1", var="tok"),
                   _consumer("s2", var="tok")],
        )
        plan = compile_target(graph)
        needs = {u.id: u.needs for u in plan.units}
        assert needs == {"src": [], "s1": ["src"], "s2": ["src"]}
        assert plan.wiring["s1"] == {"tok": "src:tok"}

    def test_aggregate_rejects_needs(self):
        with pytest.raises(CompileError, match="aggregate"):
            compile_target(SuiteGraph(mode="aggregate",
                                      units=[_consumer("c", needs=["p"]), _producer("p")]))


class TestSharedAndControl:

    def test_shared_collapse_with_remap(self):
        """同 key 同定义 → 塌缩为一份；needs 重映射。"""
        shared_scenario = _scenario("login", message="cred", extract_to="token")
        graph = SuiteGraph(
            mode="compose",
            units=[
                UnitDecl(ref="login_a", scenario=shared_scenario, shared="login"),
                UnitDecl(ref="login_b", scenario=shared_scenario.model_copy(deep=True),
                         shared="login"),
                UnitDecl(ref="use1", scenario=_scenario("u1", message="${var.token}"),
                         needs=["login_a"]),
                UnitDecl(ref="use2", scenario=_scenario("u2", message="${var.token}"),
                         needs=["login_b"]),
            ],
        )
        plan = compile_target(graph)
        ids = [u.id for u in plan.units]
        assert "login_b" not in ids          # 塌缩掉
        assert "login_a" in ids
        by_id = {u.id: u for u in plan.units}
        assert by_id["use2"].needs == ["login_a"]   # 重映射
        assert plan.wiring["use2"] == {"token": "login_a:token"}

    def test_shared_inconsistent_definition_rejected(self):
        s1 = _scenario("x", message="a", extract_to="t")
        s2 = _scenario("y", message="b", extract_to="t")
        with pytest.raises(CompileError, match="生效定义不一致"):
            compile_target(SuiteGraph(mode="compose", units=[
                UnitDecl(ref="a", scenario=s1, shared="k"),
                UnitDecl(ref="b", scenario=s2, shared="k"),
            ]))

    def test_control_only_closure(self):
        """only = 目标 + 传递依赖闭包；闭包外整体排除。"""
        graph = SuiteGraph(
            mode="chain",
            control=Control(only=["b"]),
            units=[_producer("a", out="tok", message="t0"),
                   _consumer("b", var="tok"), _consumer("c", var="tok")],
        )
        plan = compile_target(graph)
        assert [u.id for u in plan.units] == ["a", "b"]   # b 的闭包含 a，c 排除

    def test_control_only_unknown_ref(self):
        with pytest.raises(CompileError, match="不存在的 ref"):
            compile_target(SuiteGraph(mode="compose", control=Control(only=["nope"]),
                                      units=[_producer("p")]))


class TestBind:

    def test_unsatisfied_input_rejected(self):
        with pytest.raises(CompileError, match="输入不满足"):
            compile_target(SuiteGraph(mode="compose", units=[_consumer("orphan")]))

    def test_ambiguous_input_requires_map(self):
        """两个上游都产 order_id → 同名冲突；map 改名消解。"""
        with pytest.raises(CompileError, match="map 改名"):
            compile_target(SuiteGraph(mode="compose", units=[
                _producer("p1", out="order_id"), _producer("p2", out="order_id"),
                UnitDecl(ref="c", scenario=_scenario("c", message="${var.order_id}"),
                         needs=["p1", "p2"]),
            ]))

    def test_map_rename_resolves_ambiguity(self):
        """consumer.map 把 p2 的输出改名 → 无歧义。"""
        graph = SuiteGraph(mode="compose", units=[
            _producer("p1", out="order_id", message="v1"),
            _producer("p2", out="order_id", message="v2"),
            UnitDecl(ref="c",
                     scenario=_scenario("c", message="${var.primary}"),
                     needs=["p1", "p2"],
                     map={"order_id": "primary"}),   # p1/p2 的 order_id 都呈现为 primary？
        ])
        # 两个上游经同一 map 都呈现 primary → 仍歧义；map 只应对单上游改名。
        with pytest.raises(CompileError):
            compile_target(graph)

    def test_map_rename_single_upstream(self):
        graph = SuiteGraph(mode="compose", units=[
            _producer("p", out="order_id", message="v1"),
            UnitDecl(ref="c", scenario=_scenario("c", message="${var.primary}"),
                     needs=["p"], map={"order_id": "primary"}),
        ])
        plan = compile_target(graph)
        assert plan.wiring["c"] == {"primary": "p:order_id"}

    def test_cycle_rejected(self):
        with pytest.raises(CompileError, match="循环"):
            compile_target(SuiteGraph(mode="compose", units=[
                UnitDecl(ref="a", scenario=_scenario("a", message="${var.t}"),
                         needs=["b"]),
                UnitDecl(ref="b", scenario=_scenario("b", message="x"),
                         needs=["a"]),
            ]))

    def test_needs_unknown_ref_rejected(self):
        with pytest.raises(CompileError, match="不存在的 ref"):
            compile_target(SuiteGraph(mode="compose", units=[
                _consumer("c", needs=["ghost"]),
            ]))

    def test_before_outputs_feed_units(self):
        """before 括号单元的输出可被主体消费（全局前置最高频用法）。"""
        graph = SuiteGraph(
            mode="aggregate",
            before=[_producer("login", out="token", message="cred")],
            units=[UnitDecl(ref="u1", scenario=_scenario("u1", message="${var.token}"))],
        )
        plan = compile_target(graph)
        assert plan.wiring["u1"] == {"token": "login:token"}

    def test_brackets_reject_needs(self):
        with pytest.raises(CompileError, match="不允许声明 needs"):
            compile_target(SuiteGraph(mode="compose",
                                      before=[UnitDecl(ref="b0", scenario=_scenario("b0"),
                                                       needs=["x"])],
                                      units=[_producer("p")]))
