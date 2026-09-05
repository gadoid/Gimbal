# tests/plate/test_io_declarations_p1.py
"""declarations 形状(2026-09-05 目录化:state 轴 + wire 同形)。

P2 存储翻转后访问面为 .declarations 属性(存储即声明,wire 同形);
channel 键已退役,面划分读 entry.state。
"""
from gimbal_plate.schema.endpoint.io_spec import (
    DeclarationEntry, RequestSpec, ResponseSpec,
)
from gimbal_plate.systems.fin.endpoint import (
    ALL_ENDPOINTS, SETTLEMENT_CREATE_ORDER, ACCOUNT_QUERY_BALANCE,
)


class TestDeclarationsShape:
    def test_request_states_and_order(self) -> None:
        rs = RequestSpec(
            body_type="json",
            declarations=[
                DeclarationEntry(name="remark", path="$.remark", type='string'),
                DeclarationEntry(name="notes", path="$.notes", state='carry',
                                 type="string", description="备注"),
            ],
        )
        dv = [e.model_dump() for e in rs.declarations]
        # 列表序即声明序(不再有桥的"binding 前 carry 后"重排)
        assert [e["state"] for e in dv] == ["form", "carry"]
        assert all("channel" not in e for e in dv)          # channel 键退役
        (carry,) = [e for e in dv if e["state"] == "carry"]
        assert carry["type"] == "string" and carry["description"] == "备注"
        assert all(e["assertable"] is False for e in dv)  # 请求侧恒 False

    def test_response_assertable_flags(self) -> None:
        resp = ResponseSpec(
            status=200,
            declarations=[
                DeclarationEntry(name="audit_id",
                                 path="$.data.data[0].audit_id", type='string'),
                DeclarationEntry(name="total", path="$.data.total", type='string',
                                 assertable=True),
            ],
        )
        dv = [e.model_dump() for e in resp.declarations]
        by_path = {e["path"]: e for e in dv}
        assert by_path["$.data.total"]["assertable"] is True
        assert by_path["$.data.data[0].audit_id"]["assertable"] is False

    def test_root_path_entry(self) -> None:
        # 根路径现网实例已随 2026-09-02 语料重构移除;合成用例锁合法形态:
        # 根路径 last_segment 为 None → name 惯例落 "$"(spec §3.1)
        rs = RequestSpec(
            body_type="json",
            declarations=[DeclarationEntry(name="$", path="$",
                                           state='carry', type="object")],
        )
        (e,) = rs.declarations
        assert e.name == "$" and e.path == "$" and e.state == "carry"

    def test_coverage_1175(self) -> None:
        # 意识性 re-baseline(2026-09-05 目录化):
        # 901(09-03 口径)→ 深实例缩并(9 条折叠进 children)+ audit_page
        # 落地 + confirm/book 端点 = 1175(顶层条目口径,children 树内
        # 条目另计,见 test_coverage_with_children)。
        total = 0
        for ep in ALL_ENDPOINTS:
            if ep.request:
                total += len(ep.request.declarations)
            total += sum(len(r.declarations)
                         for r in ep.responses.values())
        assert total == 1175, f"declarations 覆盖 {total} != 1175"

    def test_serialize_wire_shape(self) -> None:
        # P2 后 wire 恒发 declarations(空声明即空表,不再按键省略)
        rs = RequestSpec(body_type="json")
        assert rs.model_dump(mode="json")["declarations"] == []
        # account:零请求声明端点,full 视图不含 declarations(⑨ 的前置事实)
        full = ACCOUNT_QUERY_BALANCE.request
        assert full is None or not full.declarations

    def test_settlement_carry_entry_shape(self) -> None:
        dv = [e.model_dump() for e in SETTLEMENT_CREATE_ORDER.request.declarations]
        remark = next(e for e in dv if e["path"] == "$.remark")
        assert remark["state"] == "carry"
        assert remark["description"] == "订单备注(carry 传递字段)"
        assert remark["default"] is None and remark["example"] is None
