"""Compute field default suggestions for a single EndpointSpec (API Surface A5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from gimbal_plate.schema.endpoint.endpoint import EndpointSpec
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry, iter_declarations

FieldDefaultKind = Literal[
    "literal",
    "scenario_var",
    "env_placeholder",
    "auth_placeholder",
    "lookup",
    "generated",
]


@dataclass(slots=True)
class FieldDefault:
    name: str
    kind: FieldDefaultKind
    value: Any | None


def _classify(field: DeclarationEntry) -> tuple[FieldDefaultKind, Any | None]:
    """Classify a single ``DeclarationEntry`` into kind + value."""
    example = field.example
    default = field.default

    # Source-kind based classification takes precedence because it expresses
    # the actual contract intent (e.g. generated timestamps).
    if field.source_kind == "generated":
        if isinstance(example, str) and "auto" in example.lower():
            return "generated", example
        return "generated", example

    if isinstance(example, str):
        if example.startswith("${var."):
            return "scenario_var", example
        if example.startswith("${env."):
            return "env_placeholder", example
        if example.startswith("${auth."):
            return "auth_placeholder", example
        if example:
            return "literal", example

    if isinstance(default, str):
        if default.startswith("${var."):
            return "scenario_var", default
        if default.startswith("${env."):
            return "env_placeholder", default
        if default.startswith("${auth."):
            return "auth_placeholder", default
        if default:
            return "literal", default

    if example is not None:
        return "literal", example
    if default is not None:
        return "literal", default
    return "literal", None


def compute_field_defaults(
    endpoint: EndpointSpec,
    *,
    step_index: int | None = None,
    scenario_vars: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return A5-shaped field default suggestions for ``endpoint``."""
    _ = step_index  # reserved for future per-step customisation
    _ = scenario_vars  # reserved for future ${var.*} resolution hint

    # 2026-09-05 目录化:全量出默认值(children 树展开,含嵌套叶子 —
    # 前端行壳预填用);form/carry 面划分是场景语境,由 platform 按
    # 解析态(step.field_states ?? entry.state)过滤,plate 不带参数。
    field_defaults: list[dict[str, Any]] = []
    for f in iter_declarations(endpoint.request.declarations):
        kind, value = _classify(f)
        field_defaults.append(
            {"name": f.name, "path": f.path, "kind": kind, "value": value}
        )

    # generated_fields: placeholders for the schema-only / generated channel.
    # (响应侧 generated 字段清单;2026-08-31 起 "carry" 一词专指请求侧
    #  传递字段(carry 通道声明条目,spec carry 设计 §2.1.1 术语唯一化);
    #  条目内层旗标同步由 "carry": True 改名 "generated": True,
    #  全仓零生产消费方,仅本测试锁形状。)
    generated_fields: list[dict[str, Any]] = []
    resp_200 = endpoint.responses.get(200)
    if resp_200 is not None:
        # 响应面单脸(state 无视),全量展开
        for f in iter_declarations(resp_200.declarations):
            if f.source_kind != "generated":
                continue
            generated_fields.append(
                {
                    "name": f.name,
                    "type": f.ui_kind if f.ui_kind != "unknown" else "string",
                    "generated": True,
                    "default": f.default if f.default is not None else "",
                }
            )

    return {
        "field_defaults": field_defaults,
        "generated_fields": generated_fields,
    }


__all__ = ["compute_field_defaults", "FieldDefault"]
