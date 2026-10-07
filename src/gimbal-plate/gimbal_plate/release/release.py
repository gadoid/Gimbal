"""release 冻结（批次 B 真实现，7.1 / 8.2 / 8v）。

发布闸门只检查、不编辑（已定）：
    ① 机械检查：F/T/S 阻塞级 + F2 模板 required + F4 交付件清单阈值
    ② 一致性检查：被待冻结内容引用的 draft 词条须已处理（阻塞）；
       未被引用的孤儿 draft 只是不进本次 release（修订九，与块同口径）
    ③ 冻结范围与引用闭包（8v）：只收 ``reviewed`` 块；已冻结块只能引用
       已冻结的块与词条，违反即阻塞
    ④ 人签发（签发人由调用方传入）

产物（内容寻址，全局对象池）：
    plate_artifacts/objects/<hash>.json          每对象一份,跨版本/跨系统共享
    plate_artifacts/<系统>/releases/<id>/manifest.json
        对象 hash 清单 + call 投影清单 + 模板/方言/M2 版本 + 矫正日志

release_id = ``YYYY.MM.N``（年月 + 当月序号，系统内单调递增，N2 已定）。
磁盘增长与「变更量」成正比（未变化对象跨版本同 hash,manifest 天然 diff）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gimbal_plate.dialect import EndpointSpec, Statement, Term, object_hash
from gimbal_plate.dialect.parser import Deliverable, parse_markdown
from gimbal_plate.dialect.validation import (
    Finding,
    ValidationReport,
    load_types,
    validate_consistency,
    validate_deliverable,
    validate_references,
    validate_terms,
)

DIALECT_VERSION = "1"   # 方言版本(manifest 记录,修订四)
M2_VERSION = "2"        # M2 schema 代际(1=旧栈 ApiSpec,2=Binding/outcome 键)


class ReleaseResult:
    def __init__(self, *, success: bool, release_id: str | None = None,
                 message: str = "", manifest: dict[str, Any] | None = None,
                 report: ValidationReport | None = None) -> None:
        self.success = success
        self.release_id = release_id
        self.message = message
        self.manifest = manifest
        self.report = report

    def __repr__(self) -> str:  # pragma: no cover - 调试便利
        return (f"ReleaseResult(success={self.success}, "
                f"release_id={self.release_id!r}, message={self.message!r})")


def _call_projection(ep: EndpointSpec) -> dict[str, Any]:
    """binding → call 投影（6.2 export 映射;timeout_seconds → timeout）。"""
    b = ep.binding
    out: dict[str, Any] = {
        "kind": "call",
        "protocol": b.protocol,
        "service": ep.service,
        "timeout": b.timeout_seconds,
    }
    # http 专属字段按协议分派（P5:各协议自有字段原样透传）
    for attr in ("method", "path", "headers"):
        if hasattr(b, attr):
            out[attr] = getattr(b, attr)
    return out


def _next_release_id(system_releases_dir: Path) -> str:
    """YYYY.MM.N(年月 + 当月序号,系统内单调,N2 已定)。"""
    now = datetime.now(timezone.utc)
    prefix = f"{now.year}.{now.month:02d}."
    existing = (
        [d.name for d in system_releases_dir.iterdir()
         if d.is_dir() and d.name.startswith(prefix)]
        if system_releases_dir.exists() else []
    )
    seq = max((int(n.rsplit(".", 1)[1]) for n in existing), default=0) + 1
    return f"{prefix}{seq}"


def _freeze_objects(
    artifacts_root: Path, models: list[tuple[str, Any]],
) -> list[dict[str, Any]]:
    """对象落全局池（评审 P0-16：临时文件 + rename 原子写；复用前校验）。"""
    import os
    import tempfile

    objects_dir = artifacts_root / "objects"
    objects_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for kind, model in models:
        h = object_hash(model)
        obj_path = objects_dir / f"{h}.json"
        content = json.dumps(
            {"kind": kind, **model.model_dump(mode="json")},
            ensure_ascii=False, indent=1,
        ).encode("utf-8")
        if not (obj_path.exists() and obj_path.read_bytes() == content):
            fd, tmp = tempfile.mkstemp(dir=objects_dir, suffix=".tmp")
            try:
                os.write(fd, content)
            finally:
                os.close(fd)
            os.replace(tmp, obj_path)   # 原子:截断文件不会被「已存在」掩护
        entries.append({"kind": kind, "id": getattr(model, "id", ""), "hash": h})
    return entries


def release_system(
    system_root: Path,
    *,
    artifacts_root: Path | None = None,
    signed_by: str = "",
    checklist: dict[str, int] | None = None,
) -> ReleaseResult:
    """冻结一个系统（发布闸门 + 内容寻址产物）。

    ``checklist``：交付件清单阈值（F4；判定项与 gaps 共用）。
    缺省不设阈值（v0 清单 = 只要机械检查通过）。
    """
    repo_root = system_root.parent.parent
    artifacts_root = artifacts_root or (repo_root / "plate_artifacts")
    if not system_root.is_dir():
        return ReleaseResult(success=False, message=f"系统目录不存在: {system_root}")
    # 评审 P0-12:签发人必填(8.2 ④「人签发」,空值拒绝)
    if not signed_by or not signed_by.strip():
        return ReleaseResult(success=False, message="签发人(signed_by)不可为空")

    # ── 装载（working 树;common 参照随引用系统一并冻结,N3）──
    deliverables: list[Deliverable] = [
        parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
        for md in sorted(system_root.rglob("*.md"))
    ]
    common_terms: dict[str, Term] = {}
    common_review: dict[str, bool] = {}
    common_root = system_root.parent / "common"
    if common_root.is_dir() and system_root.name != "common":
        for md in sorted(common_root.rglob("*.md")):
            d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
            for b in d.blocks("term"):
                for m in b.models():
                    if isinstance(m, Term):
                        common_terms[m.id] = m
                        common_review[m.id] = (b.review == "reviewed")

    # ── ① 机械检查 ──
    types = load_types(repo_root / "types" / "types.yaml")
    report = ValidationReport()
    endpoints: list[EndpointSpec] = []
    statements: list[Statement] = []
    terms: dict[str, Term] = {}
    reviewed: list[tuple[str, Any]] = []   # 只收 reviewed(8v)
    statement_ids: set[str] = set()

    for d in deliverables:
        validate_deliverable(d, types=types, report=report)
        for b in d.blocks():
            for m in b.models():
                if isinstance(m, EndpointSpec):
                    endpoints.append(m)
                    if b.review == "reviewed":
                        reviewed.append(("endpoint", m))
                elif isinstance(m, Statement):
                    if m.id in statement_ids:
                        report.add(Finding(
                            "F3", "blocking", f"片段 id {m.id!r} 系统内重复"))
                    statement_ids.add(m.id)
                    statements.append(m)
                    if b.review == "reviewed":
                        reviewed.append(("statement", m))
                elif isinstance(m, Term):
                    terms[m.id] = m
                    if b.review == "reviewed":
                        reviewed.append(("term", m))

    ep_ids = [e.id for e in endpoints]
    dup_eps = {i for i in ep_ids if ep_ids.count(i) > 1}
    if dup_eps:
        report.add(Finding(
            "F3", "blocking", f"接口 id 系统内重复: {sorted(dup_eps)[:3]}"))

    # 块信封映射(评审 P0-15):区分「词条不存在」与「词条为 draft」
    term_block_review: dict[str, bool] = {}
    for d in deliverables:
        for b in d.blocks("term"):
            for m in b.models():
                if isinstance(m, Term):
                    term_block_review[m.id] = (b.review == "reviewed")
    term_block_review.update(common_review)

    validate_terms(
        terms.values(), system_id=system_root.name,
        common_ids=set(common_terms), report=report,
    )
    validate_references(
        endpoints, statements, terms, common_terms=common_terms, report=report,
    )
    validate_consistency(endpoints, statements, report=report)

    # F4:交付件清单阈值(判定项与 gaps 共用)
    from gimbal_plate.dialect.gaps import gap_items
    items = gap_items(endpoints, statements, terms, common_terms)
    for key, minimum in (checklist or {}).items():
        actual = items.get(key)
        if actual is not None and actual < minimum:
            report.add(Finding(
                "F4", "blocking",
                f"交付件清单: {key} = {actual} < 阈值 {minimum}",
            ))

    if report.blocking:
        return ReleaseResult(
            success=False,
            message=f"发布闸门未过: {len(report.blocking)} 条阻塞"
                    f"(首条: {report.blocking[0].message})",
            report=report,
        )
    # 8.2 ②(评审 P0-13):C 类不一致须经矫正变更处理,否则阻塞发布;
    # correction_log 记 finding 供矫正定位,清零后方可发出。
    if report.corrections:
        return ReleaseResult(
            success=False,
            message=f"C 类一致性未处理: {len(report.corrections)} 条"
                    f"(首条: {report.corrections[0].message[:80]})",
            report=report,
        )

    # ── ②③ 冻结范围与引用闭包(8v,评审 P0-15 强化:闭包传递)──
    # 被(传递地)引用到的词条必须 reviewed;沿 refers/父节点/replaced_by
    # 传递展开。common 词条(N3):只冻结**被引用到的**子集且须 reviewed,
    # 未被引用的不进 manifest;draft 的 common 词条被引用即阻塞。
    from gimbal_plate.dialect.validation import _parent_of

    def _term_edges(tid: str) -> list[str]:
        t_ = terms.get(tid) or common_terms.get(tid)
        if t_ is None:
            return []
        out: list[str] = []
        if t_.refers:
            out.append(t_.refers)
        if t_.replaced_by:
            out.append(t_.replaced_by)
        parent = _parent_of(tid)
        if parent:
            out.append(parent)
        return out

    frozen_ids = {m.id for kind, m in reviewed if kind == "term"}
    common_frozen: set[str] = set()
    closure: list[tuple[str, str]] = []
    visited: set[str] = set()
    queue: list[tuple[str, str]] = []
    for kind, m in reviewed:
        refs: list[str] = []
        if isinstance(m, EndpointSpec):
            refs = [r for r in (m.capability, *m.consumes, *m.produces) if r]
        elif isinstance(m, Statement):
            for v in m.slots.values():
                if isinstance(v, str):
                    refs.append(v)
                elif isinstance(v, list):
                    refs.extend(x for x in v if isinstance(x, str))
        for r in refs:
            queue.append((getattr(m, "id", "?"), r))
    while queue:
        owner, tid = queue.pop()
        if tid in visited:
            continue
        visited.add(tid)   # 边始终展开:种子(reviewed)也不例外——传递引用仍要查
        if tid not in terms and tid not in common_terms:
            closure.append((owner, tid))   # 不存在(S2 已报,双保险)
            continue
        if not term_block_review.get(tid, False):
            closure.append((owner, tid))   # draft 词条被待冻结内容引用
            continue
        if tid in common_terms:
            common_frozen.add(tid)
        else:
            frozen_ids.add(tid)
        queue.extend((owner, e) for e in _term_edges(tid))
    if closure:
        return ReleaseResult(
            success=False,
            message=(
                f"引用闭包(8v)未闭合: {len(closure)} 处待冻结内容引用"
                f"未冻结词条(首条: {closure[0][0]} → {closure[0][1]})"
            ),
            report=report,
        )

    # ── 冻结(评审 P0-16:release_id 目录冲突重试防并发覆盖)──
    releases_dir = artifacts_root / system_root.name / "releases"
    release_id = _next_release_id(releases_dir)
    manifest_dir = releases_dir / release_id
    for _attempt in range(8):
        try:
            manifest_dir.mkdir(parents=True)
            break
        except FileExistsError:
            release_id = _next_release_id(releases_dir)
            manifest_dir = releases_dir / release_id
    else:
        return ReleaseResult(success=False, message="release_id 竞争重试耗尽")
    freeze_list = list(reviewed) + [
        ("term", common_terms[mid]) for mid in sorted(common_frozen)
    ]
    object_entries = _freeze_objects(artifacts_root, freeze_list)
    call_projections = {
        m.id: _call_projection(m)
        for kind, m in reviewed if kind == "endpoint"
    }
    manifest = {
        "system": system_root.name,
        "release_id": release_id,
        "released_at": datetime.now(timezone.utc).isoformat(),
        "signed_by": signed_by,
        "dialect_version": DIALECT_VERSION,
        "m2_version": M2_VERSION,
        "types_version": 1,
        "checklist_applied": checklist or {},
        "objects": object_entries,
        "call_projections": call_projections,
        "correction_log": [f.to_dict() for f in report.corrections],
        "summary": {
            "endpoints": sum(1 for k, _ in reviewed if k == "endpoint"),
            "statements": sum(1 for k, _ in reviewed if k == "statement"),
            "terms": sum(1 for k, _ in reviewed if k == "term")
            + len(common_frozen),
            "common_terms_frozen": len(common_frozen),
            "draft_skipped_endpoints": len(endpoints)
            - sum(1 for k, _ in reviewed if k == "endpoint"),
        },
    }
    (manifest_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1),
        encoding="utf-8", newline="\n",
    )
    return ReleaseResult(
        success=True, release_id=release_id, manifest=manifest, report=report,
        message=(
            f"冻结 {manifest['summary']['endpoints']} 接口 / "
            f"{manifest['summary']['statements']} 片段 / "
            f"{manifest['summary']['terms']} 词条"
        ),
    )


class PlateRelease:
    """兼容旧占位入口的薄壳;真实现见 :func:`release_system`。"""

    def release(self, *, version: str | None = None) -> ReleaseResult:
        _ = version
        repo = Path(__file__).resolve().parents[3]
        return release_system(repo / "systems" / "fin")


__all__ = ["DIALECT_VERSION", "M2_VERSION", "PlateRelease", "ReleaseResult",
           "release_system"]
