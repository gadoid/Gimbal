# tests/plate/test_io_declarations_p2.py
"""结构守卫(spec §4/§5)。

桥(fields/carry/assertable_fields 入参)与派生投影已随 P2 存储翻转
退役;本文件只锁仍存续的校验:path 唯一、B7 通道闭合、B4 none 即零声明。
"""
import pytest

from gimbal_plate.schema.endpoint.io_spec import (
    DeclarationEntry, RequestSpec, ResponseSpec,
)


def test_all_endpoints_declarations_are_lists() -> None:
    # 全部 ALL_ENDPOINTS 可构造且 declarations 形状不变(细锁在 golden)
    from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS
    for ep in ALL_ENDPOINTS:
        if ep.request:
            assert isinstance(ep.request.declarations, list)


class TestStructuralGuards:
    def test_duplicate_path_cross_channel(self) -> None:
        with pytest.raises(ValueError, match="重复"):
            RequestSpec(body_type="json", declarations=[
                DeclarationEntry(name="x", path="$.x", type='string'),
                DeclarationEntry(name="x", path="$.x", state='carry',
                                 type="string"),
            ])

    def test_duplicate_path_after_normalization(self) -> None:
        # 短名在条目级先归一为 $.x,再进 spec 级判重 —— 归一后重复同样拒
        with pytest.raises(ValueError, match="重复"):
            RequestSpec(body_type="json", declarations=[
                DeclarationEntry(name="x", path="$.x", type='string'),
                DeclarationEntry(name="x", path="x", state='carry',
                                 type="string"),
            ])

    def test_state_vocab_closure(self) -> None:
        # B7 通道闭合退役(2026-09-05 目录化):请求/响应不再按通道互斥;
        # 继任守卫 = state 三态 Literal 词表闭合(条目级)。
        with pytest.raises(Exception):
            RequestSpec(body_type="json", declarations=[
                DeclarationEntry(name="x", path="$.x", type='string',
                                 state="binding")])  # type: ignore[call-arg]
        # 响应面无视 state:carry 条目合法(共识默认不被读取)
        ResponseSpec(status=200, declarations=[
            DeclarationEntry(name="x", path="$.x", state='carry',
                             type="string")])

    def test_b4_body_type_none(self) -> None:
        with pytest.raises(ValueError, match="none"):
            RequestSpec(body_type="none", declarations=[
                DeclarationEntry(name="x", path="$.x", type='string')])


class TestAssertableSemantics:
    """⑥(spec §8):assertable 缺省 False;wire 投影按条目旗标原样输出。"""

    def test_default_is_false(self) -> None:
        resp = ResponseSpec(status=200, 
                            declarations=[DeclarationEntry(
                                name="code", path="$.code", type='string',
                                )])
        assert resp.declarations[0].assertable is False  # B3:缺省 False

    def test_wire_keeps_entry_flags(self) -> None:
        resp = ResponseSpec(status=200, 
                            declarations=[
                                DeclarationEntry(name="code", path="$.code", type='string',
                                                 
                                                 assertable=True),
                                DeclarationEntry(name="msg", path="$.msg", type='string',
                                                 ),
                            ])
        dump = resp.model_dump(mode="json")
        assert [e["assertable"] for e in dump["declarations"]] == [True, False]
