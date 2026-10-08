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
        对象 hash 清单 + call 投影清单 + 模板/方言/M2 版本
        (correction_log 已删——零 finding 才能发版,该字段恒空;见修订十一)

release_id = ``YYYY.MM.N``（年月 + 当月序号，系统内单调递增，N2 已定）。
磁盘增长与「变更量」成正比（未变化对象跨版本同 hash,manifest 天然 diff）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gimbal_plate.dialect import EndpointSpec, Statement, Term, object_hash
from gimbal_plate.dialect.validation import (
    Finding,
    ValidationReport,
    load_types,
    validate_system_tree,
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
    # X3(第六轮,N3):common 不单独发版——被引用的 common 对象随引用
    # 系统的 manifest 冻结;common 自身无独立版本语义。
    if system_root.name == "common":
        return ReleaseResult(
            success=False,
            message="common 不单独发版(N3):被引用的 common 对象随引用系统的 manifest 冻结")

    # ── 装载 + ① 机械检查(J1,第五轮:与 check 同一引擎)──
    # 此前 release 自带一套装配,弱于 check(不跑树级 F3/路由键/J3);
    # 现与 validate_system_tree 共用 collect_system_tree 唯一装配点,
    # 发布闸门只保留自己特有的步骤(签发/F4/闭包/冻结)。
    from gimbal_plate.dialect.parser import DialectError
    from gimbal_plate.dialect.validation import collect_system_tree

    types = load_types(repo_root / "types" / "types.yaml")
    try:
        tree = collect_system_tree(system_root)
    except DialectError as e:
        # J5 残留(第六轮):方言错误也带 report(F0 finding),HTTP 422
        # 的 details 里可见 findings,与 check 的口径一致
        report = ValidationReport()
        report.add(Finding("F0", "blocking", str(e),
                           source=e.source, line=e.line))
        return ReleaseResult(
            success=False, message=f"方言错误: {e}", report=report)
    report = validate_system_tree(system_root, types=types, tree=tree)
    endpoints, statements = tree.endpoints, tree.statements
    terms, common_terms = tree.terms, tree.common_terms
    reviewed, term_block_review = tree.reviewed, dict(tree.term_block_review)

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
    # 清零后方可发出(revision-11 拍板:correction_log 字段删除——发布
    # 闸门只放行零 finding 的 release,该字段在已发布 manifest 里恒为空,
    # 属死字段;「记录矫正变更引用」随 C 闸门语义成熟再回填,S1.5 清单)。
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
    # 闭包起点 = **全部 reviewed 词条**(评审 R4):此前种子只含 reviewed
    # 块对词条的引用,未被块引用的 reviewed 词条自身 refers 到 draft、
    # 或父节点是 draft,都漏检照样发版。reviewed 词条自己的边也是待冻结
    # 内容的引用,同样须闭合。
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
        elif isinstance(m, Term):
            refs = _term_edges(m.id)
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
    # O1(第七轮/R1):freeze_list 与空检查在 mkdir **之前**——空发版被拒
    # 时不创建目录、不占用 release 号(此前连拒两次会留下 2026.10.1/.2
    # 空目录,把真实发版的编号挤后,还会让 diff 崩在无 manifest 的目录上)。
    freeze_list = list(reviewed) + [
        ("term", common_terms[mid]) for mid in sorted(common_frozen)
    ]
    # X3(第六轮):0 个对象的「空 release」拒绝——manifest 无内容、
    # 序号却被占用,还会把后续真实 release 的编号挤后。
    if not freeze_list:
        return ReleaseResult(
            success=False,
            message="无可冻结对象(reviewed 块为空且无被引用的 common 词条)"
                    "——空 release 拒绝发出",
            report=report)
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


__all__ = ["DIALECT_VERSION", "M2_VERSION", "ReleaseResult", "release_system"]
