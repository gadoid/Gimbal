"""query-views 目录级校验与索引投影(2026-09-07 动态取数源 §3.3 聚合层 / §3.4)。

纯函数 over list[EndpointSpec],零 HTTP 依赖。两个消费方:
- systems/fin/endpoint ALL_ENDPOINTS 组装后立即 validate(构造期拒);
- http/routes_grammar GET /api/query-views 按需 build_index(纯投影零状态)。
"""
from __future__ import annotations

from typing import Any

from gimbal_plate.schema.endpoint import EndpointSpec
from gimbal_plate.schema.endpoint.io_spec import iter_declarations
from gimbal_plate.schema.endpoint.query_view import resolve_view_params


def validate_query_view_catalog(endpoints: list[EndpointSpec]) -> None:
    """聚合层校验 ①②⑥(③条目级/④⑤端点级在 schema validator,§3.3)。"""
    # pass 1:① view name 全局唯一(跨端点)
    seen: dict[str, str] = {}
    for ep in endpoints:
        for v in ep.query_views or []:
            if v.name in seen:
                raise ValueError(
                    f"QueryView.name={v.name!r} 重复(§3.3①):"
                    f"{seen[v.name]} 与 {ep.id}"
                )
            seen[v.name] = ep.id
    # pass 2:② 引用闭合 + ⑥ 分组一致性(解析后键 = group or view)
    group_view: dict[str, str] = {}
    for ep in endpoints:
        if ep.request is None:
            continue
        for entry in iter_declarations(ep.request.declarations):
            vs = entry.value_source
            if vs is None:
                continue
            if vs.view not in seen:
                raise ValueError(
                    f"value_source.view={vs.view!r} 未命中任何 QueryView"
                    f"(§3.3②):{ep.id} {entry.path}"
                )
            key = vs.group or vs.view
            if key in group_view and group_view[key] != vs.view:
                raise ValueError(
                    f"分组一致性(§3.3⑥):group={key!r} 同时绑定 view "
                    f"{group_view[key]!r} 与 {vs.view!r}({ep.id} {entry.path})"
                )
            group_view[key] = vs.view


def build_query_view_index(endpoints: list[EndpointSpec]) -> list[dict[str, Any]]:
    """§3.4 只读聚合投影。columns = label ∪ 全目录绑定列(有序去重)。"""
    binding_cols: dict[str, list[str]] = {}
    for ep in endpoints:
        if ep.request is None:
            continue
        for entry in iter_declarations(ep.request.declarations):
            vs = entry.value_source
            if vs is None or not vs.column:
                continue
            cols = binding_cols.setdefault(vs.view, [])
            if vs.column not in cols:
                cols.append(vs.column)
    rows: list[dict[str, Any]] = []
    for ep in endpoints:
        for v in ep.query_views or []:
            merged, missing = resolve_view_params(ep, v)
            cols = [v.label] + [c for c in binding_cols.get(v.name, []) if c != v.label]
            rows.append({
                "name": v.name,
                "endpoint_id": ep.id,
                "system": ep.system,
                "service": ep.service,
                "method": ep.api.method,
                "path": ep.api.path,
                "params": merged,
                "query_params": list(v.query_params or []),
                "items": v.items,
                "label": v.label,
                "columns": cols,
                "query_safe": ep.metadata.query_safe,
                "missing_required": missing,
                # §4.2:超时与鉴权跟随 ApiSpec —— 索引是派生载体,真源仍是 ApiSpec
                "auth": ep.api.auth,
                "timeout_seconds": ep.api.timeout_seconds,
            })
    rows.sort(key=lambda r: r["name"])
    return rows
