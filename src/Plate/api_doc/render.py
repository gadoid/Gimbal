"""Plate API doc 渲染层。

对应设计:``design/phase3/PR-3.1.md`` §2.3。

数据源(只读):
  - ``Plate.spec.EndpointSpec`` —— L1 契约(method / path / summary / tags /
    category / mutates_state / bindings / response_data_models / ...)
  - ``Plate.doc.EndpointDoc`` —— L2 注释(summary / notes / requires / see_also)

输出:人类可读的 Markdown,按 category 分组(BUSINESS → QUERY → TOOL)+ path 字典序。
L2 doc=None 时静默显示 "(无 L2 注释)",不抛错(对应 PLATE_DESIGN §0 L1/L2 解耦)。

**B2 原则(渲染层零副作用)**:本模块**只读** spec 与 doc,**不**做任何修改,
**不**触发任何 IO,**不** import 任何 service 子包。
"""
from __future__ import annotations

from typing import Callable

from Plate.doc import EndpointDoc
from Plate.spec import EndpointCategory, EndpointSpec


# ════════════════════════════════════════════════════════════════════════════
# 分类排序与中文标签(对齐 PLATE_DESIGN §0 核心原则"业务流程地图,非字母序平铺")
# ════════════════════════════════════════════════════════════════════════════

_CATEGORY_ORDER: tuple[EndpointCategory, ...] = (
    EndpointCategory.BUSINESS,
    EndpointCategory.QUERY,
    EndpointCategory.TOOL,
)

_CATEGORY_LABELS: dict[EndpointCategory, str] = {
    EndpointCategory.BUSINESS: "业务接口",
    EndpointCategory.QUERY: "查询接口",
    EndpointCategory.TOOL: "工具接口",
}


# ════════════════════════════════════════════════════════════════════════════
# 渲染函数
# ════════════════════════════════════════════════════════════════════════════


def _format_path(path: tuple[str, ...] | list[str]) -> str:
    """``(a, b, c)`` → ``"a.b.c"``,空元组 → ``"<body>"``。"""
    if not path:
        return "<body>"
    return ".".join(path)


def render_endpoint(
    spec: EndpointSpec,
    doc: EndpointDoc | None = None,
) -> str:
    """渲染单个 ``EndpointSpec`` 的 Markdown。

    L2 doc=None 时,业务备注段显示 "(无 L2 注释)"(对齐 PLATE_DESIGN §0 "L2 不阻塞 L1")。
    """
    parts: list[str] = [f"### {spec.method} {spec.path}"]

    if spec.summary:
        parts.append(f"- **summary**: {spec.summary}")

    parts.append(
        f"- **category**: {spec.category.value} "
        f"({_CATEGORY_LABELS[spec.category]})"
    )
    parts.append(f"- **mutates_state**: {spec.mutates_state}")

    if spec.tags:
        parts.append(f"- **tags**: {', '.join(spec.tags)}")

    # request / responses 模型类名(不展开 JSON schema,只显示类名)
    if spec.request is not None:
        parts.append(f"- **request**: `{spec.request.__name__}`")
    if spec.responses:
        parts.append("- **responses**:")
        for code, model in sorted(spec.responses.items()):
            parts.append(f"  - `{code}`: `{model.__name__}`")

    # bindings(PR-3.1 §2.7 字段偏差已记录:实际字段是 ``bindings`` 不是
    # ``field_bindings``,实际 ``FieldBinding`` 只记 ``from_path/to_path/required/transform``)
    if spec.bindings:
        parts.append("- **字段绑定(bindings)**:")
        for fb in spec.bindings:
            from_path = _format_path(fb.from_path)
            to_path = _format_path(fb.to_path)
            extra = ""
            if fb.transform:
                extra += f" [transform: {fb.transform}]"
            if not fb.required:
                extra += " [optional]"
            parts.append(f"  - `{to_path}` ← `{from_path}`{extra}")

    # L2 doc
    if doc is None:
        parts.append("- **业务备注**: (无 L2 注释)")
    else:
        if doc.summary and doc.summary != spec.summary:
            parts.append(f"- **L2 summary**: {doc.summary}")
        if doc.notes:
            parts.append("- **注意事项(notes)**:")
            for n in doc.notes:
                parts.append(f"  - {n}")
        if doc.requires:
            parts.append("- **前置条件(requires)**:")
            for r in doc.requires:
                parts.append(f"  - {r}")
        if doc.see_also:
            parts.append(f"- **see_also**: {', '.join(doc.see_also)}")

    return "\n".join(parts) + "\n"


def render_service(
    service: str,
    specs: list[EndpointSpec],
    doc_lookup: Callable[[str], EndpointDoc | None] | None = None,
) -> str:
    """渲染整个 service 的 Markdown。

    排序:BUSINESS → QUERY → TOOL(category 固定顺序),同 category 内按 path 字典序。

    ``doc_lookup(path) -> EndpointDoc | None`` 是注入的 L2 查询函数;
    ``None`` 表示该 service 没有 L2 注释,所有 endpoint 都显示 "(无 L2 注释)"。
    这是 Phase 1 设计允许的状态(PLATE_DESIGN §4 "L1/L2 物理解耦")。
    """
    by_cat: dict[EndpointCategory, list[EndpointSpec]] = {c: [] for c in _CATEGORY_ORDER}
    for spec in specs:
        by_cat[spec.category].append(spec)

    out: list[str] = [f"# {service} 服务 API 文档\n"]

    total = len(specs)
    with_l2 = 0
    if doc_lookup is not None:
        with_l2 = sum(1 for s in specs if doc_lookup(s.path) is not None)
    out.append(f"> 共 {total} 个端点,{with_l2} 个有 L2 注释\n")

    for cat in _CATEGORY_ORDER:
        group = sorted(by_cat[cat], key=lambda s: s.path)
        if not group:
            continue
        out.append(f"## {_CATEGORY_LABELS[cat]}({cat.value}, {len(group)})\n")
        for spec in group:
            doc = doc_lookup(spec.path) if doc_lookup else None
            out.append(render_endpoint(spec, doc))
        out.append("")  # 空行分隔不同 category 块

    return "\n".join(out)


__all__ = [
    "render_endpoint",
    "render_service",
]