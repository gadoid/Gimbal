"""dialect.validation —— 方言校验引擎（批次 B：F/T/S/C 规则全量）。

规则编号即错误码（G2：``plate check --json`` 与 HTTP 校验共用本引擎，
每条结果带文件与行号）。

阻塞级（入库闸门 / release 机械检查）：
    F1 frontmatter 与块类型/片段 kind 在模板内
    F2 交付物满足模板 required（release 时）
    F3 系统内交付物 id / 接口 id / 片段 id 唯一 + 路由键唯一
    T1-T6 词条规则（id 合语法/唯一/父节点/replaced_by/refers）
    S1 片段槽位符合 kind 必填/可选与词条 kind 约束
    S3 transition from/to 同 attr
告警级：
    T4 同 kind label 重复；T5 alias 冲突；S2 已废弃词条引用；S4 anchor 语法
语义矫正（C 类，发布闸门要求处理完毕；修订十二：不冲突口径——
交集为空才报，子集/互补 = 部分描述，兼容）：
    C1 同一 outcome 各来源的 cap 归属集合没有任何交集
    C2 同一 cap 的 before 前置条件各来源一致
    C3 同一 (attr, from) 转移各来源的去向集合没有任何交集
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from .models import EndpointSpec, Statement, Term
from .parser import Deliverable

_SEVERITY_ORDER = {"blocking": 0, "warning": 1, "correction": 2}


@dataclass
class Finding:
    """一条校验结果：规则编号即错误码。"""

    rule: str          # F1 / T2 / S3 / C1 …
    severity: str      # blocking | warning | correction
    message: str
    source: str = ""
    line: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule, "severity": self.severity,
            "message": self.message, "source": self.source, "line": self.line,
        }


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "blocking"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def corrections(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "correction"]

    @property
    def ok(self) -> bool:
        """入库闸门口径：F/T/S 阻塞级全过；C 类只告警（发布闸门才阻塞）。"""
        return not self.blocking

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blocking": [f.to_dict() for f in self.blocking],
            "warning": [f.to_dict() for f in self.warnings],
            "correction": [f.to_dict() for f in self.corrections],
            "total": len(self.findings),
        }


# ── 类型模板 ──────────────────────────────────────────────────────

_TYPES_CACHE: dict[str, dict[str, Any]] = {}


def load_types(types_path: Path | None = None) -> dict[str, dict[str, Any]]:
    """载入 types/*.yaml → {type_id: 模板}。

    候选顺序:CWD types/ → 包位置回溯仓库根 types/(A2 同款双根)。
    显式路径不存在时同样回退——tmp 系统树的测试不依赖调用方位置。
    一个模板都没加载到时**报错不静默**(评审 M1:此前回退到不存在的
    路径会静默返回空表,F1 全线失明、/api/type 为空)。
    """
    _pkg_repo = Path(__file__).resolve().parents[3]
    candidates = [
        types_path,
        Path("types") / "types.yaml",
        _pkg_repo / "types" / "types.yaml",
    ]
    types_path = next(
        (p for p in candidates if p is not None and p.exists()),
        candidates[-1],
    )
    key = str(types_path)
    mtime = types_path.stat().st_mtime if types_path.exists() else 0
    if _TYPES_CACHE.get(key, {}).get("_mtime") != mtime:
        data = (
            yaml.safe_load(types_path.read_text(encoding="utf-8"))
            if types_path.exists() else []
        ) or []
        table = {t["id"]: t for t in data if isinstance(t, dict) and "id" in t}
        if not table:
            raise RuntimeError(
                f"交付物类型模板加载为空: {types_path}"
                f"(候选: {[str(c) for c in candidates]})——"
                f"types.yaml 缺失或损坏,CWD 与包位置均未命中仓库根?"
            )
        table["_mtime"] = mtime  # type: ignore[assignment]
        _TYPES_CACHE[key] = table
    return {k: v for k, v in _TYPES_CACHE[key].items() if k != "_mtime"}


# ── 词条 id 语法（T1）─────────────────────────────────────────────

_TERM_ID = re.compile(
    r"^(?P<kind>entity|attr|value|cap|outcome):"
    r"(?P<e>[a-z][a-z0-9_]*)"
    r"(?:\.(?P<a>[a-z][a-z0-9_]*))?"
    r"(?:\.(?P<v>[a-z0-9_]+))?"
    r"(?:\.(?P<action>[a-z][a-z0-9_]*))?$"
)
# 各 kind 的段数（固定深度,6.4）
_TERM_DEPTH = {"entity": 1, "attr": 2, "value": 3, "cap": 2, "outcome": 2}
_SEG = r"[a-z][a-z0-9_]*"
_TERM_ID_FULL = {
    "entity": re.compile(rf"^entity:{_SEG}$"),
    "attr": re.compile(rf"^attr:{_SEG}\.{_SEG}$"),
    "value": re.compile(rf"^value:{_SEG}\.{_SEG}\.[a-z0-9_]+$"),
    "cap": re.compile(rf"^cap:{_SEG}\.{_SEG}$"),
    "outcome": re.compile(rf"^outcome:{_SEG}\.{_SEG}$"),
}
# 槽位允许的词条 kind（S1:kind 必填/可选表,6.3)
_SLOT_KINDS: dict[str, set[str]] = {
    "subject": {"entity", "attr", "value", "cap", "outcome"},
    "about": {"attr", "value", "cap"},
    "before": {"cap"},
    "violation": {"outcome"},
    "cap": {"cap"},
    "outcome": {"outcome"},
    "when": {"value"},
    "target": {"entity", "attr"},
    "from": {"value"},
    "to": {"value"},
    "order": set(),   # 整数,非词条
    "branch_on": {"outcome", "value"},
    "terms": {"entity", "attr", "value", "cap", "outcome"},
}
_REQUIRED_SLOTS: dict[str, set[str]] = {
    "mention": {"subject"},
    "define": {"subject"},
    "rule": {"about"},
    "outcome": {"cap"},
    "transition": {"cap", "from", "to"},
    "step": {"cap", "order"},
    "note": set(),
}
# 各 kind 的合法槽位全集(6.3 表;白名单外即 S1 阻塞——评审 R2-a)
_ALLOWED_SLOTS: dict[str, set[str]] = {
    "mention": {"subject"},
    "define": {"subject"},
    "rule": {"about", "before", "violation"},
    "outcome": {"cap", "outcome", "when", "target"},
    "transition": {"cap", "from", "to"},
    "step": {"cap", "order", "branch_on"},
    "note": {"terms"},
}
# 至少一槽(6.3:outcome 与 target 至少一个)
_AT_LEAST_ONE: dict[str, tuple[str, ...]] = {
    "outcome": ("outcome", "target"),
}


def term_kind_of(term_id: str) -> str | None:
    """词条 id → kind（前缀解析）。"""
    return term_id.split(":", 1)[0] if ":" in term_id else None


# ── 校验主入口 ────────────────────────────────────────────────────

def validate_deliverable(
    deliverable: Deliverable, *, types: dict[str, Any] | None = None,
    report: ValidationReport | None = None,
) -> ValidationReport:
    """单交付物校验（F1 / F2 / S1 / S3 / S4 / T·局部）。"""
    types = types if types is not None else load_types()
    report = report if report is not None else ValidationReport()
    src = deliverable.source
    fm = deliverable.frontmatter

    if fm is None:
        report.add(Finding("F1", "blocking", "缺少 frontmatter", source=src))
        type_id = None
    else:
        type_id = fm.type
        if type_id not in types:
            report.add(Finding(
                "F1", "blocking",
                f"未知交付物类型 {type_id!r}(合法: {sorted(types)})",
                source=src,
            ))
            type_id = None

    template = types.get(type_id or "", {})
    allowed_blocks = set(template.get("blocks", []))
    allowed_kinds = set(template.get("statement_kinds", []))

    counts: dict[str, int] = {}
    for node in deliverable.nodes:
        if not hasattr(node, "type"):
            continue
        block = node
        counts[block.type] = counts.get(block.type, 0) + 1
        if allowed_blocks and block.type not in allowed_blocks:
            report.add(Finding(
                "F1", "blocking",
                f"块类型 gimbal:{block.type} 不在类型 {type_id!r} 的 blocks 内",
                source=src, line=block.line,
            ))
        for model in block.models():
            if isinstance(model, Statement):
                counts[f"kind:{model.kind}"] = (
                    counts.get(f"kind:{model.kind}", 0) + 1)
                _check_statement(model, allowed_kinds, src, block.line, report)

    # F2:required 计数（片段 kind 也计入）
    required: dict[str, int] = template.get("required", {}) or {}
    for key, minimum in required.items():
        # 计数口径(6.5):键匹配块类型(如 system)或片段 kind(如 step)
        actual = counts.get(key, counts.get(f"kind:{key}", 0))
        if actual < minimum:
            report.add(Finding(
                "F2", "blocking",
                f"类型 {type_id!r} 要求 {key} ≥ {minimum},实际 {actual}",
                source=src,
            ))
    return report


def _check_statement(
    st: Statement, allowed_kinds: set[str], src: str, line: int,
    report: ValidationReport,
) -> None:
    if allowed_kinds and st.kind not in allowed_kinds:
        report.add(Finding(
            "F1", "blocking",
            f"片段 kind {st.kind!r} 不在模板 statement_kinds 内",
            source=src, line=line,
        ))
    # S1:必填槽位
    missing = _REQUIRED_SLOTS.get(st.kind, set()) - set(st.slots)
    if missing:
        report.add(Finding(
            "S1", "blocking",
            f"片段 {st.id}: kind={st.kind} 缺必填槽位 {sorted(missing)}",
            source=src, line=line,
        ))
    # S1:槽位白名单(kind 私有语法,未知槽=拼写错误/错 kind)
    unknown = set(st.slots) - _ALLOWED_SLOTS.get(st.kind, set())
    if unknown:
        report.add(Finding(
            "S1", "blocking",
            f"片段 {st.id}: kind={st.kind} 不接受槽位 {sorted(unknown)}"
            f"(合法: {sorted(_ALLOWED_SLOTS[st.kind])})",
            source=src, line=line,
        ))
    # S1:at-least-one(如 outcome 须有 outcome 或 target 之一)
    need_group = _AT_LEAST_ONE.get(st.kind)
    if need_group and not any(g in st.slots for g in need_group):
        report.add(Finding(
            "S1", "blocking",
            f"片段 {st.id}: kind={st.kind} 须至少提供 {'/'.join(need_group)}",
            source=src, line=line,
        ))
    # S1:step.order 整数
    if st.kind == "step" and not isinstance(st.slots.get("order"), int):
        report.add(Finding(
            "S1", "blocking",
            f"片段 {st.id}: step.order 须为整数",
            source=src, line=line,
        ))
    # S1:槽位词条 kind 约束(order 为整数槽)
    for slot, value in st.slots.items():
        allowed = _SLOT_KINDS.get(slot)
        if allowed is None or isinstance(value, int):
            continue
        ids = value if isinstance(value, list) else [value]
        for tid in ids:
            if not isinstance(tid, str):
                continue
            k = term_kind_of(tid)
            if k is None or k not in allowed:
                report.add(Finding(
                    "S1", "blocking",
                    f"片段 {st.id}: 槽位 {slot} 不接受词条 kind {k!r}({tid})",
                    source=src, line=line,
                ))
    # S3:transition from/to 同 attr
    if st.kind == "transition":
        f_, t_ = str(st.slots.get("from", "")), str(st.slots.get("to", ""))
        if f_.rsplit(".", 1)[0] != t_.rsplit(".", 1)[0]:
            report.add(Finding(
                "S3", "blocking",
                f"片段 {st.id}: transition from/to 须属同一 attr({f_} vs {t_})",
                source=src, line=line,
            ))


def validate_terms(
    terms: Iterable[Term], *, system_id: str, common_ids: set[str] | None = None,
    report: ValidationReport | None = None,
) -> ValidationReport:
    """词条规则 T1–T5（单系统 + common 参照）。"""
    report = report if report is not None else ValidationReport()
    common_ids = common_ids or set()
    seen: dict[str, str] = {}       # id → source
    labels: dict[str, str] = {}     # (kind,label) → id
    aliases: dict[str, str] = {}    # alias → id

    for term in terms:
        src = getattr(term, "_source", system_id)
        # T1:语法 + 系统内唯一 + 不与 common 重名
        kind = term_kind_of(term.id)
        pat = _TERM_ID_FULL.get(kind or "")
        if kind is None or pat is None or not pat.match(term.id):
            report.add(Finding(
                "T1", "blocking",
                f"词条 id {term.id!r} 不合语法(kind 段数固定,6.4)", source=src,
            ))
            continue
        if term.id in seen:
            report.add(Finding(
                "T1", "blocking",
                f"词条 id {term.id!r} 系统内重复(先见于 {seen[term.id]})",
                source=src,
            ))
        if term.id in common_ids:
            report.add(Finding(
                "T1", "blocking",
                f"词条 id {term.id!r} 与 systems/common 重名", source=src,
            ))
        seen[term.id] = src
        # T2:父节点存在(entity 无父;attr→entity;value→attr;cap/outcome→entity)
        parent = _parent_of(term.id)
        if parent is not None and parent not in {
            t.id for t in terms if t is not term
        } and parent not in common_ids and seen.get(parent) is None:
            # 宽松:同批后出现也算(收集完再验由调用方二次跑);此处即时报
            report.add(Finding(
                "T2", "blocking",
                f"词条 {term.id!r} 的父节点 {parent!r} 不存在", source=src,
            ))
        # T4:同 kind label 重复(告警)
        key = (kind, term.label)
        if key in labels and labels[key] != term.id:
            report.add(Finding(
                "T4", "warning",
                f"同 kind label 重复: {term.label!r}({labels[key]} / {term.id})",
                source=src,
            ))
        else:
            labels[key] = term.id
        # T5:alias 冲突(告警)
        for alias in term.aliases:
            if alias in aliases and aliases[alias] != term.id:
                report.add(Finding(
                    "T5", "warning",
                    f"alias {alias!r} 与 {aliases[alias]} 冲突",
                    source=src,
                ))
            else:
                aliases[alias] = term.id
    # T3:replaced_by 存在/同 kind/active/不成环(收全后验)
    all_ids = set(seen) | common_ids
    by_id: dict[str, Term] = {t.id: t for t in terms}
    for term in terms:
        if term.replaced_by is None:
            continue
        target = by_id.get(term.replaced_by)
        if term.replaced_by not in all_ids or target is None:
            report.add(Finding(
                "T3", "blocking",
                f"词条 {term.id!r} 的 replaced_by {term.replaced_by!r} 不存在",
            ))
            continue
        if term_kind_of(term.replaced_by) != term_kind_of(term.id):
            report.add(Finding(
                "T3", "blocking",
                f"词条 {term.id!r} 的 replaced_by 须同 kind",
            ))
        if target.status != "active":
            report.add(Finding(
                "T3", "blocking",
                f"词条 {term.id!r} 的 replaced_by {target.id!r} 须 active",
            ))
        # 不成环:沿链走
        hop, seen_chain = term.replaced_by, {term.id}
        while hop is not None and hop in by_id:
            if hop in seen_chain:
                report.add(Finding(
                    "T3", "blocking",
                    f"词条 {term.id!r} 的 replaced_by 链成环",
                ))
                break
            seen_chain.add(hop)
            hop = by_id[hop].replaced_by
    # T6:refers 仅 attr→attr、目标 active、不成环
    for term in terms:
        if term.refers is None:
            continue
        if term_kind_of(term.id) != "attr" or term_kind_of(term.refers) != "attr":
            report.add(Finding(
                "T6", "blocking",
                f"词条 {term.id!r} 的 refers 仅允许 attr → attr",
            ))
            continue
        target = by_id.get(term.refers)
        if target is None or target.status != "active":
            report.add(Finding(
                "T6", "blocking",
                f"词条 {term.id!r} 的 refers 目标 {term.refers!r} 须为 active attr",
            ))
        hop, seen_chain = term.refers, {term.id}
        while hop is not None and hop in by_id:
            if hop in seen_chain:
                report.add(Finding(
                    "T6", "blocking", f"词条 {term.id!r} 的 refers 链成环",
                ))
                break
            seen_chain.add(hop)
            hop = by_id[hop].refers
    return report


def _parent_of(term_id: str) -> str | None:
    kind = term_kind_of(term_id)
    if kind == "attr":
        return "entity:" + term_id.split(":", 1)[1].rsplit(".", 1)[0]
    if kind in ("value",):
        return "attr:" + term_id.split(":", 1)[1].rsplit(".", 1)[0]
    if kind in ("cap", "outcome"):
        return "entity:" + term_id.split(":", 1)[1].rsplit(".", 1)[0]
    return None


def validate_references(
    endpoints: Iterable[EndpointSpec], statements: Iterable[Statement],
    terms: dict[str, Term], *, common_terms: dict[str, Term] | None = None,
    report: ValidationReport | None = None,
) -> ValidationReport:
    """S2:Spec/片段的词条引用可解析(不存在阻塞;已废弃告警)。"""
    report = report if report is not None else ValidationReport()
    pool = dict(terms)
    pool.update(common_terms or {})

    def _check_ref(tid: str, who: str) -> None:
        if tid not in pool:
            report.add(Finding("S2", "blocking", f"{who} 引用的词条 {tid!r} 不存在"))
        elif pool[tid].status == "deprecated":
            report.add(Finding(
                "S2", "warning",
                f"{who} 引用已废弃词条 {tid!r}(replaced_by={pool[tid].replaced_by})",
            ))

    for ep in endpoints:
        if ep.capability:
            _check_ref(ep.capability, f"接口 {ep.id}.capability")
        for tid in (*ep.consumes, *ep.produces):
            _check_ref(tid, f"接口 {ep.id}")
    for st in statements:
        for slot, value in st.slots.items():
            if isinstance(value, int):
                continue
            for tid in (value if isinstance(value, list) else [value]):
                if isinstance(value := tid, str):  # noqa: PLW2901
                    _check_ref(value, f"片段 {st.id}.{slot}")
    return report


def validate_consistency(
    endpoints: Iterable[EndpointSpec], statements: Iterable[Statement],
    report: ValidationReport | None = None,
) -> ValidationReport:
    """C1–C3:跨**来源**(交付物文件)一致性(评审 P0-14 重写;修订十二
    口径 = 不冲突:交集为空才报,子集/互补视为部分描述)。

    - 同一文件内的多处引用不算「来源不一致」(同来源由评审把关);
    - C1:同一 outcome 在**不同来源**中的 cap 归属集合没有任何公共值
      (PRD 只关联降级、接口文档只关联删除 → 不相交 → 报);
    - C2:同一 about 主语在不同来源中的 before 前置条件不一致;
    - C3:同一 (attr, from) 转移在不同来源中的去向集合没有任何公共值
      (a→b vs a→c → 报;a→b vs 完整链里的 a→b → 不报——边级比对,
      不同转移边互补不比较)。
    """
    report = report if report is not None else ValidationReport()

    def _src(st: Statement) -> str:
        return getattr(st, "_source", "") or "<unknown>"

    # C1(修订十二拍板:不冲突口径)
    # 报告条件 = 各来源 cap 集合的**交集为空**(对同一 outcome 没有任何
    # 一致的 cap 归属)。子集/超集/有交集 = 部分描述,兼容——C 类在发布
    # 闸门是硬阻塞,全等口径会让「局部文档撞完整文档」随文档增多频繁
    # 锁死发版;设计 §7 的典型实例(PRD 只关联降级、接口文档只关联删除)
    # 本就是两个不相交的集合,交集口径足以捕捉。
    caps_by_outcome: dict[str, dict[str, set[str]]] = {}
    for st in statements:
        if st.kind not in ("rule", "outcome"):
            continue
        cap: str | None = None
        if st.kind == "outcome":
            c = st.slots.get("cap")
            cap = c if isinstance(c, str) else None
        else:
            a = st.slots.get("about")
            cap = a if isinstance(a, str) and a.startswith("cap:") else None
        if cap is None:
            continue
        for slot in ("violation", "outcome"):
            v = st.slots.get(slot)
            if isinstance(v, str):
                caps_by_outcome.setdefault(v, {}).setdefault(
                    _src(st), set()).add(cap)
    for outcome, per_src in caps_by_outcome.items():
        sets = [s for s in per_src.values() if s]
        if len(sets) > 1 and not set.intersection(*sets):
            report.add(Finding(
                "C1", "correction",
                f"outcome {outcome!r} 各来源没有任何一致的 cap 归属: "
                + "; ".join(f"{src}→{sorted(s)}" for src, s in per_src.items()),
            ))
    # C2
    before_by_about: dict[str, dict[str, set[str]]] = {}
    for st in statements:
        if st.kind != "rule":
            continue
        about, before = st.slots.get("about"), st.slots.get("before")
        if not isinstance(about, str) or "before" not in st.slots:
            continue
        b = before if isinstance(before, str) else ",".join(before)
        before_by_about.setdefault(about, {}).setdefault(
            _src(st), set()).add(b)
    for about, per_src in before_by_about.items():
        sets = [s for s in per_src.values() if s]
        if len(sets) > 1 and any(a != sets[0] for a in sets[1:]):
            report.add(Finding(
                "C2", "correction",
                f"{about!r} 的 before 前置条件各来源不一致: "
                + "; ".join(f"{src}→{sorted(s)}" for src, s in per_src.items()),
            ))
    # C3(修订十二拍板:不冲突口径,边级比对)
    # 同一 (attr, from) 的去向集合按来源分组,**交集为空**才报——同一
    # from 的分支(去向有公共值)= 更完整的描述,兼容;不同转移边
    # (a→b 与 b→c)= 互补描述同一状态机,不比较。全等口径会把「一份
    # 文档只描述状态机的一部分」误判为与完整描述冲突。
    edges_by_from: dict[tuple[str, str], dict[str, set[str]]] = {}
    for st in statements:
        if st.kind != "transition":
            continue
        f_ = str(st.slots.get("from", ""))
        t_ = str(st.slots.get("to", ""))
        attr = f_.rsplit(".", 1)[0]
        if attr and f_.startswith("value:"):
            edges_by_from.setdefault((attr, f_), {}).setdefault(
                _src(st), set()).add(t_)
    for (attr, from_v), per_src in edges_by_from.items():
        sets = [s for s in per_src.values() if s]
        if len(sets) > 1 and not set.intersection(*sets):
            report.add(Finding(
                "C3", "correction",
                f"attr {attr!r} 的转移 {from_v!r} 各来源没有任何一致的去向: "
                + "; ".join(f"{src}→{sorted(s)}" for src, s in per_src.items()),
            ))
    return report


def validate_tree_ids(
    deliverables: list[Deliverable],
    report: ValidationReport | None = None,
) -> ValidationReport:
    """F3(树级):系统内交付物 id(显式声明的)唯一。"""
    report = report if report is not None else ValidationReport()
    seen: dict[str, str] = {}
    for d in deliverables:
        if d.frontmatter is None or not d.frontmatter.id:
            continue   # 缺省取路径,天然唯一(8w)
        did = d.frontmatter.id
        if did in seen:
            report.add(Finding(
                "F3", "blocking",
                f"交付物 id {did!r} 重复(先见于 {seen[did]})",
                source=d.source,
            ))
        else:
            seen[did] = d.source
    return report


@dataclass
class SystemTree:
    """一次系统树装配的全部产物。

    评审 J1/J5(第五轮):「同一引擎」不能只靠口头约定——此前
    validate_system_tree / release / gaps / cli._load_tree / loader 各自
    遍历,已经出现口径分歧(release 弱于 check、错误处理不一致)。
    collect_system_tree 是唯一装配点;校验走 validate_system_tree,
    消费方(release 冻结 / gaps / CLI 检索)复用同一份产物。
    """

    system_root: Path
    deliverables: list[Deliverable] = field(default_factory=list)
    endpoints: list[EndpointSpec] = field(default_factory=list)
    statements: list[Statement] = field(default_factory=list)
    terms: dict[str, Term] = field(default_factory=dict)
    reviewed: list[tuple[str, Any]] = field(default_factory=list)  # (kind, model),8v
    term_block_review: dict[str, bool] = field(default_factory=dict)  # 含 common
    common_terms: dict[str, Term] = field(default_factory=dict)


def collect_system_tree(
    system_root: Path, *, with_common: bool = True,
) -> SystemTree:
    """解析一个系统目录(+common 参照)为 SystemTree(唯一装配点)。

    DialectError 不在此吞——调用方决定口径:validate_system_tree 转
    F0 finding(J5),release 转发布失败。
    """
    from .parser import parse_markdown

    tree = SystemTree(system_root=system_root)
    for md in sorted(system_root.rglob("*.md")):
        d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
        tree.deliverables.append(d)
        for b in d.blocks():
            for m in b.models():
                if isinstance(m, EndpointSpec):
                    tree.endpoints.append(m)
                    if b.review == "reviewed":
                        tree.reviewed.append(("endpoint", m))
                elif isinstance(m, Statement):
                    tree.statements.append(m)
                    if b.review == "reviewed":
                        tree.reviewed.append(("statement", m))
                elif isinstance(m, Term):
                    tree.terms[m.id] = m
                    tree.term_block_review[m.id] = (b.review == "reviewed")
                    if b.review == "reviewed":
                        tree.reviewed.append(("term", m))
    if with_common:
        common_root = system_root.parent / "common"
        if common_root.is_dir() and system_root.name != "common":
            for md in sorted(common_root.rglob("*.md")):
                d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
                for b in d.blocks("term"):
                    for m in b.models():
                        if isinstance(m, Term):
                            tree.common_terms[m.id] = m
                            tree.term_block_review[m.id] = (b.review == "reviewed")
    return tree


def validate_system_tree(
    system_root: Path,
    *,
    types: dict[str, Any] | None = None,
    report: ValidationReport | None = None,
    tree: SystemTree | None = None,
) -> ValidationReport:
    """系统级校验引擎——CLI ``plate check`` / HTTP ``system/action/check``
    / ``release_system`` 机械检查的**同一**实现。

    装配口径:单交付物规则(F1/F2/S1/S3)+ 树级 F3(交付物 id / 接口
    id / 路由键 / 片段 id / system 字段与目录一致性)+ 词条 T1–T6
    (含 ``systems/common`` 参照)+ 引用 S2 + 一致性 C1–C3。

    J5:方言级解析错误在此统一转 F0(带 e.source/e.line)——CLI 与
    HTTP 不再各自拆字符串或裸 500。
    """
    from .parser import DialectError

    report = report if report is not None else ValidationReport()
    types = types if types is not None else load_types()
    if tree is None:
        try:
            tree = collect_system_tree(system_root)
        except DialectError as e:
            report.add(Finding("F0", "blocking", str(e),
                               source=e.source, line=e.line))
            return report
    endpoints, statements = tree.endpoints, tree.statements
    common_terms = tree.common_terms

    for d in tree.deliverables:
        validate_deliverable(d, types=types, report=report)
    validate_tree_ids(tree.deliverables, report=report)
    # F3(树级,与 release 闸门同口径——评审第三轮:此前 check 只查交付物
    # id,跨文件重复的接口 id / 片段 id / 路由键要到发版才拦,入库闸门
    # 漏 F3)。路由键 = (protocol, service, *locator),取代旧注册表
    # 「先注册者胜」的顺序依赖语义(设计 §7 F3)。
    ep_seen: dict[str, str] = {}
    route_seen: dict[tuple, str] = {}
    for ep in endpoints:
        src = getattr(ep, "_source", "")
        # J3:接口 system 字段须与所在目录一致——不一致时 loader 会把它
        # 注册到别的系统下,check/release 冻结的归属与查询面分裂
        if ep.system != system_root.name:
            report.add(Finding(
                "F3", "blocking",
                f"接口 {ep.id!r} 的 system 字段 {ep.system!r} 与所在目录 "
                f"{system_root.name!r} 不一致",
                source=src,
            ))
        if ep.id in ep_seen:
            report.add(Finding(
                "F3", "blocking",
                f"接口 id {ep.id!r} 系统内重复(先见于 {ep_seen[ep.id]})",
                source=src,
            ))
        else:
            ep_seen[ep.id] = src
        route = (ep.binding.protocol, ep.service, *ep.binding.locator())
        if route in route_seen:
            report.add(Finding(
                "F3", "blocking",
                f"路由键 {route} 重复({ep.id} 与先见于 {route_seen[route]} 的接口)",
                source=src,
            ))
        else:
            route_seen[route] = ep.id
    st_seen: dict[str, str] = {}
    for st in statements:
        src = getattr(st, "_source", "")
        if st.id in st_seen:
            report.add(Finding(
                "F3", "blocking",
                f"片段 id {st.id!r} 系统内重复(先见于 {st_seen[st.id]})",
                source=src,
            ))
        else:
            st_seen[st.id] = src
    validate_terms(
        tree.terms.values(), system_id=system_root.name,
        common_ids=set(common_terms), report=report,
    )
    validate_references(
        endpoints, statements, tree.terms, common_terms=common_terms, report=report,
    )
    validate_consistency(endpoints, statements, report=report)
    return report
