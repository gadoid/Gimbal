"""批次 C 静态分析测试：三形态输入面 + 输出面（总案风险 #1 的正面验收）。

三形态（与运行期取值通道一一对应，见 compiler/analysis.py docstring）：
  1. ``${var.x}`` / 裸 ``${x}`` 模板
  2. ``$.x`` JSONPath（Assign source，STEP 作用域回退 SCENARIO 层）
  3. 裸名（Assign source ``${x}`` STEP 作用域先 scratch 后 scenario）
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.compiler.analysis import analyze_scenario
from gimbal.schema.call import Call
from gimbal.schema.scenario import Config as ScenarioConfig, Meta, Scenario
from gimbal.schema.step import Step


def _scenario(steps, vars=None) -> Scenario:
    return Scenario(
        scenarioId="sc-a",
        meta=Meta(name="t", description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(vars=vars or {}),
        resource={},
        steps=steps,
    )


class TestThreeForms:

    def test_form1_var_template(self):
        """形态 1：${var.x} 模板引用 → 输入 x。"""
        sc = _scenario([Step(
            call=Call(protocol="echo", message="${var.order_id}"), strategy=[])])
        a = analyze_scenario(sc)
        assert "order_id" in a.var_refs
        assert "order_id" in a.inputs

    def test_form1_bare_template(self):
        """形态 1（裸）：${x} → 输入 x。"""
        sc = _scenario([Step(
            call=Call(protocol="echo", message="prefix-${token}-suffix"), strategy=[])])
        a = analyze_scenario(sc)
        assert "token" in a.var_refs and "token" in a.inputs

    def test_form1_non_var_namespaces_excluded(self):
        """service./auth. 前缀不是 scenario 变量，不进输入面。"""
        sc = _scenario([Step(
            call=Call(protocol="http", service="${service.fin}", method="GET",
                      path="/x", headers={"Authorization": "${auth.admin.token}"}),
            strategy=[])])
        a = analyze_scenario(sc)
        assert a.inputs == set(), f"不应有输入，得到 {a.inputs}"

    def test_form2_jsonpath_source(self):
        """形态 2：Assign source $.x（STEP 作用域回退 SCENARIO 层）→ 输入 x。"""
        sc = _scenario([Step(
            call=Call(protocol="echo", message="x"),
            strategy=[{"kind": "assign", "name": "a", "source": "$.upstream_key",
                       "target": "local_x"}])])
        a = analyze_scenario(sc)
        assert "upstream_key" in a.jsonpath_refs
        assert "upstream_key" in a.inputs

    def test_form2_internal_scratch_prefix_not_input(self):
        """形态 2 的内部面：协议调用产出的 scratch 前缀不算外部输入。"""
        sc = _scenario([Step(
            call=Call(protocol="echo", message="x"),
            strategy=[{"kind": "assign", "name": "a", "source": "$.response_body.code",
                       "target": "c"}])])
        a = analyze_scenario(sc)
        assert "response_body" not in a.inputs

    def test_form3_bare_name_scratch(self):
        """形态 3：Assign source ${x}（STEP 作用域先 scratch 后 scenario）→ 输入 x。"""
        sc = _scenario([Step(
            call=Call(protocol="echo", message="x"),
            strategy=[{"kind": "assign", "name": "a", "source": "${shared_token}",
                       "target": "t"}])])
        a = analyze_scenario(sc)
        assert "shared_token" in a.inputs


class TestOutputsAndDefaults:

    def test_outputs_from_scenario_scope_extract(self):
        """输出面 = scenario 作用域 extract 目标（STEP 作用域不算）。"""
        sc = _scenario([Step(
            call=Call(protocol="echo", message="x"),
            strategy=[
                {"kind": "extract", "name": "o1", "expression": "$.call.response.body.echo",
                 "target": "order_id", "scope": "scenario"},
                {"kind": "extract", "name": "o2", "expression": "$.response_status",
                 "target": "tmp", "scope": "step"},
            ])])
        a = analyze_scenario(sc)
        assert a.outputs == {"order_id"}

    def test_internal_output_not_input(self):
        """自己产出的变量不算自己的输入（自给自足）。"""
        sc = _scenario([Step(
            call=Call(protocol="echo", message="${var.order_id}"),
            strategy=[{"kind": "extract", "name": "o", "expression": "$.call.response.body.echo",
                       "target": "order_id", "scope": "scenario"}])])
        a = analyze_scenario(sc)
        assert "order_id" in a.outputs
        assert "order_id" not in a.inputs

    def test_config_vars_default_makes_optional(self):
        """config.vars 有默认值 → 可选输入（不进必选）。"""
        sc = _scenario(
            [Step(call=Call(protocol="echo", message="${var.maybe}"), strategy=[])],
            vars={"maybe": "default"},
        )
        a = analyze_scenario(sc)
        assert "maybe" in a.optional_inputs
        assert "maybe" not in a.inputs
