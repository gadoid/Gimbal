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
    """对象落全局池(已存在即跳过——hash 相同内容必相同)。返回清单条目。"""
    objects_dir = artifacts_root / "objects"
    objects_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for kind, model in models:
        h = object_hash(model)
        obj_path = objects_dir / f"{h}.json"
        if not obj_path.exists():
            payload = {"kind": kind, **model.model_dump(mode="json")}
            obj_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=1),
                encoding="utf-8", newline="\n",
            )
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

    # ── 装载（working 树;common 参照随引用系统一并冻结,N3）──
    deliverables: list[Deliverable] = [
        parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
        for md in sorted(system_root.rglob("*.md"))
    ]
    common_terms: dict[str, Term] = {}
    common_root = system_root.parent / "common"
    if common_root.is_dir() and system_root.name != "common":
        for md in sorted(common_root.rglob("*.md")):
            d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
            for b in d.blocks("term"):
                for m in b.models():
                    if isinstance(m, Term):
                        common_terms[m.id] = m

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

    # ── ②③ 冻结范围与引用闭包(8v)──
    frozen_term_ids = {
        m.id for kind, m in reviewed if kind == "term"
    } | set(common_terms)
    closure: list[tuple[str, str]] = []
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
        for ref in refs:
            if ref and ref not in frozen_term_ids:
                closure.append((getattr(m, "id", "?"), ref))
    if closure:
        return ReleaseResult(
            success=False,
            message=(
                f"引用闭包(8v)未闭合: {len(closure)} 处待冻结内容引用"
                f"未冻结词条(首条: {closure[0][0]} → {closure[0][1]})"
            ),
            report=report,
        )

    # ── 冻结 ──
    release_id = _next_release_id(
        artifacts_root / system_root.name / "releases"
    )
    object_entries = _freeze_objects(artifacts_root, reviewed)
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
        "objects": object_entries,
        "call_projections": call_projections,
        "correction_log": [f.to_dict() for f in report.corrections],
        "summary": {
            "endpoints": sum(1 for k, _ in reviewed if k == "endpoint"),
            "statements": sum(1 for k, _ in reviewed if k == "statement"),
            "terms": sum(1 for k, _ in reviewed if k == "term"),
            "draft_skipped_endpoints": len(endpoints)
            - sum(1 for k, _ in reviewed if k == "endpoint"),
        },
    }
    manifest_dir = artifacts_root / system_root.name / "releases" / release_id
    manifest_dir.mkdir(parents=True, exist_ok=True)
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
