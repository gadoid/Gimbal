"""L1 序列化单元测试(PR-2.0)。

业务承诺:
  * ``EndpointSpec.to_dict()`` 包含全部 L1 字段
  * ``EndpointSpec.from_dict(to_dict(s))`` 字段相等(BaseModel 引用除外)
  * ``FieldBinding.to_dict()`` / ``from_dict()`` 互逆
  * 同 spec 两次 to_dict 字典相等(byte-equal)
  * bindings 顺序无关 byte-equal(本 PR 范围:保留 to_dict 输入顺序)
  * tags 输出已排序
  * 必填字段缺失 → KeyError(严格不容错)
  * 31 个 fin 端点全部 round-trip 不挂

对应设计:PR-2.0 §2.3 + A2 不可变序列化 + D6/D7 role-aware。
"""
from __future__ import annotations

import dataclasses

import pytest
from pydantic import BaseModel, ConfigDict

from Plate.binding import FieldBinding
from Plate.spec import EndpointCategory, EndpointSpec


# ════════════════════════════════════════════════════════════════════════════
# 工具:构造合规 Pydantic 模型
# ════════════════════════════════════════════════════════════════════════════


def _good_model(name: str) -> type[BaseModel]:
    return type(
        name,
        (BaseModel,),
        {
            "model_config": ConfigDict(extra="forbid"),
            "__annotations__": {"x": str},
            "x": "",
        },
    )


# ════════════════════════════════════════════════════════════════════════════
# FieldBinding 序列化
# ════════════════════════════════════════════════════════════════════════════


class TestFieldBindingSerialization:
    def test_to_dict_all_fields(self) -> None:
        """业务需求:to_dict 包含 4 字段(from_path/to_path/required/transform)。"""
        b = FieldBinding(
            from_path=("data", "audit_id"),
            to_path=("audit_id",),
            required=True,
            transform=None,
        )
        d = b.to_dict()
        assert d == {
            "from_path": ["data", "audit_id"],
            "to_path": ["audit_id"],
            "required": True,
            "transform": None,
        }

    def test_to_dict_tuple_to_list(self) -> None:
        """业务需求:tuple 字段 → list(JSON 数组无 tuple 概念)。"""
        b = FieldBinding(from_path=("a",), to_path=("b", "c"))
        d = b.to_dict()
        assert d["from_path"] == ["a"]
        assert d["to_path"] == ["b", "c"]
        assert isinstance(d["from_path"], list)
        assert isinstance(d["to_path"], list)

    def test_round_trip_preserves_fields(self) -> None:
        """业务需求:to_dict → from_dict 互逆。"""
        b = FieldBinding(
            from_path=("data", "audit_id"),
            to_path=("audit_id",),
            required=False,
            transform="int->str",
        )
        b2 = FieldBinding.from_dict(b.to_dict())
        assert b2.from_path == b.from_path
        assert b2.to_path == b.to_path
        assert b2.required == b.required
        assert b2.transform == b.transform

    def test_round_trip_tuple_restored(self) -> None:
        """业务需求:from_dict 后,from_path/to_path 还原为 tuple(非 list)。"""
        b = FieldBinding(from_path=("a", "b"), to_path=("c",))
        b2 = FieldBinding.from_dict(b.to_dict())
        assert isinstance(b2.from_path, tuple)
        assert isinstance(b2.to_path, tuple)

    def test_from_dict_missing_required_raises(self) -> None:
        """业务需求:缺 from_path → KeyError(严格不容错)。"""
        with pytest.raises(KeyError, match="缺失字段"):
            FieldBinding.from_dict({"to_path": ["a"]})  # type: ignore[dict-item]

    def test_from_dict_non_dict_raises(self) -> None:
        """业务需求:非 dict 输入 → TypeError。"""
        with pytest.raises(TypeError, match="期望 dict"):
            FieldBinding.from_dict("not a dict")  # type: ignore[arg-type]

    def test_from_dict_wrong_path_type_raises(self) -> None:
        """业务需求:from_path 不是 list/tuple → TypeError。"""
        with pytest.raises(TypeError, match="必须是 list/tuple"):
            FieldBinding.from_dict({"from_path": "not a list", "to_path": ["a"]})  # type: ignore[dict-item]


