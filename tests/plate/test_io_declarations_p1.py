# tests/plate/test_io_declarations_p1.py
"""P1:declarations_view 派生视图(spec §3.1 形状、§4.3 键序)。"""
from gimbal_plate.schema.endpoint.io_spec import (
    CarryEntry, IOFieldBinding, RequestSpec, ResponseSpec,
)
from gimbal_plate.systems.fin.endpoint import (
    ALL_ENDPOINTS, SETTLEMENT_CREATE_ORDER, ACCOUNT_QUERY_BALANCE,
)


def _by_channel(entries):
    return [e for e in entries if e["channel"] != "carry"], \
           [e for e in entries if e["channel"] == "carry"]


class TestDeclarationsView:
    def test_request_channels_and_order(self) -> None:
        rs = RequestSpec(
            body_type="json", schema_={},
            fields=[IOFieldBinding(name="remark", path="$.remark")],
            carry={"$.notes": CarryEntry(description="备注", type="string")},
        )
        dv = rs.declarations_view()
        non_carry, carry = _by_channel(dv)
        assert [e["path"] for e in non_carry] == ["$.remark"]
        assert all(e["channel"] == "binding" for e in non_carry)
        assert [e["path"] for e in carry] == ["$.notes"]
        assert carry[0]["type"] == "string" and carry[0]["description"] == "备注"
        assert all(e["assertable"] is False for e in dv)  # 请求侧恒 False

    def test_response_assertable_mapping(self) -> None:
        resp = ResponseSpec(
            status=200, schema_={},
            fields=[IOFieldBinding(name="audit_id", path="$.data.data[0].audit_id"),
                    IOFieldBinding(name="total", path="$.data.total")],
            assertable_fields=["$.data.total"],
        )
        dv = resp.declarations_view()
        assert all(e["channel"] == "view_only" for e in dv)
        by_path = {e["path"]: e for e in dv}
        assert by_path["$.data.total"]["assertable"] is True
        assert by_path["$.data.data[0].audit_id"]["assertable"] is False

    def test_root_path_entry(self) -> None:
        # 根路径现网实例已随 2026-09-02 语料重构移除;合成用例锁派生逻辑:
        # carry 根路径 last_segment 为 None → name 落 "$" 兜底(spec §3.1)
        rs = RequestSpec(
            body_type="json", schema_={},
            carry={"$": CarryEntry(description="整包透传", type="object")},
        )
        (e,) = rs.declarations_view()
        assert e["name"] == "$" and e["path"] == "$" and e["channel"] == "carry"

    def test_coverage_667(self) -> None:
        total = 0
        for ep in ALL_ENDPOINTS:
            if ep.request:
                total += len(ep.request.declarations_view())
            total += sum(len(r.declarations_view())
                         for r in ep.responses.values())
        assert total == 667, f"declarations 覆盖 {total} != 667"

    def test_serialize_emits_only_when_present(self) -> None:
        rs = RequestSpec(body_type="json", schema_={})
        assert "declarations" not in rs.model_dump(mode="json")
        # account:零声明端点,full 视图不含 declarations(⑨ 的前置事实)
        full = ACCOUNT_QUERY_BALANCE.request
        assert full is None or not full.declarations_view()

    def test_settlement_carry_entry_shape(self) -> None:
        dv = SETTLEMENT_CREATE_ORDER.request.declarations_view()
        remark = next(e for e in dv if e["path"] == "$.remark")
        assert remark["channel"] == "carry"
        assert remark["description"] == "备注(随请求传递,不进表单)"
        assert remark["default"] is None and remark["example"] is None  # B6 形状
