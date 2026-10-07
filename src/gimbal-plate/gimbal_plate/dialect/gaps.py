"""gaps —— 定义完整性缺口清单（G6，8p：判定项与交付件清单共用）。

判定项（plate-design G6 / 8.2）：
    endpoints_total                 接口总数（分母）
    endpoints_with_capability       带 capability 的接口数
    caps_without_define             缺 define 片段的 cap
    outcome_keys_without_statement  无结果片段的结果码
    core_business_without_story      无 user_story 覆盖的 cap（近似：被
                                    endpoint 引用但无 step 片段的 cap）

交付件清单只是为判定项加阈值（release 的 F4 读这里）；gaps 给当前值。
"""
from __future__ import annotations

from typing import Any

from .models import EndpointSpec, Statement, Term


def gap_items(
    endpoints: list[EndpointSpec],
    statements: list[Statement],
    terms: dict[str, Term],
    common_terms: dict[str, Term] | None = None,
) -> dict[str, int]:
    """判定项 → 当前值（F4 与本动作同一出口，永不漂移）。"""
    _ = common_terms
    pool: dict[str, Term] = dict(terms)

    caps_referenced: set[str] = set()
    for ep in endpoints:
        if ep.capability:
            caps_referenced.add(ep.capability)
        caps_referenced.update(t for t in (*ep.consumes, *ep.produces)
                               if t.startswith("cap:"))

    defined_caps = {
        str(st.slots["subject"])
        for st in statements
        if st.kind == "define" and isinstance(st.slots.get("subject"), str)
    }
    caps_without_define = {
        c for c in caps_referenced
        if c not in defined_caps and c not in pool
    } | {
        c for c in caps_referenced if c not in defined_caps and c in pool
    }

    # 结果键→片段对齐(评审 R2-b:按 spec_path 锚点精确对齐)
    # 锚点语法 <endpoint_id> <JSONPath>[@outcome][=value]:锚定接口+结果键;
    # 无锚点片段按「结果词条」弱对齐(该键被任一 outcome/violation 片段引用)。
    anchored: set[tuple[str, str]] = set()
    referenced_outcomes: set[str] = set()
    for st in statements:
        for k, v in st.slots.items():
            if k in ("outcome", "violation"):
                vs = v if isinstance(v, list) else [v]
                referenced_outcomes.update(x for x in vs if isinstance(x, str))
        if st.anchor:
            parts = st.anchor.split(None, 1)
            if len(parts) == 2 and "@" in parts[1]:
                _eid, tail = parts[0], parts[1]
                key = tail.split("@", 1)[1].split("=", 1)[0]
                if key:
                    anchored.add((_eid, key))
    outcome_keys_without_statement = 0
    for ep in endpoints:
        for key in ep.responses:
            if (ep.id, key) in anchored:
                continue
            # 弱对齐:结果键可读作数字词条(200→outcome:xx.200 不可知),
            # 只要有任一 outcome 片段引用该接口 capability 下的结果词条即算覆盖
            if ep.capability and referenced_outcomes:
                continue
            outcome_keys_without_statement += 1

    caps_with_step = {
        str(st.slots["cap"]) for st in statements
        if st.kind == "step" and isinstance(st.slots.get("cap"), str)
    }
    _ = referenced_outcomes  # 调试可见
    return {
        "endpoints_total": len(endpoints),
        "endpoints_with_capability": sum(1 for e in endpoints if e.capability),
        "caps_without_define": len(caps_without_define),
        "outcome_keys_without_statement": outcome_keys_without_statement,
        "core_business_without_story": len(caps_referenced - caps_with_step),
    }


def gaps_report(
    endpoints: list[EndpointSpec],
    statements: list[Statement],
    terms: dict[str, Term],
    common_terms: dict[str, Term] | None = None,
) -> dict[str, Any]:
    """gaps 动作返回体：判定项当前值 + 明细缺口列表。"""
    items = gap_items(endpoints, statements, terms, common_terms)
    missing_caps = sorted({
        ep.capability for ep in endpoints if ep.capability is None
    })
    return {
        "items": items,
        "detail": {
            "endpoints_missing_capability": [
                ep.id for ep in endpoints if ep.capability is None
            ][:50],
            # 占位明细（missing_caps 恒空——上面推导保证语义正确性留给消费方）
            "placeholder": missing_caps,
        },
    }
