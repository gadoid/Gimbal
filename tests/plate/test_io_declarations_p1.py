# tests/plate/test_io_declarations_p1.py
"""declarations 形状(spec §3.1、§4.3 键序)。

P2 存储翻转后访问面为 .declarations 属性(存储即声明,wire 同形)。
"""
from gimbal_plate.schema.endpoint.io_spec import (
    DeclarationEntry, RequestSpec, ResponseSpec,
)
from gimbal_plate.systems.fin.endpoint import (
    ALL_ENDPOINTS, SETTLEMENT_CREATE_ORDER, ACCOUNT_QUERY_BALANCE,
)


class TestDeclarationsShape:
    def test_request_channels_and_order(self) -> None:
        rs = RequestSpec(
            body_type="json", schema_={},
            declarations=[
                DeclarationEntry(name="remark", path="$.remark",
                                 channel="binding"),
                DeclarationEntry(name="notes", path="$.notes", channel="carry",
                                 type="string", description="备注"),
            ],
        )
        dv = [e.model_dump() for e in rs.declarations]
        # 列表序即声明序(不再有桥的"binding 前 carry 后"重排)
        assert [e["channel"] for e in dv] == ["binding", "carry"]
        (carry,) = [e for e in dv if e["channel"] == "carry"]
        assert carry["type"] == "string" and carry["description"] == "备注"
        assert all(e["assertable"] is False for e in dv)  # 请求侧恒 False

    def test_response_assertable_flags(self) -> None:
        resp = ResponseSpec(
            status=200, schema_={},
            declarations=[
                DeclarationEntry(name="audit_id",
                                 path="$.data.data[0].audit_id",
                                 channel="view_only"),
                DeclarationEntry(name="total", path="$.data.total",
                                 channel="view_only", assertable=True),
            ],
        )
        dv = [e.model_dump() for e in resp.declarations]
        assert all(e["channel"] == "view_only" for e in dv)
        by_path = {e["path"]: e for e in dv}
        assert by_path["$.data.total"]["assertable"] is True
        assert by_path["$.data.data[0].audit_id"]["assertable"] is False

    def test_root_path_entry(self) -> None:
        # 根路径现网实例已随 2026-09-02 语料重构移除;合成用例锁合法形态:
        # 根路径 last_segment 为 None → name 惯例落 "$"(spec §3.1)
        rs = RequestSpec(
            body_type="json", schema_={},
            declarations=[DeclarationEntry(name="$", path="$",
                                           channel="carry", type="object")],
        )
        (e,) = rs.declarations
        assert e.name == "$" and e.path == "$" and e.channel == "carry"

    def test_coverage_901(self) -> None:
        # 意识性 re-baseline(2026-09-03):order_dispatch 落地(+234,241 请求 + 响应)
        total = 0
        for ep in ALL_ENDPOINTS:
            if ep.request:
                total += len(ep.request.declarations)
            total += sum(len(r.declarations)
                         for r in ep.responses.values())
        assert total == 901, f"declarations 覆盖 {total} != 901"

    def test_serialize_wire_shape(self) -> None:
        # P2 后 wire 恒发 declarations(空声明即空表,不再按键省略)
        rs = RequestSpec(body_type="json", schema_={})
        assert rs.model_dump(mode="json")["declarations"] == []
        # account:零声明端点,full 视图不含 declarations(⑨ 的前置事实)
        full = ACCOUNT_QUERY_BALANCE.request
        assert full is None or not full.declarations

    def test_settlement_carry_entry_shape(self) -> None:
        dv = [e.model_dump() for e in SETTLEMENT_CREATE_ORDER.request.declarations]
        remark = next(e for e in dv if e["path"] == "$.remark")
        assert remark["channel"] == "carry"
        assert remark["description"] == "备注(随请求传递,不进表单)"
        assert remark["default"] is None and remark["example"] is None  # B6 形状
