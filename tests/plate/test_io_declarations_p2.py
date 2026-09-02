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
            RequestSpec(body_type="json", schema_={}, declarations=[
                DeclarationEntry(name="x", path="$.x", channel="binding"),
                DeclarationEntry(name="x", path="$.x", channel="carry",
                                 type="string"),
            ])

    def test_duplicate_path_after_normalization(self) -> None:
        # 短名在条目级先归一为 $.x,再进 spec 级判重 —— 归一后重复同样拒
        with pytest.raises(ValueError, match="重复"):
            RequestSpec(body_type="json", schema_={}, declarations=[
                DeclarationEntry(name="x", path="$.x", channel="binding"),
                DeclarationEntry(name="x", path="x", channel="carry",
                                 type="string"),
            ])

    def test_b7_channel_closure(self) -> None:
        with pytest.raises(ValueError, match="view_only"):
            RequestSpec(body_type="json", schema_={}, declarations=[
                DeclarationEntry(name="x", path="$.x", channel="view_only")])
        with pytest.raises(ValueError, match="binding"):
            ResponseSpec(status=200, schema_={}, declarations=[
                DeclarationEntry(name="x", path="$.x", channel="binding")])
        with pytest.raises(ValueError, match="carry"):
            ResponseSpec(status=200, schema_={}, declarations=[
                DeclarationEntry(name="x", path="$.x", channel="carry",
                                 type="string")])

    def test_b4_body_type_none(self) -> None:
        with pytest.raises(ValueError, match="none"):
            RequestSpec(body_type="none", declarations=[
                DeclarationEntry(name="x", path="$.x", channel="binding")])


class TestAssertableSemantics:
    """⑥(spec §8):assertable 缺省 False;wire 投影按条目旗标原样输出。"""

    def test_default_is_false(self) -> None:
        resp = ResponseSpec(status=200, schema_={},
                            declarations=[DeclarationEntry(
                                name="code", path="$.code",
                                channel="view_only")])
        assert resp.declarations[0].assertable is False  # B3:缺省 False

    def test_wire_keeps_entry_flags(self) -> None:
        resp = ResponseSpec(status=200, schema_={},
                            declarations=[
                                DeclarationEntry(name="code", path="$.code",
                                                 channel="view_only",
                                                 assertable=True),
                                DeclarationEntry(name="msg", path="$.msg",
                                                 channel="view_only"),
                            ])
        dump = resp.model_dump(mode="json")
        assert [e["assertable"] for e in dump["declarations"]] == [True, False]
