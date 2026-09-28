"""N5:mode 表 params_schema 注册(ext list --json 输出面)。

C5(P3-05 suite 编排页)的「参数表单由 schema 生成」前置 —— 定稿 A7
未落地,mode 表 params_schema 恒 None,表单渲染不出内容。本批给四模式
注册参数模型;chain 携带 from_node/to_node,其余三模式无可调参数
(空 schema,表单渲染为空表是正确语义)。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.suite.modes import MODE_REGISTRY


class TestModeParamsSchema:

    def test_all_modes_have_schema(self):
        d = {e["name"]: e for e in MODE_REGISTRY.describe()}
        assert set(d) == {"aggregate", "compose", "fanout", "chain"}
        for name, entry in d.items():
            assert entry["table"] == "mode"
            assert entry["params_schema"] is not None, (
                f"mode {name} 缺 params_schema(C5 编排页表单前置)")

    def test_chain_schema_has_slice_fields(self):
        chain = next(e for e in MODE_REGISTRY.describe()
                     if e["name"] == "chain")
        props = chain["params_schema"]["properties"]
        assert "from_node" in props and "to_node" in props
        # Optional[str] → anyOf[string, null](pydantic v2 形态)
        assert {"type": "string"} in props["from_node"].get("anyOf",
               [props["from_node"]] if "type" in props["from_node"] else [])
        # 可选参数:默认 None,不在 required
        assert chain["params_schema"].get("required", []) == []

    def test_empty_param_modes_render_empty_form(self):
        """aggregate/compose/fanout 无可调参数 → 空 properties(表单空是
        正确语义,不再恒 None 渲染不出)。"""
        for name in ("aggregate", "compose", "fanout"):
            entry = next(e for e in MODE_REGISTRY.describe()
                         if e["name"] == name)
            assert entry["params_schema"]["properties"] == {}

    def test_desugar_functions_unchanged(self):
        """注册 params 不改变 desugar 行为(注册面只是元数据)。"""
        from datetime import datetime, timezone
        from gimbal.compiler.pipeline import compile_target
        from gimbal.schema.call import Call
        from gimbal.schema.scenario import Config as SC, Meta, Scenario, SuiteGraph, UnitDecl
        from gimbal.schema.step import Step

        def _scenario(sid):
            return Scenario(
                scenarioId=sid,
                meta=Meta(name=sid, description="d", module="m", priority=1,
                          author="a", owner="o", tags=[], version="1",
                          createTime=datetime.now(timezone.utc), expire=False,
                          requirementRef=[]),
                config=SC(), resource={},
                steps=[Step(call=Call(protocol="http", service="s",
                                      method="GET", path="/x"), strategy=[])],
            )

        graph = SuiteGraph(
            kind="graph", mode="chain",
            units=[UnitDecl(ref="a", scenario=_scenario("a")),
                   UnitDecl(ref="b", scenario=_scenario("b"))],
        )
        plan = compile_target(graph)
        assert [u.id for u in plan.units] == ["a", "b"]
        assert plan.units[1].needs == ["a"]
