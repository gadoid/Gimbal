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
from gimbal.compiler.pipeline import compile_target
from gimbal.schema.call import Call
from gimbal.schema.scenario import (
    Config as ScenarioConfig, Meta, Scenario, SuiteGraph, UnitDecl,
)
from gimbal.schema.step import Step


def _scenario(steps, vars=None, sid: str = "sc-a") -> Scenario:
    return Scenario(
        scenarioId=sid,
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

    def test_same_step_use_before_produce_is_input(self):
        """同 step 先引用后产出（P0-7 语义修正，原 test_internal_output_not_input）。

        call message 的 ${var.order_id} 在请求期解析，Extract（after_request）
        晚于调用才产出 order_id —— 引用先于产出，是真实输入；旧断言
        "自己产出不算自己输入" 依赖无序集合差抵消，只对 produce-then-use
        成立（见 TestOrderedDataflow.test_produce_then_use_self_sufficient）。
        """
        sc = _scenario([Step(
            call=Call(protocol="echo", message="${var.order_id}"),
            strategy=[{"kind": "extract", "name": "o", "expression": "$.call.response.body.echo",
                       "target": "order_id", "scope": "scenario"}])])
        a = analyze_scenario(sc)
        assert "order_id" in a.outputs
        assert "order_id" in a.inputs

    def test_config_vars_default_makes_optional(self):
        """config.vars 有默认值 → 可选输入（不进必选）。"""
        sc = _scenario(
            [Step(call=Call(protocol="echo", message="${var.maybe}"), strategy=[])],
            vars={"maybe": "default"},
        )
        a = analyze_scenario(sc)
        assert "maybe" in a.optional_inputs
        assert "maybe" not in a.inputs


def _extract(target: str, scope: str = "scenario") -> dict:
    """SCENARIO 提升提取策略（与既有测试的内联 dict 同构）。"""
    return {"kind": "extract", "name": "o",
            "expression": "$.call.response.body.echo",
            "target": target, "scope": scope}


class TestOrderedDataflow:
    """P0-7：静态分析按 step 序做数据流——引用先于产出即输入，不再被后续产出抵消。

    旧实现 ``required = (引用) - outputs`` 是无序集合差：先引用后产出（同场景
    回写）的名字被晚到的产出吞掉 → 静默错绑（"错了不报错"）。
    """

    def test_use_before_produce_is_input(self):
        """消费者先用 ${orderId}（step1）再提取 orderId（step2）→ orderId 是输入。"""
        sc = _scenario([
            Step(call=Call(protocol="echo", message="need-${orderId}"), strategy=[]),
            Step(call=Call(protocol="echo", message="ok"), strategy=[_extract("orderId")]),
        ])
        a = analyze_scenario(sc)
        assert "orderId" in a.inputs, (
            f"use-before-produce 必须计输入（P0-7），得到 inputs={sorted(a.inputs)}"
        )
        # 产出面不受影响：orderId 同时是对外输出
        assert "orderId" in a.outputs

    def test_produce_then_use_self_sufficient(self):
        """step1 提取 order_id，step2 再用 → 自给自足，不算输入（有序不等于全扣）。"""
        sc = _scenario([
            Step(call=Call(protocol="echo", message="v"),
                 strategy=[_extract("order_id")]),
            Step(call=Call(protocol="echo", message="${var.order_id}"), strategy=[]),
        ])
        a = analyze_scenario(sc)
        assert "order_id" in a.outputs
        assert "order_id" not in a.inputs, (
            f"produce-then-use 不应计输入，得到 inputs={sorted(a.inputs)}"
        )

    def test_late_produce_does_not_cancel_earlier_use_chain_wiring(self):
        """chain e2e：B 先用后产 orderId；A 产 orderId → B 的连线来自 A。

        旧集合差把 B 的 orderId 引用吞掉 → wiring 缺线 → 运行期模板拿不到值。
        """
        producer = _scenario(
            [Step(call=Call(protocol="echo", message="v0"),
                  strategy=[_extract("orderId")])], sid="sc-a")
        consumer = _scenario([
            Step(call=Call(protocol="echo", message="need-${orderId}"), strategy=[]),
            Step(call=Call(protocol="echo", message="ok"),
                 strategy=[_extract("orderId")]),
        ], sid="sc-b")
        graph = SuiteGraph(mode="chain", units=[
            UnitDecl(ref="A", scenario=producer),
            UnitDecl(ref="B", scenario=consumer),
        ])
        plan = compile_target(graph)
        wires = plan.wiring.get("B", {})
        assert any(v.startswith("A:") for v in wires.values()), (
            f"B 应有来自 A 的连线（P0-7），得到 wiring={plan.wiring}"
        )


class TestExactInternalKeys:
    """P1-8：内部键精确匹配——业务变量不被 'call'/'response_' 前缀误吞。"""

    def test_callback_url_not_internal(self):
        """$.callbackUrl 首段 callbackUrl 不因 startswith('call') 被吞。"""
        sc = _scenario([Step(
            call=Call(protocol="echo", message="x"),
            strategy=[{"kind": "assign", "name": "a", "source": "$.callbackUrl",
                       "target": "u"}])])
        a = analyze_scenario(sc)
        assert "callbackUrl" in a.jsonpath_refs, (
            f"callbackUrl 是外部 jsonpath 引用（P1-8），"
            f"得到 jsonpath_refs={sorted(a.jsonpath_refs)}"
        )
        assert "callbackUrl" in a.inputs

    def test_exact_protocol_keys_still_internal(self):
        """精确协议键（$.call… / $.response_body…）仍不算外部输入。"""
        sc = _scenario([Step(
            call=Call(protocol="echo", message="x"),
            strategy=[
                {"kind": "assign", "name": "a", "source": "$.call.response.body",
                 "target": "c"},
                {"kind": "assign", "name": "b", "source": "$.response_body.code",
                 "target": "d"},
            ])])
        a = analyze_scenario(sc)
        assert "call" not in a.inputs
        assert "response_body" not in a.inputs
