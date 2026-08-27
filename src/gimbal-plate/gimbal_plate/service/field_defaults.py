"""Compute field default suggestions for a single EndpointSpec (API Surface A5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from gimbal_plate.schema.endpoint.endpoint import EndpointSpec
from gimbal_plate.schema.endpoint.io_spec import IOFieldBinding

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


def _classify(field: IOFieldBinding) -> tuple[FieldDefaultKind, Any | None]:
    """Classify a single ``IOFieldBinding`` into kind + value."""
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

    field_defaults: list[dict[str, Any]] = []
    for f in endpoint.request.fields:
        kind, value = _classify(f)
        field_defaults.append(
            {"name": f.name, "kind": kind, "value": value}
        )

    # carry_fields: placeholders for the schema-only / generated channel.
    # V1 semantics: every response 200 IOFieldBinding with source_kind=generated
    # is treated as a "carry" field; IOFieldBinding does not yet expose a
    # ``carry`` flag, so this is a best-effort default and is explicitly
    # documented as such in the response.
    carry_fields: list[dict[str, Any]] = []
    resp_200 = endpoint.responses.get(200)
    if resp_200 is not None:
        for f in resp_200.fields:
            if f.source_kind != "generated":
                continue
            carry_fields.append(
                {
                    "name": f.name,
                    "type": f.ui_kind if f.ui_kind != "unknown" else "string",
                    "carry": True,
                    "default": f.default if f.default is not None else "",
                }
            )

    return {
        "field_defaults": field_defaults,
        "carry_fields": carry_fields,
    }


__all__ = ["compute_field_defaults", "FieldDefault"]
