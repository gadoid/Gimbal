"""release 读取侧（版本模型 v1.4 第 7 节；Release v4.4 §4；开发计划 T1.7）。

- **ref 三写法**（版本模型 §7）：``<line>#<n>``（精确修订）/ ``<line>``
  （该线最新修订）/ ``working``（缺省）。平台侧强制精确修订属接口约束
  （``REF_REQUIRED``），由调用方保证。
- **修订快照装载**（Release 4.1）：读 manifest → 按 hash 取对象逐个校验
  → 用当前知识侧模型水合 → 构建仅含该系统的 :class:`PlateRegistry`
  （``snapshot_id = <系统>@<line>#<n>``）。hash 不符报
  ``RELEASE_CORRUPT``；知识侧代际不同报 ``RELEASE_M2_INCOMPATIBLE``。
  ``gimbal:defaults`` 不冻结（3.1），修订快照不含 defaults 派生的 dim。
- **差异**（Release 4.3 / R7）：对象级（增删改）＋变更接口的**变化部位**
  （``service`` / ``binding`` / ``request`` / ``responses``，binding 内
  path 占位符集合单列）；``a``/``b`` 可跨版本线，也可与 working 比。
- **生效修订**（Release 4.4）：可用集合语义（版本模型 4.2，D-5）——
  线内、场景用到的接口 ``shape_hash`` 与已验证修订全同的修订集合
  （不必连续），生效修订 = 集合中最新的一个。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gimbal_plate.dialect import (
    EndpointSpec,
    Statement,
    Term,
    object_hash,
    shape_hash,
    shape_projection,
)
from gimbal_plate.release.release import (
    M2_VERSION,
    latest_revision_manifest,
    resolve_artifacts_root,
)

_WORKING = "working"


class ReleaseReadError(Exception):
    """读取侧错误：code 即 HTTP 错误码（release_not_found 等）。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def parse_ref(ref: str) -> tuple[str, str | None, int | None]:
    """``working`` | ``<line>`` | ``<line>#<n>`` → (kind, line, n)。"""
    ref = (ref or "").strip()
    if not ref or ref == _WORKING:
        return (_WORKING, None, None)
    if "#" in ref:
        line, _, n = ref.rpartition("#")
        if not line or not n.isdigit():
            raise ReleaseReadError(
                "invalid_ref", f"ref {ref!r} 非法(须为 <line>#<n>)")
        return ("revision", line, int(n))
    return ("line", ref, None)


def load_manifest(root: Path, system: str, line: str, n: int) -> dict[str, Any]:
    p = root / system / "lines" / line / str(n) / "manifest.json"
    if not p.is_file():
        raise ReleaseReadError(
            "release_not_found", f"修订 {system}@{line}#{n} 不存在")
    return json.loads(p.read_text(encoding="utf-8"))


def list_lines(root: Path, system: str) -> list[dict[str, Any]]:
    """版本线列表（按各线最新修订的 released_at 排序）。"""
    lines_dir = root / system / "lines"
    if not lines_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for line_dir in sorted(lines_dir.iterdir()):
        if not line_dir.is_dir():
            continue
        nums = sorted(int(p.name) for p in line_dir.iterdir()
                      if p.is_dir() and p.name.isdigit())
        if not nums:
            continue
        m = load_manifest(root, system, line_dir.name, nums[-1])
        out.append({
            "line": line_dir.name,
            "revisions": len(nums),
            "latest": f"{line_dir.name}#{nums[-1]}",
            "line_scheme": m.get("line_scheme"),
            "line_service": m.get("line_service"),
            "predecessor_line": m.get("predecessor_line"),
            "latest_released_at": m.get("released_at"),
        })
    return sorted(out, key=lambda d: str(d.get("latest_released_at") or ""))


def list_revisions(root: Path, system: str, line: str) -> list[dict[str, Any]]:
    line_dir = root / system / "lines" / line
    if not line_dir.is_dir():
        raise ReleaseReadError(
            "release_not_found", f"版本线 {system}@{line} 不存在")
    out = []
    for p in sorted(line_dir.iterdir()):
        if not (p.is_dir() and p.name.isdigit()):
            continue
        m = load_manifest(root, system, line, int(p.name))
        out.append({
            "revision": f"{line}#{p.name}",
            "released_at": m.get("released_at"),
            "signed_by": m.get("signed_by"),
            "corrections": m.get("corrections", []),
            "warnings": len(m.get("warnings", [])),
            "summary": m.get("summary", {}),
        })
    return out


def resolve_revision(root: Path, system: str, ref: str,
                     ) -> tuple[str, int, dict[str, Any]]:
    """ref → (line, n, manifest)；working ref 不在此处理（调用方分流）。"""
    kind, line, n = parse_ref(ref)
    if kind == _WORKING:
        raise ReleaseReadError("invalid_ref", "working 不是修订 ref")
    if kind == "line":
        latest = latest_revision_manifest(root, system, line or "")
        if latest is None:
            raise ReleaseReadError(
                "release_not_found", f"版本线 {system}@{line} 不存在")
        n, m = latest
        return line or "", n, m          # type: ignore[return-value]
    m = load_manifest(root, system, line or "", int(n or 0))   # type: ignore[arg-type]
    return line or "", int(n or 0), m    # type: ignore[arg-type]


