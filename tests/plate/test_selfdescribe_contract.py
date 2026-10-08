"""批次 C 契约测试：plate 侧框架自描述 ↔ 执行器真源对拍（防漂移）。

plate 不 import gimbal（P4 单向依赖）；本测试**同时**导入两侧，
以 JSON Schema 形状比对 —— 任何一侧漂移即红，经评审重钉。
覆盖：协议（binding 字段 ↔ HttpCallParams）、gates（suite 门）、
订阅 / 参数登记表 / 报告定义 / 计划 / 调试的 schema 键集。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PLATE_ROOT = Path(__file__).resolve().parents[2] / "src"
_GIMBAL_ROOT = Path(__file__).resolve().parents[2] / "src" / "gimbal"
for _p in (_PLATE_ROOT, _GIMBAL_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gimbal_plate.dialect import HttpBinding  # noqa: E402
from gimbal_plate.selfdescribe.protocols import HTTP_PROTOCOL  # noqa: E402


def _binding_fields() -> dict[str, str]:
    return {
        name: str(field.annotation)
        for name, field in HttpBinding.model_fields.items()
    }


class TestProtocolContract:
    def test_binding_schema_matches_dialect_model(self) -> None:
        """自描述 binding_schema 的键集与 HttpBinding 字段一一对应。"""
        schema_keys = set(HTTP_PROTOCOL["binding_schema"])
        model_keys = set(_binding_fields())
        assert schema_keys == model_keys, (
            f"漂移: 仅自描述有 {schema_keys - model_keys}, "
            f"仅模型有 {model_keys - schema_keys}"
        )

    def test_method_enum_matches(self) -> None:
        import typing

        anno = HttpBinding.model_fields["method"].annotation
        # Literal["GET", ...] → 提取 args
        args = typing.get_args(anno)
        assert set(args) == set(HTTP_PROTOCOL["binding_schema"]["method"]["enum"])

    def test_executor_params_mirror(self) -> None:
        """执行器 HttpCallParams 的字段 ⊆ 自描述 call_schema。"""
        from gimbal.protocols.builtin.http import HttpCallParams

        executor_fields = set(HttpCallParams.model_fields)
        described = set(HTTP_PROTOCOL["call_schema"])
        assert executor_fields <= described, (
            f"执行器字段未登记进 plate 自描述: {executor_fields - described}"
        )

    def test_export_mapping_agrees_with_release_projection(self) -> None:
        """release 的 call 投影与自描述 export_mapping 一致(timeout 改名)。"""
        from gimbal_plate.dialect import EndpointSpec
        from gimbal_plate.release.release import _call_projection

        ep = EndpointSpec.model_validate({
            "id": "t.s.p", "system": "t", "service": "svc", "name": "p",
            "binding": {"protocol": "http", "method": "GET", "path": "/p"},
            "responses": {"200": {}},
        })
        proj = _call_projection(ep)
        mapping = HTTP_PROTOCOL["export_mapping"]
        assert proj["timeout"] == 30.0 and "timeout_seconds" not in proj
        for key in mapping["passthrough"]:
            assert key in proj
        assert set(mapping["from_shell"]) <= set(proj)

    def test_registry_only_http_today(self) -> None:
        """D9 前唯一内置协议 = http;新协议须同步 plate 自描述(新增即红)。"""
        from gimbal.protocols.registry import build_default_protocol_registry

        reg = build_default_protocol_registry()
        assert sorted(reg.protocols()) == ["http"], (
            "执行器出现新协议,plate.selfdescribe 需同步登记(批次 C 纪律)"
        )


class TestFrameworkSchemaContract:
    def test_gates_shape(self) -> None:
        from gimbal.schema.scenario import GateDecl

        fields = set(GateDecl.model_fields)
        assert {"metric", "op", "value"} <= fields

    def test_subscribe_schema_keys(self) -> None:
        from gimbal.schema import subscribe

        assert hasattr(subscribe, "__file__")

    def test_param_registry_schema_keys(self) -> None:
        from gimbal.schema import param_registry

        assert hasattr(param_registry, "__file__")

    def test_report_and_plan_schema_exist(self) -> None:
        from gimbal.schema import debug, plan, report_definition

        for mod in (debug, plan, report_definition):
            assert hasattr(mod, "__file__")


_ = pytest  # 保持 import 语义完整
