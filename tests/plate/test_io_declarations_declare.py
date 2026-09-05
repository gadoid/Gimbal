# tests/plate/test_io_declarations_declare.py
"""declare() 展开规则与表达力边界(2026-09-05 目录化 P7 重写后)。

旧通道参数(bindings/carry/view_only)退役;全量目录吸收 +
states 盖戳 + assert_paths 标记为新三轴。纪律全量用例见
test_field_state_catalog.py,本文件聚焦 declare() 糖本身。
"""
import pytest
from pydantic import BaseModel as PdBModel

from gimbal_plate.schema.endpoint.io_spec import RequestSpec, ResponseSpec


class CreateOrderRequest(PdBModel):
    order_id: str
    amount: int = 100
    currency: str = "CNY"
    remark: str = ""


class TestDeclare:
    def test_full_catalog_absorption(self) -> None:
        # 全量吸收(Type C 死亡):所有 properties 顶层字段都成条目,
        # required 自 schema,default 保留(B6 软化),ui_kind 自 type 推断。
        rs = RequestSpec.declare(CreateOrderRequest)
        by = {e.path: e for e in rs.declarations}
        assert sorted(by) == ["$.amount", "$.currency", "$.order_id", "$.remark"]
        assert by["$.order_id"].required is True
        assert by["$.amount"].required is False and by["$.amount"].default == 100
        assert by["$.amount"].ui_kind == "number"     # int → number 控件
        assert all(e.state == "form" for e in rs.declarations)  # 未列出 = form

    def test_states_stamp_carry(self) -> None:
        rs = RequestSpec.declare(CreateOrderRequest,
                                 states={"remark": "carry"})
        by = {e.path: e for e in rs.declarations}
        assert by["$.remark"].state == "carry"
        assert by["$.remark"].type == "string"
        assert by["$.order_id"].state == "form"       # 盖戳只影响列出者

    def test_states_accepts_normalized_path_key(self) -> None:
        # states 键支持 path 形态(归一化后匹配),短名与 $. 全称等价。
        rs = RequestSpec.declare(CreateOrderRequest,
                                 states={"$.remark": "carry"})
        assert {e.path: e for e in rs.declarations}["$.remark"].state == "carry"

    def test_states_unknown_key_is_silent_noop(self) -> None:
        # 现行为:未命中任何条目的 states 键静默不生效(归一化匹配,
        # 无严格校验)— 钉住语义防误改;typo 防护挂账 M2 校验链。
        rs = RequestSpec.declare(CreateOrderRequest,
                                 states={"nope": "carry"})
        assert all(e.state == "form" for e in rs.declarations)

    def test_type_absorbs_from_optional_anyof(self) -> None:
        # 真实 settlement 形态:`remark: str | None = None` → 节点
        # anyOf[{string},{null}] 无顶层 type;吸收解析 Optional 得 T
        class WithOptional(PdBModel):
            remark: "str | None" = None

        rs = RequestSpec.declare(WithOptional, states={"remark": "carry"})
        (e,) = rs.declarations
        assert e.type == "string" and e.state == "carry"

    def test_node_without_type_rejected(self) -> None:
        # 节点无 type 可吸收即构造错误(目录 type 必备,拒绝静默垃圾条目)
        with pytest.raises(ValueError, match="无 type 可吸收"):
            RequestSpec.declare({"properties": {"x": {}}})

    def test_empty_schema_declares_empty_catalog(self) -> None:
        rs = RequestSpec.declare({})
        assert rs.declarations == []

    def test_response_declare_assert_paths(self) -> None:
        class Resp(PdBModel):
            code: int
            msg: str

        resp = ResponseSpec.declare(Resp, assert_paths=["$.code"])
        by = {e.path: e for e in resp.declarations}
        assert by["$.code"].assertable is True
        assert by["$.msg"].assertable is False
        # 响应面无视 state(条目仍带共识默认 form,但不参与面划分)
        assert by["$.code"].state == "form"
