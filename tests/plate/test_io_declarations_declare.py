# tests/plate/test_io_declarations_declare.py
"""declare() 展开规则与表达力边界(spec §3.4)。"""
import pytest
from pydantic import BaseModel as PdBModel

from gimbal_plate.schema.endpoint.io_spec import RequestSpec, ResponseSpec


class CreateOrderRequest(PdBModel):
    order_id: str
    amount: int = 100
    currency: str = "CNY"
    remark: str = ""


class TestDeclare:
    def test_bindings_absorption(self) -> None:
        rs = RequestSpec.declare(
            CreateOrderRequest,
            bindings={"order_id": None, "amount": {"ui_kind": "number"}},
        )
        by = {e.path: e for e in rs.declarations}
        assert by["$.order_id"].required is True
        assert by["$.amount"].ui_kind == "number"      # 覆写优先
        assert by["$.amount"].default == 100            # 节点吸收
        assert all(e.channel == "binding" for e in rs.declarations)
        assert "remark" not in {e.path.strip("$.") for e in rs.declarations}  # Type C
        assert rs.schema_ == CreateOrderRequest.model_json_schema()  # 伴随原样

    def test_carry_absorbs_type_skips_default(self) -> None:
        rs = RequestSpec.declare(CreateOrderRequest, carry=["remark"])
        (e,) = rs.declarations
        assert e.channel == "carry" and e.type == "string"
        assert e.default is None        # B6:跳过 default 吸收
        assert e.example is None        # example 从不在吸收清单

    def test_carry_requires_explicit_type_when_nodeless(self) -> None:
        with pytest.raises(ValueError, match="carry.*type"):
            RequestSpec.declare({}, carry=["remark"])  # 空 schema 无节点

    def test_boundary_nested_key_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"\.| \["):
            RequestSpec.declare(CreateOrderRequest,
                                bindings={"a.b": None})
        with pytest.raises(ValueError):
            RequestSpec.declare(CreateOrderRequest, bindings={"a[0]": None})

    def test_boundary_unknown_binding_key(self) -> None:
        with pytest.raises(ValueError, match="schema.properties"):
            RequestSpec.declare(CreateOrderRequest, bindings={"nope": None})

    def test_response_declare_assert_paths(self) -> None:
        class Resp(PdBModel):
            code: int
            msg: str

        resp = ResponseSpec.declare(Resp, view_only=["code"],
                                    assert_paths=["$.code"])
        by = {e.path: e for e in resp.declarations}
        assert by["$.code"].assertable is True
        assert by["$.code"].channel == "view_only"
