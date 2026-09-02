# tests/plate/test_io_declarations_p2.py
"""P2:存储翻转 —— 桥编译、派生等价、结构守卫(spec §4/§5)。"""
import pytest

from gimbal_plate.schema.endpoint.io_spec import (
    CarryEntry, DeclarationEntry, IOFieldBinding, RequestSpec, ResponseSpec,
)


class TestBridge:
    def test_request_bridge_equivalence(self) -> None:
        legacy = RequestSpec(
            body_type="json", schema_={},
            fields=[IOFieldBinding(name="order_id", path="$.order_id")],
            carry={"$.remark": CarryEntry(description="备注")},
        )
        canonical = RequestSpec(
            body_type="json", schema_={},
            declarations=[
                DeclarationEntry(name="order_id", path="$.order_id",
                                 channel="binding"),
                DeclarationEntry(name="remark", path="$.remark",
                                 channel="carry", type="string",
                                 description="备注"),
            ],
        )
        assert legacy.fields == canonical.fields
        assert legacy.carry == canonical.carry
        assert legacy.declarations == canonical.declarations  # 键序:binding 前 carry 后

    def test_response_bridge_assertable(self) -> None:
        legacy = ResponseSpec(
            status=200, schema_={},
            fields=[IOFieldBinding(name="total", path="$.data.total")],
            assertable_fields=["$.data.total"],
        )
        (d,) = legacy.declarations
        assert d.channel == "view_only" and d.assertable is True

    def test_mutual_exclusion(self) -> None:
        with pytest.raises(ValueError, match="二选一"):
            RequestSpec(body_type="json", schema_={},
                        fields=[IOFieldBinding(name="x", path="$.x")],
                        declarations=[DeclarationEntry(name="x", path="$.x",
                                                       channel="binding")])

    def test_seventeen_endpoint_files_untouched_shape(self) -> None:
        # 桥承接:全部 ALL_ENDPOINTS 仍可构造且派生形状不变(细锁在 Task 9 ②)
        from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS
        for ep in ALL_ENDPOINTS:
            if ep.request:
                assert isinstance(ep.request.fields, list)


class TestStructuralGuards:
    def test_duplicate_path_cross_channel(self) -> None:
        with pytest.raises(ValueError, match="重复"):
            RequestSpec(body_type="json", schema_={}, declarations=[
                DeclarationEntry(name="x", path="$.x", channel="binding"),
                DeclarationEntry(name="x", path="$.x", channel="carry",
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


class TestDerived:
    def test_derived_returns_fresh_snapshots(self) -> None:
        rs = RequestSpec(body_type="json", schema_={},
                         declarations=[DeclarationEntry(name="x", path="$.x",
                                                        channel="binding")])
        rs.fields[0].name = "mutated"  # type: ignore[index]
        assert rs.fields[0].name == "x"  # 派生每次新建,改快照不回流