@dataclass
class RevisionSnapshot:
    """一个修订的水合产物：注册表（查询面）+ 全量对象（diff/resolve 用）。"""

    system: str
    line: str
    n: int
    manifest: dict[str, Any]
    endpoints: dict[str, EndpointSpec] = field(default_factory=dict)
    statements: dict[str, Statement] = field(default_factory=dict)
    terms: dict[str, Term] = field(default_factory=dict)
    services: list[dict[str, Any]] = field(default_factory=list)
    projections: dict[str, dict[str, Any]] = field(default_factory=dict)
    _registry: Any = None

    @property
    def ref(self) -> str:
        return f"{self.line}#{self.n}"

    def registry(self) -> Any:
        """水合注册表（懒建；仅本系统，snapshot_id = <系统>@<line>#<n>）。"""
        if self._registry is None:
            from gimbal_plate.loader import register_core_dims
            from gimbal_plate.registry import PlateRegistry

            reg = PlateRegistry()
            register_core_dims(reg)
            reg.declare_system(self.system)
            from gimbal_plate.schema.service_definition import (
                ServiceDefinition,
            )
            for svc in self.services:
                reg.register_service(ServiceDefinition.model_validate(svc))
            for ep in self.endpoints.values():
                reg.register_endpoint(ep)
            reg.snapshot_id = f"{self.system}@{self.ref}"  # type: ignore[attr-defined]
            self._registry = reg
        return self._registry

    def endpoint_shapes(self) -> dict[str, str]:
        return {eid: shape_hash(ep) for eid, ep in self.endpoints.items()}


def _read_envelope(root: Path, h: str, expect_type: str) -> dict[str, Any]:
    p = root / "objects" / f"{h}.json"
    if not p.is_file():
        raise ReleaseReadError(
            "release_corrupt", f"对象 {h[:12]}… 不在对象池(RELEASE_CORRUPT)")
    envelope = json.loads(p.read_text(encoding="utf-8"))
    if envelope.get("type") != expect_type:
        raise ReleaseReadError(
            "release_corrupt",
            f"对象 {h[:12]}… 信封类型 {envelope.get('type')!r} ≠ {expect_type!r}")
    return envelope


def load_snapshot(root: Path, system: str, line: str, n: int,
                  ) -> RevisionSnapshot:
    """读 manifest → 逐对象校验 hash → 水合（Release 4.1）。"""
    m = load_manifest(root, system, line, n)
    if str(m.get("m2_version")) != M2_VERSION:
        raise ReleaseReadError(
            "release_m2_incompatible",
            f"{system}@{line}#{n} 的知识侧代际 {m.get('m2_version')!r} "
            f"与当前 {M2_VERSION!r} 不同(RELEASE_M2_INCOMPATIBLE)")
    snap = RevisionSnapshot(system=system, line=line, n=n, manifest=m)
    for e in m.get("objects", []):
        h, t = e["hash"], e.get("type")
        envelope = _read_envelope(root, h, t)
        data = envelope["data"]
        if t == "endpoint":
            ep = EndpointSpec.model_validate(data)
            if object_hash(ep) != h:
                raise ReleaseReadError(
                    "release_corrupt", f"接口 {e.get('id')} hash 校验失败")
            snap.endpoints[e["id"]] = ep
        elif t == "statement":
            st = Statement.model_validate(data)
            if object_hash(st) != h:
                raise ReleaseReadError(
                    "release_corrupt", f"片段 {e.get('id')} hash 校验失败")
            snap.statements[e["id"]] = st
        elif t == "term":
            tm = Term.model_validate(data)
            if object_hash(tm) != h:
                raise ReleaseReadError(
                    "release_corrupt", f"词条 {e.get('id')} hash 校验失败")
            snap.terms[e["id"]] = tm
        elif t == "service":
            import hashlib
            rehash = hashlib.sha256(json.dumps(
                data, ensure_ascii=False, separators=(",", ":"),
                sort_keys=True).encode("utf-8")).hexdigest()
            if rehash != h:
                raise ReleaseReadError(
                    "release_corrupt", f"服务 {e.get('id')} hash 校验失败")
            snap.services.append(data)
    for eid, ph in (m.get("call_projections") or {}).items():
        snap.projections[eid] = _read_envelope(root, ph, "call")["data"]
    return snap


def snapshot_from_registry(reg: Any, system: str) -> RevisionSnapshot:
    """working 侧的伪快照（diff 的 working 端点；只含注册表有的对象）。"""
    snap = RevisionSnapshot(system=system, line=_WORKING, n=0,
                            manifest={"system": system})
    for ep in getattr(reg, "endpoints", []) or []:
        if getattr(ep, "system", system) == system:
            snap.endpoints[ep.id] = ep
    return snap


def _path_placeholders(path: str) -> set[str]:
    import re
    return set(re.findall(r"\{([^}]+)\}", path or ""))


