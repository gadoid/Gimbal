"""Resolve failed_criteria × assertable_fields linkage (API Surface B2)."""

from __future__ import annotations

import re
from typing import Any

from gimbal_plate.schema.endpoint.endpoint import EndpointSpec

# A failed_criteria line typically looks like:
#   "401 未登录 / token 过期 → response.code = 10001"
# We split into (status_code, description, field_path, field_value) when
# possible. Field references match $.<jsonpath> optionally followed by =<value>.
_LEADING_CODE = re.compile(r"^\s*(\d{3})\b")
_FIELD_REF = re.compile(r"(\$[\w.\[\]'\"]+)\s*=\s*([^\s,;→]+)")


def _parse_line(line: str) -> tuple[int | None, str, str | None, str | None]:
    code: int | None = None
    desc = line.strip()
    m = _LEADING_CODE.match(desc)
    if m:
        code = int(m.group(1))
        desc = desc[m.end():].lstrip(" ：:、,，")

    # If the line still contains an arrow separator (e.g. "未登录 → response.code = 10001"),
    # treat the second half as the actionable payload and the first half as
    # the human description. This keeps the regex search local to the
    # payload and avoids losing the description entirely.
    if "→" in desc:
        head, _, tail = desc.partition("→")
        field: str | None = None
        value: str | None = None
        fm = _FIELD_REF.search(tail)
        if fm:
            field = fm.group(1)
            value = fm.group(2).rstrip(".,;")
        return code, head.strip(), field, value

    field = None
    value = None
    fm = _FIELD_REF.search(desc)
    if fm:
        field = fm.group(1)
        value = fm.group(2).rstrip(".,;")
    return code, desc, field, value


def resolve_failed_criteria(endpoint: EndpointSpec) -> dict[str, Any]:
    """Return B2-shaped failed_criteria analysis for ``endpoint``."""
    assertable = set(endpoint.responses.get(200).assertable_fields or [])

    resolved: list[dict[str, Any]] = []
    for line in endpoint.metadata.failed_criteria or []:
        code, desc, field, _value = _parse_line(line)
        # Field path may have been extracted, but the assertable check needs the
        # exact $.code style (no trailing =value). Strip a possible value suffix
        # so a stored "$.code=10001" still matches "$.code" in assertable_fields.
        if field and "=" in field:
            field = field.split("=", 1)[0]
        assertable_flag = field in assertable if field else False
        resolved.append(
            {
                "code": code,
                "description": desc,
                "field": field,
                "assertable": assertable_flag,
            }
        )

    return {"failed_criteria": resolved}


__all__ = ["resolve_failed_criteria"]