# ════════════════════════════════════════════════════════════════════════════
# EndpointSpec 序列化 — 字段覆盖
# ════════════════════════════════════════════════════════════════════════════


class TestEndpointSpecSerializationFields:
    def _spec(self) -> EndpointSpec:
        return EndpointSpec(
            method="GET",
            path="/api/test",
            category=EndpointCategory.QUERY,
            mutates_state=False,
            bindings=(
                FieldBinding(from_path=("data", "x"), to_path=("x",)),
            ),
            request=_good_model("TestReq"),
            responses={200: _good_model("TestResp")},
            summary="hello",
            description="d",
            tags=["zeta", "alpha"],
            auth_required=True,
        )

    def test_to_dict_has_all_l1_fields(self) -> None:
        """业务需求:to_dict 包含 L1 字段(分类 / 依赖边 / 文档元数据)。"""
        d = self._spec().to_dict()
        expected_keys = {
            "method", "path", "category", "mutates_state", "bindings",
            "request_ref", "responses_ref", "default_response_ref",
            "response_data_models_ref", "summary", "description", "tags",
            "auth_required", "response_union_ref",
            "mock_hook_ref", "validate_hook_ref", "build_request_hook_ref",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_category_as_string_value(self) -> None:
        """业务需求:category 序列化为字符串值("query" 而非 "EndpointCategory.QUERY")。"""
        d = self._spec().to_dict()
        assert d["category"] == "query"

    def test_to_dict_tags_sorted(self) -> None:
        """业务需求:tags 序列化前已排序(对应 A2 byte-equal)。"""
        d = self._spec().to_dict()
        assert d["tags"] == ["alpha", "zeta"]

    def test_to_dict_bindings_as_list_of_dicts(self) -> None:
        """业务需求:bindings 序列化为 list[dict](非 list[FieldBinding])。"""
        d = self._spec().to_dict()
        assert isinstance(d["bindings"], list)
        assert len(d["bindings"]) == 1
        assert isinstance(d["bindings"][0], dict)
        assert d["bindings"][0]["from_path"] == ["data", "x"]

    def test_to_dict_responses_keys_are_strings(self) -> None:
        """业务需求:responses_ref key 是 status 字符串(JSON key 必为 str)。"""
        d = self._spec().to_dict()
        assert "200" in d["responses_ref"]

    def test_to_dict_request_ref_contains_module(self) -> None:
        """业务需求:request_ref 包含 module.ClassName(便于 importlib 重建)。"""
        d = self._spec().to_dict()
        assert d["request_ref"] is not None
        assert "." in d["request_ref"]
        assert d["request_ref"].endswith(".TestReq")


# ════════════════════════════════════════════════════════════════════════════
# EndpointSpec 序列化 — round-trip
# ════════════════════════════════════════════════════════════════════════════


class TestEndpointSpecRoundTrip:
    def test_from_dict_restores_simple_fields(self) -> None:
        """业务需求:from_dict 还原 method/path/category/mutates_state。"""
        spec = EndpointSpec(
            method="POST",
            path="/p",
            category=EndpointCategory.BUSINESS,
            mutates_state=True,
        )
        restored = EndpointSpec.from_dict(spec.to_dict())
        assert restored.method == "POST"
        assert restored.path == "/p"
        assert restored.category == EndpointCategory.BUSINESS
        assert restored.mutates_state is True

    def test_from_dict_restores_bindings(self) -> None:
        """业务需求:bindings round-trip 不丢字段。"""
        spec = EndpointSpec(
            method="GET",
            path="/p",
            category=EndpointCategory.QUERY,
            mutates_state=False,
            bindings=(
                FieldBinding(
                    from_path=("data", "audit_id"),
                    to_path=("audit_id",),
                    required=True,
                ),
            ),
        )
        restored = EndpointSpec.from_dict(spec.to_dict())
        assert len(restored.bindings) == 1
        b = restored.bindings[0]
        assert b.from_path == ("data", "audit_id")
        assert b.to_path == ("audit_id",)
        assert b.required is True

    def test_from_dict_basemodel_refs_left_none(self) -> None:
        """业务需求:本 PR 范围(BaseModel 引用还原留 None,PR-2.2 SDK 负责)。

        这是有意为之的退路 —— 不在 PR-2.0 做 importlib 重建。
        """
        spec = EndpointSpec(
            method="GET",
            path="/p",
            category=EndpointCategory.QUERY,
            mutates_state=False,
            request=_good_model("Req"),
            responses={200: _good_model("Resp")},
        )
        restored = EndpointSpec.from_dict(spec.to_dict())
        assert restored.request is None
        assert restored.responses == {}
        assert restored.default_response is None

    def test_from_dict_summary_description_auth_restored(self) -> None:
        """业务需求:summary/description/auth_required 严格还原。"""
        spec = EndpointSpec(
            method="GET",
            path="/p",
            category=EndpointCategory.QUERY,
            mutates_state=False,
            summary="s",
            description="d",
            auth_required=True,
        )
        restored = EndpointSpec.from_dict(spec.to_dict())
        assert restored.summary == "s"
        assert restored.description == "d"
        assert restored.auth_required is True

    def test_from_dict_invalid_category_raises(self) -> None:
        """业务需求:category 不在 enum 内 → ValueError(严格不容错)。"""
        bad = {
            "method": "GET",
            "path": "/p",
            "category": "unknown_category",
            "mutates_state": False,
        }
        with pytest.raises(ValueError, match="category"):
            EndpointSpec.from_dict(bad)

    def test_from_dict_missing_required_field_raises(self) -> None:
        """业务需求:缺 method → KeyError(严格不容错)。"""
        with pytest.raises(KeyError, match="缺失字段"):
            EndpointSpec.from_dict({"path": "/p", "category": "query", "mutates_state": False})  # type: ignore[dict-item]


# ════════════════════════════════════════════════════════════════════════════
# byte-equal 保证
# ════════════════════════════════════════════════════════════════════════════


class TestEndpointSpecByteEqual:
    def test_to_dict_twice_same(self) -> None:
        """业务需求:同 spec 两次 to_dict 字典相等(byte-equal)。"""
        spec = EndpointSpec(
            method="GET",
            path="/p",
            category=EndpointCategory.QUERY,
            mutates_state=False,
            tags=["zeta", "alpha", "mu"],
        )
        assert spec.to_dict() == spec.to_dict()

    def test_tags_input_order_does_not_change_output(self) -> None:
        """业务需求:tags 输入顺序无关(序列化前排序)。

        两个 spec 构造时 tags 顺序相反,to_dict 后必须 byte-equal。
        """
        s1 = EndpointSpec(
            method="GET",
            path="/p",
            category=EndpointCategory.QUERY,
            mutates_state=False,
            tags=["a", "b", "c"],
        )
        s2 = EndpointSpec(
            method="GET",
            path="/p",
            category=EndpointCategory.QUERY,
            mutates_state=False,
            tags=["c", "b", "a"],
        )
        assert s1.to_dict() == s2.to_dict()


# ════════════════════════════════════════════════════════════════════════════
# 集成:实际 fin 端点 round-trip
# ════════════════════════════════════════════════════════════════════════════


class TestFinEndpointsRoundTrip:
    """集成测试:31 个 fin 端点全部 to_dict 不挂 + from_dict 不挂。"""

    @pytest.fixture
    def fin_specs(self):
        """触发 fin 服务加载并返回所有 spec。"""
        from Plate import registry
        registry.resolve("fin", "POST", "/api/order/order/orderDetail")
        return [s for k, s in registry._index.items() if k.service == "fin"]

    def test_all_31_fin_endpoints_serializable(self, fin_specs) -> None:
        """业务需求:31 个 fin 端点全部 to_dict 不抛。"""
        assert len(fin_specs) == 31
        for spec in fin_specs:
            d = spec.to_dict()
            assert d["method"] == spec.method
            assert d["path"] == spec.path

    def test_all_31_fin_endpoints_round_trip(self, fin_specs) -> None:
        """业务需求:31 个 fin 端点全部 to_dict → from_dict 字段相等。"""
        for spec in fin_specs:
            restored = EndpointSpec.from_dict(spec.to_dict())
            assert restored.method == spec.method
            assert restored.path == spec.path
            assert restored.category == spec.category
            assert restored.mutates_state == spec.mutates_state
            assert len(restored.bindings) == len(spec.bindings)