def _endpoint_changed_parts(a: EndpointSpec, b: EndpointSpec) -> dict[str, Any]:
    """变化部位（Release 4.3）：service / binding / request / responses。"""
    parts: dict[str, Any] = {}
    if a.service != b.service:
        parts["service"] = {"from": a.service, "to": b.service}
    pa, pb = shape_projection(a), shape_projection(b)
    if pa.get("binding") != pb.get("binding"):
        detail: dict[str, Any] = {"from": pa.get("binding"), "to": pb.get("binding")}
        path_a = (pa.get("binding") or {}).get("path", "")
        path_b = (pb.get("binding") or {}).get("path", "")
        if _path_placeholders(path_a) != _path_placeholders(path_b):
            detail["path_placeholders"] = {
                "from": sorted(_path_placeholders(path_a)),
                "to": sorted(_path_placeholders(path_b)),
            }
        parts["binding"] = detail
    if pa.get("request") != pb.get("request"):
        parts["request"] = {"from": pa.get("request"), "to": pb.get("request")}
    if pa.get("responses") != pb.get("responses"):
        parts["responses"] = {"from": pa.get("responses"),
                              "to": pb.get("responses")}
    if not parts:
        parts["description_only"] = True
    return parts


def diff_snapshots(sa: RevisionSnapshot, sb: RevisionSnapshot,
                   ) -> dict[str, Any]:
    """对象级差异 + 变化接口的部位（a → b）。"""
    ea = {(e["type"], e["id"]): e for e in sa.manifest.get("objects", [])}
    if not ea and sa.endpoints:
        # working 伪快照没有 manifest objects——按水合对象即时取 hash
        ea = {("endpoint", eid): {"hash": object_hash(ep)}
              for eid, ep in sa.endpoints.items()}
    eb = {(e["type"], e["id"]): e for e in sb.manifest.get("objects", [])}
    if not eb and sb.endpoints:
        eb = {("endpoint", eid): {"hash": object_hash(ep)}
              for eid, ep in sb.endpoints.items()}

    added = sorted(f"{t}.{i}" for k in eb.keys() - ea.keys() for t, i in [k])
    removed = sorted(f"{t}.{i}" for k in ea.keys() - eb.keys() for t, i in [k])
    changed: dict[str, Any] = {}
    for key in ea.keys() & eb.keys():
        if ea[key].get("hash") != eb[key].get("hash"):
            t, i = key
            entry: dict[str, Any] = {"type": t}
            if t == "endpoint" and i in sa.endpoints and i in sb.endpoints:
                entry["parts"] = _endpoint_changed_parts(
                    sa.endpoints[i], sb.endpoints[i])
            changed[f"{t}.{i}"] = entry
    return {"from": sa.ref if sa.line != _WORKING else _WORKING,
            "to": sb.ref if sb.line != _WORKING else _WORKING,
            "added": added, "removed": removed, "changed": changed}


def resolve_effective(
    root: Path, system: str, verified: str,
    endpoints_used: list[str],
) -> dict[str, Any]:
    """生效修订（版本模型 4.2 / Release 4.4，可用集合语义 D-5）。

    返回 ``{effective, available, changed_endpoints}``：``effective`` =
    可用集合中最新的修订；``changed_endpoints`` = 最新修订上、场景用到的
    接口中与已验证修订 shape 不同的（待线内修正适配的提示依据）。
    """
    kind, line, n = parse_ref(verified)
    if kind != "revision":
        raise ReleaseReadError(
            "invalid_ref", f"已验证修订须为 <line>#<n>，得到 {verified!r}")
    load_manifest(root, system, line or "", int(n or 0))   # 存在性校验
    latest = latest_revision_manifest(root, system, line or "")
    if latest is None:
        raise ReleaseReadError("release_not_found", f"版本线 {line} 无修订")
    latest_n = latest[0]
    used = set(endpoints_used)
    # 逐修订计算 shape（只依赖 manifest 的 shape_hash，无需水合对象）
    shapes_by_rev: dict[int, dict[str, str | None]] = {}
    for rev_n in range(int(n or 0), latest_n + 1):
        m = load_manifest(root, system, line or "", rev_n)
        shapes_by_rev[rev_n] = {
            e["id"]: e.get("shape_hash")
            for e in m.get("objects", []) if e.get("type") == "endpoint"
        }
    base_s = shapes_by_rev[int(n or 0)]
    available = [
        rev_n for rev_n, shapes in shapes_by_rev.items()
        if all(shapes.get(eid) == base_s.get(eid) for eid in used)
    ]
    effective = max(available)
    latest_s = shapes_by_rev[latest_n]
    changed = sorted(
        eid for eid in used if latest_s.get(eid) != base_s.get(eid))
    return {"effective": f"{line}#{effective}", "available": available,
            "changed_endpoints": changed}


__all__ = [
    "ReleaseReadError", "RevisionSnapshot",
    "diff_snapshots", "list_lines", "list_revisions", "load_manifest",
    "load_snapshot", "parse_ref", "resolve_artifacts_root",
    "resolve_effective", "resolve_revision", "snapshot_from_registry",
]
