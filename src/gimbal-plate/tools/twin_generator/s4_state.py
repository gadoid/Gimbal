"""S4:状态赋值(spec §2 白名单判据)+ value_source 同名匹配。

判据:read → form;
     !read && (required | must_include | not_null_no_default) → carry + 须挂 value_source;
     其余 → carry。
enum×value_source 互斥(io_spec):enum 字段跳过挂载,标 needs_capture:enum_required。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ir import ActionIR, FieldIR
from .schema_source import ColumnCatalog


@dataclass
class DisambigReport:
    ambiguous: list = field(default_factory=list)   # (action_id, key, {视图名})


def assign(all_fields: dict, actions: list[ActionIR], catalog: ColumnCatalog,
           view_rows: list[dict]) -> DisambigReport:
    report = DisambigReport()
    for act in actions:
        for f in all_fields.get(act.id, []):
            if f.read:
                f.state = "form"
                continue
            f.state = "carry"
            needs_value = (f.required or f.must_include
                           or catalog.not_null_no_default(f.key))
            if not needs_value:
                continue
            if f.enum_values:
                f.flags.append("needs_capture:enum_required")
                continue
            hits = [r["name"] for r in view_rows if f.key in r["columns"]]
            if len(hits) == 1:
                f.value_source = (hits[0], f.key)
            else:
                f.flags.append("needs_capture:value_source")
                if len(hits) > 1:
                    report.ambiguous.append((act.id, f.key, set(hits)))
    return report
