"""Generic grammar router (ADR 0002 §D1 / §D2).

10 handlers implementing the M6 URL grammar:
  /api/{dim}                                          GET  list
  /api/{dim}/{id}                                     GET  detail
  /api/{dim}/{id}/action/{name}                       GET  object action
  /api/{dim}/{id}/action/{name}                       POST object action
  /api/{dim}/action/{name}                            POST dim-node action
  /api/systems/{system}/{dim}                         GET  list_for_system
  /api/systems/{system}/{dim}/{id}                    GET  detail_for_system
  /api/systems/{system}/{dim}/tree                    GET  tree_for_system
  /api/systems/{system}/{dim}/{id}/action/{name}      POST object action_for_system
  /api/systems/{system}/{dim}/action/{name}           POST dim-node action_for_system

FastAPI route registration order matters (see ADR 0002 §D2):
  1. /systems/{system}/{dim}/...   MUST come before /{dim}/{id}
  2. /api/{dim}/action/{name}      MUST come before /api/{dim}/{id}
Otherwise FastAPI matches /systems as dim="systems", or eats action names into {dim_id}.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import ValidationError

from gimbal_plate import export
from gimbal_plate.http.envelope import (
    ErrorCode,
    PlateHTTPError,
    ok_response,
)
from gimbal_plate.registry import PlateRegistry
from gimbal_plate.schema.scenario import Scenario
from gimbal_plate.service.field_defaults import compute_field_defaults
from gimbal_plate.service.failed_resolver import resolve_failed_criteria
from gimbal_plate.service.paths_resolver import resolve_paths
from gimbal_plate.service.query_views import build_query_view_index
from gimbal_plate.service.system_from_service import system_from_service


router = APIRouter(prefix="/api", tags=["grammar"])


# ── Helpers ──────────────────────────────────────────────────────


import json
from functools import lru_cache


def _registry(request: Request, system: str | None = None) -> PlateRegistry:
    """查询注册表——ref 感知的唯一取用点（版本模型 §7 / Release 4.1–4.2）。

    无 ``?ref=`` 或 ``ref=working`` → 进程的 working 注册表；带精确/线
    ref 且调用方提供系统作用域 → 装载该系统该修订的快照注册表（按修订
    缓存，原子性由装载函数保证）。RS1 起 system 作用域路由与 endpoint
    id 前缀路由支持 ref；全局路由不带系统，ref 无从解析。
    """
    ref = (request.query_params.get("ref") or "").strip()
    working = not ref or ref == "working"
    if working or not system:
        reg: PlateRegistry | None = getattr(request.app.state, "registry", None)
        if reg is None:
            raise PlateHTTPError(
                http_status=503,
                code=ErrorCode.REGISTRY_UNAVAILABLE,
                message="plate registry is not initialised",
            )
        return reg
    from gimbal_plate.release import read as release_read
    from gimbal_plate.release.release import resolve_artifacts_root

    # 修订快照缓存（容量淘汰,Release 4.1:修订不可变、按修订缓存整个
    # 快照,超容量 LRU 淘汰最旧条目;设计未定具体数字,取 64）
    cache: dict | None = getattr(request.app.state, "revision_registries", None)
    if cache is None:
        cache = {}
        request.app.state.revision_registries = cache
    _REVISION_CACHE_MAX = 64

    def _cache_put(key, snap):
        if len(cache) >= _REVISION_CACHE_MAX:
            # 简单 FIFO 淘汰(dict 保插入序,删最早条目;修订不可变,
            # 淘汰只是丢缓存,下次访问重新装载)
            for oldest in list(cache):
                cache.pop(oldest)
                break
        cache[key] = snap
    try:
        root = resolve_artifacts_root()
    except RuntimeError as e:
        raise PlateHTTPError(
            http_status=503, code=ErrorCode.REGISTRY_UNAVAILABLE,
            message=str(e))
    try:
        line, n, _ = release_read.resolve_revision(root, system, ref)
        snap = cache.get((system, line, n))
        if snap is None:
            snap = release_read.load_snapshot(root, system, line, n)
            _cache_put((system, line, n), snap)
    except release_read.ReleaseReadError as e:
        raise _read_error(e)
    return snap.registry()


_READ_ERROR_HTTP = {
    "release_not_found": (404, ErrorCode.RELEASE_NOT_FOUND),
    "release_corrupt": (409, ErrorCode.RELEASE_CORRUPT),
    "release_m2_incompatible": (409, ErrorCode.RELEASE_M2_INCOMPATIBLE),
    "invalid_ref": (400, ErrorCode.INVALID_REF),
}


def _read_error(e: Any) -> PlateHTTPError:
    status, code = _READ_ERROR_HTTP.get(
        getattr(e, "code", ""), (400, ErrorCode.INVALID_REF))
    return PlateHTTPError(http_status=status, code=code,
                          message=getattr(e, "message", str(e)))


def _service_of_system(reg: PlateRegistry, system: str) -> str:
    """系统内任一服务名(声明闸取 kind 用;无服务 → 空串,按未登记处理)。"""
    for sd in reg.iter_services_for_system(system):
        return sd.name
    return ""


def _resolve_system(reg: PlateRegistry, system: str) -> None:
    """Raise SYSTEM_NOT_FOUND if no endpoint under ``system`` exists."""
    if not reg.has_system(system):
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.SYSTEM_NOT_FOUND,
            message=f"system '{system}' has no registered endpoints",
        )


def _pass_through_kwargs(body: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    """Return a subset of ``body`` containing only the keys explicitly present.

    Why not ``{k: body.get(k) for k in keys}``?
        Some consumer request models use ``extra="forbid"`` and reject keys
        whose value is ``None`` (e.g. ``GimbalConsumerRequest`` forbids
        ``endpoints=None`` even though the field is absent by default).
        ``body.get(k)`` returns ``None`` for missing keys, which would then
        be forwarded to the consumer model and trip validation. Using
        ``k in body`` keeps the contract: "the caller explicitly sent this
        field, so we forward it as-is".
    """
    return {k: body[k] for k in keys if k in body}


# ── Handlers — system-scoped first (registration order matters) ──


# ── 版本模型读取侧（Release v4.4 §4.3–4.4；T1.7）────────────────────
# 单数 /system/ 路径族：不与 /systems/{system}/{dim} 泛型路由冲突。
# ref 中的 '#' 由调用方按 URL 规范百分号编码（%23），或用 <line> /
# working 两种无 '#' 写法。


def _artifacts_root_or_503(request: Request) -> Any:
    from gimbal_plate.release.release import resolve_artifacts_root

    try:
        return resolve_artifacts_root()
    except RuntimeError as e:
        raise PlateHTTPError(
            http_status=503, code=ErrorCode.REGISTRY_UNAVAILABLE,
            message=str(e))


@router.get("/system/{system_id}/lines")
def system_lines(system_id: str, request: Request) -> dict[str, Any]:
    """版本线列表（版本模型 2.4；`line_scheme` 以线内最新修订为准）。"""
    from gimbal_plate.release import read as release_read

    root = _artifacts_root_or_503(request)
    items = release_read.list_lines(root, system_id)
    return ok_response({"items": items, "total": len(items)}, dim="system")


@router.get("/system/{system_id}/lines/{line}/revisions")
def system_line_revisions(system_id: str, line: str,
                          request: Request) -> dict[str, Any]:
    from gimbal_plate.release import read as release_read

    root = _artifacts_root_or_503(request)
    try:
        items = release_read.list_revisions(root, system_id, line)
    except release_read.ReleaseReadError as e:
        raise _read_error(e)
    return ok_response({"items": items, "total": len(items)}, dim="system")


@router.get("/system/{system_id}/revisions/{line}/{n}")
def system_revision_manifest(system_id: str, line: str, n: int,
                             request: Request) -> dict[str, Any]:
    from gimbal_plate.release import read as release_read

    root = _artifacts_root_or_503(request)
    try:
        m = release_read.load_manifest(root, system_id, line, n)
    except release_read.ReleaseReadError as e:
        raise _read_error(e)
    return ok_response({"item": m, "total": 1}, dim="system")


@router.get("/system/{system_id}/diff/{a}/{b}")
def system_revision_diff(system_id: str, a: str, b: str,
                         request: Request) -> dict[str, Any]:
    """对象级差异 + 变化接口的变化部位（Release 4.3 / R7）。

    ``a``/``b`` 可跨版本线，也可为 ``working``（与进程当前树比）；
    ``#`` 需编码为 ``%23``，或用 ``<line>``（最新修订）写法。
    """
    from gimbal_plate.release import read as release_read

    root = _artifacts_root_or_503(request)

    def _snap(ref: str) -> Any:
        if ref == "working":
            return release_read.snapshot_from_registry(
                _registry(request), system_id)
        try:
            ln, nn, _m = release_read.resolve_revision(root, system_id, ref)
            return release_read.load_snapshot(root, system_id, ln, nn)
        except release_read.ReleaseReadError as e:
            raise _read_error(e)

    return ok_response(
        {"item": release_read.diff_snapshots(_snap(a), _snap(b))},
        dim="system")


@router.get("/system/{system_id}/cold-archive")
def system_cold_archive(system_id: str, request: Request) -> dict[str, Any]:
    """冷化判定查询（Release v4.4 §9 / RS5）。

    查询参数：
    - referenced：逗号分隔的已验证修订（line#n,line#n,...）
    - pinned：逗号分隔的执行记录钉住修订

    返回可冷化修订列表（含 manifest 摘要）。
    """
    from gimbal_plate.release.cold_archive import list_cold_archivable
    from gimbal_plate.release.release import resolve_artifacts_root

    root = _artifacts_root_or_503(request)
    ref_raw = request.query_params.get("referenced", "")
    pin_raw = request.query_params.get("pinned", "")
    referenced = {system_id: [r.strip() for r in ref_raw.split(",") if r.strip()]} if ref_raw else {}
    pinned = {system_id: [r.strip() for r in pin_raw.split(",") if r.strip()]} if pin_raw else {}
    items = list_cold_archivable(
        root, referenced_revisions=referenced, pinned_revisions=pinned)
    # 只留本系统的
    items = [i for i in items if i["system"] == system_id]
    return ok_response({"items": items, "total": len(items)}, dim="system")


@router.get("/endpoint/{eid}/projection")
def endpoint_projection(eid: str, request: Request,
                        ref: str = Query("working")) -> dict[str, Any]:
    """call 投影只读查询（Release 4.8）：按修订返回，结果不可变可缓存。"""
    from gimbal_plate.release import read as release_read

    system = eid.split(".")[0]
    root = _artifacts_root_or_503(request)
    proj: dict[str, Any] | None = None
    try:
        if ref and ref != "working":
            ln, nn, _m = release_read.resolve_revision(root, system, ref)
            snap = release_read.load_snapshot(root, system, ln, nn)
            proj = snap.projections.get(eid)
        else:
            reg = _registry(request)
            spec = reg.index_for("endpoint")
            item = spec.index.get(eid) if spec else None
            if item is None:
                raise PlateHTTPError(
                    http_status=404, code=ErrorCode.DIM_ITEM_NOT_FOUND,
                    message=f"endpoint '{eid}' not found")
            from gimbal_plate.release.release import _call_projection
            proj = _call_projection(item)
    except release_read.ReleaseReadError as e:
        raise _read_error(e)
    if proj is None:
        raise PlateHTTPError(
            http_status=404, code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"endpoint '{eid}' has no call projection at {ref!r}")
    return ok_response({"item": proj, "ref": ref, "total": 1}, dim="endpoint")


# ── M2 框架 dim（M2 方案 v2.4 §4.3/§9.5；T1.3）──────────────────────
# literal 路由（须先于 /{dim} 泛型路由注册，同 query-views 的坑）。


@lru_cache(maxsize=1)
def _cached_m2_export():
    from gimbal_plate.export.m2_schema import export_m2
    return export_m2()


@router.get("/m2")
def m2_current() -> dict[str, Any]:
    """发布当前 M2 Schema 与 ``m2_hash`` / ``m2_generation``（4.3）。"""
    e = _cached_m2_export()
    return ok_response(
        {"schema": e.schema, "m2_hash": e.m2_hash,
         "m2_generation": e.m2_generation},
        dim="m2")


@router.post("/m2/action/migrate")
async def m2_migrate(body: dict) -> dict:
    """M2 §5.2:代际迁移纯函数——入参 {from_generation, kind, value}。

    kind 当前只支持 "definition"(Scenario dict);返回迁移后的值。
    迁移函数须随不兼容变更同一提交入库,未注册的代际 422。
    """
    from gimbal_plate.schema import M2_GENERATION
    from gimbal_plate.schema.migrate import migrate_definition

    from_gen = body.get("from_generation")
    kind = body.get("kind", "definition")
    value = body.get("value")
    if not isinstance(from_gen, int) or from_gen < 1:
        raise PlateHTTPError(
            http_status=422, code=ErrorCode.INVALID_ACTION,
            message=f"from_generation must be int ≥ 1, got {from_gen!r}")
    if kind != "definition":
        raise PlateHTTPError(
            http_status=422, code=ErrorCode.INVALID_ACTION,
            message=f"unsupported kind: {kind!r} (only 'definition')")
    if not isinstance(value, dict):
        raise PlateHTTPError(
            http_status=422, code=ErrorCode.INVALID_ACTION,
            message="value must be a dict (M2 Scenario instance)")
    if from_gen >= M2_GENERATION:
        return ok_response(
            {"value": value, "from_generation": from_gen,
             "to_generation": M2_GENERATION, "migrated": False},
            dim="m2")
    try:
        migrated = migrate_definition(value, from_gen)
    except ValueError as e:
        raise PlateHTTPError(
            http_status=422, code=ErrorCode.INVALID_ACTION,
            message=str(e)) from e
    return ok_response(
        {"value": migrated, "from_generation": from_gen,
         "to_generation": M2_GENERATION, "migrated": True},
        dim="m2")


@router.get("/m2/{m2_hash}")
def m2_by_hash(m2_hash: str, request: Request) -> dict[str, Any]:
    """按 hash 取历史 M2（9.5）：进程内当前 → 构件分支检出。"""
    from pathlib import Path as _P

    from gimbal_plate.export.m2_schema import export_m2

    current = export_m2()
    if m2_hash == current.m2_hash:
        return ok_response(
            {"schema": current.schema, "m2_hash": m2_hash,
             "m2_generation": current.m2_generation},
            dim="m2")
    try:
        from gimbal_plate.release.release import resolve_artifacts_root
        root = resolve_artifacts_root()
    except RuntimeError as e:
        raise PlateHTTPError(
            http_status=503, code=ErrorCode.REGISTRY_UNAVAILABLE,
            message=str(e))
    path = _P(root) / "objects" / f"{m2_hash}.json"
    if not path.is_file():
        raise PlateHTTPError(
            http_status=404, code=ErrorCode.M2_NOT_FOUND,
            message=f"M2 {m2_hash[:12]}… 不在当前进程与构件分支"
                    f"（M2_NOT_FOUND）")
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if envelope.get("type") != "m2":
        raise PlateHTTPError(
            http_status=404, code=ErrorCode.M2_NOT_FOUND,
            message=f"对象 {m2_hash[:12]}… 不是 M2 信封")
    return ok_response(
        {"schema": envelope["data"], "m2_hash": m2_hash},
        dim="m2")


@router.get("/ext")
def ext_snapshot() -> dict[str, Any]:
    """C 类快照全文（strategy/protocol/mode/plugin 等表，2.1）。"""
    from pathlib import Path as _P

    path = (_P(__file__).resolve().parents[1] / "selfdescribe"
            / "executor_ext.json")
    if not path.is_file():
        raise PlateHTTPError(
            http_status=503, code=ErrorCode.REGISTRY_UNAVAILABLE,
            message="executor_ext.json 不存在——运行 scripts/gen_m2.py "
                    "gen --targets ext 生成 C 类快照")
    return ok_response(json.loads(path.read_text(encoding="utf-8")),
                       dim="ext")


@router.get("/systems/{system}/{dim}/tree")
def tree_dim_for_system(
    system: str,
    dim: str,
    request: Request,
    depth: int = Query(2, ge=1, le=3),
) -> dict[str, Any]:
    """System-scoped tree view for the dim (e.g. ``GET /api/systems/fin/system/tree``).

    Generic handler: returns a per-dim tree representation. For ``system`` /
    ``service`` / ``endpoint`` the tree shape mirrors the corresponding
    pre-M6 routes (A2 / A3 tree view). Other dims return a flat list under
    ``items`` if they don't have a natural tree shape.
    """
    _ = depth  # reserved for future per-dim depth semantics
    reg = _registry(request, system)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    _resolve_system(reg, system)
    idx = spec.index
    items = idx.list_for_system(system)
    return ok_response(
        {"tree": items, "total": len(items)},
        dim=dim,
    )


# ── /full handlers (system-scoped first, then global) ────────────
#
# ADR 0002 §D-D5: ``/{dim}/full`` and ``/{dim}/{id}/full`` return the
# *full* contract (every schema field, including field-declaration metadata,
# sensitive credentials, and ``extra``-captured extension fields). When
# the dim didn't register a ``full_view_factory`` the endpoint returns
# ``501 admin_not_implemented`` — the dim chose to keep its light view
# as the only contract.
#
# Registration order (ADR 0002 §D2): ``/full`` paths MUST come before
# ``/{dim}/{id}`` otherwise ``/endpoint/full`` is parsed as
# ``dim="endpoint" id="full"``. The system-scoped /full routes are
# registered FIRST (right after the system-scoped ``/tree`` route) so
# that ``/api/systems/{system}/{dim}/full`` is not eaten by
# ``/api/systems/{system}/{dim}/{id}``.


def _require_full_factory(spec: Any, dim: str) -> None:
    """Raise 501 if the dim has no ``full_view_factory`` wired up."""
    if spec.full_view_factory is None:
        raise PlateHTTPError(
            http_status=501,
            code=ErrorCode.ADMIN_NOT_IMPLEMENTED,
            message=(
                f"dim '{dim}' has no full_view_factory; "
                f"/full endpoint is not available for this dim"
            ),
        )


def _to_full_view(spec: Any, item: Any) -> dict[str, Any]:
    """Render ``item`` through the dim's full_view_factory.

    The factory is owned by the :class:`DimSpec` (not the index), so we
    dispatch through ``spec`` and ``model_dump`` the resulting Pydantic
    view. This keeps the route unaware of each dim's payload shape.
    """
    view = spec.full_view_factory(item)
    return view.model_dump(mode="json", exclude_none=True)


# ── System-scoped /full (must precede /systems/{system}/{dim}/{id}) ─


@router.get("/systems/{system}/{dim}/full")
def list_full_dim_for_system(
    system: str, dim: str, request: Request
) -> dict[str, Any]:
    """System-scoped full list (every schema field per item)."""
    reg = _registry(request, system)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    _resolve_system(reg, system)
    _require_full_factory(spec, dim)
    raw_items = spec.index.list_for_system(system)
    items = [_to_full_view(spec, it) for it in raw_items]
    return ok_response({"items": items, "total": len(items)}, dim=dim)


@router.get("/systems/{system}/{dim}/{id}/full")
def get_full_dim_item_for_system(
    system: str, dim: str, id: str, request: Request  # noqa: A002
) -> dict[str, Any]:
    """System-scoped full detail for one item."""
    reg = _registry(request, system)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    _resolve_system(reg, system)
    _require_full_factory(spec, dim)
    item = spec.index.get(id)
    if item is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"{dim} '{id}' not found",
        )
    # Verify the item belongs to the requested system.
    # Use a key that uniquely identifies the item across all dims:
    #   - storage-backed dims (config / resource / scenario) key by registered id
    #   - endpoint has a stable `.id` attribute
    # We compare against the URL path param ``id`` directly — the index's
    # ``list_for_system`` may return objects without a uniform ``id`` attribute
    # (e.g. Config has no `id`), so we filter the *registered keys* instead.
    if not _item_belongs_to_system(spec, item, id, system):
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"{dim} '{id}' not found under system '{system}'",
        )
    return ok_response(
        {"item": _to_full_view(spec, item), "total": 1},
        dim=dim,
    )


def _item_belongs_to_system(spec: Any, item: Any, item_id: str, system: str) -> bool:
    """Return True iff ``item`` (returned by ``index.get(item_id)``) is in
    ``spec.index.list_for_system(system)``.

    Strategy: every index's ``list_for_system`` returns the same object
    instances as ``get`` (storage-backed dims use a single dict; endpoint /
    service / system iterate their own registries). So we compare by object
    identity (``is``) against the listed items.
    """
    items = spec.index.list_for_system(system)
    return any(it is item for it in items)


@router.get("/systems/{system}/{dim}/{id}")
def get_dim_item_for_system(
    system: str, dim: str, id: str, request: Request  # noqa: A002 - intentional path param
) -> dict[str, Any]:
    reg = _registry(request, system)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    _resolve_system(reg, system)
    item = spec.index.get(id)
    if item is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"{dim} '{id}' not found",
        )
    # Verify the item belongs to the requested system.
    if not _item_belongs_to_system(spec, item, id, system):
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"{dim} '{id}' not found under system '{system}'",
        )
    return ok_response(
        {"item": spec.index.to_view(item), "total": 1},
        dim=dim,
    )


@router.get("/systems/{system}/{dim}")
def list_dim_for_system(
    system: str, dim: str, request: Request
) -> dict[str, Any]:
    reg = _registry(request, system)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    _resolve_system(reg, system)
    raw_items = spec.index.list_for_system(system)
    items = [spec.index.to_view(it) for it in raw_items]
    return ok_response({"items": items, "total": len(items)}, dim=dim)


@router.post("/systems/{system}/{dim}/{id}/action/{name}")
def run_item_action_for_system(
    system: str,
    dim: str,
    id: str,  # noqa: A002
    name: str,
    request: Request,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if request is None:
        raise PlateHTTPError(
            http_status=503,
            code=ErrorCode.REGISTRY_UNAVAILABLE,
            message="plate registry is not initialised",
        )
    reg = _registry(request)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    _resolve_system(reg, system)
    item = spec.index.get(id)
    if item is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"{dim} '{id}' not found",
        )
    # X4(第六轮):系统作用域的对象动作补归属校验——与同 URL 的 GET
    # 详情同口径(此前动作直接作用在别系统的对象上,GET 却 404)。
    if not _item_belongs_to_system(spec, item, id, system):
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"{dim} '{id}' not found in system '{system}'",
        )
    return _dispatch_action(
        reg=reg,
        spec=spec,
        dim=dim,
        name=name,
        item=item,
        body=body,
        request=request,
    )


@router.post("/systems/{system}/{dim}/action/{name}")
def run_dim_action_for_system(
    system: str,
    dim: str,
    name: str,
    request: Request,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """System-scoped dim-node action (e.g. ``sync`` for C2)."""
    reg = _registry(request)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    _resolve_system(reg, system)
    # Pass the system name through the request context so dim-node actions
    # that need it (e.g. ``system/sync``) can include it in error messages.
    body = dict(body or {})
    body.setdefault("_system", system)
    return _dispatch_action(
        reg=reg,
        spec=spec,
        dim=dim,
        name=name,
        item=None,
        body=body,
        request=request,
    )


# ── Handlers — dim-node actions (must come before /{dim}/{id}) ──


@router.post("/{dim}/action/{name}")
def run_dim_action(
    dim: str,
    name: str,
    request: Request,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dim-node action (no ``{id}``) — e.g. B3 ``from-service``, C1 ``register``."""
    reg = _registry(request)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    return _dispatch_action(
        reg=reg,
        spec=spec,
        dim=dim,
        name=name,
        item=None,
        body=body,
        request=request,
    )


# ── /query-views(动态取数源 spec 2026-09-07 §3.4)──────────────────
#
# 注册顺序坑:本路由 MUST 先于下方 ``@router.get("/{dim}")`` 注册,
# 否则 ``/api/query-views`` 被吞成 ``dim="query-views"`` → 404 DIM_NOT_FOUND。


@router.get("/query-views")
def list_query_views(
    request: Request,
    ref: str = Query("working"),
    system: str | None = Query(None),
) -> dict[str, Any]:
    """动态取数源只读聚合索引(2026-09-07 spec §3.4):纯投影零状态。

    Release 4.7:``ref`` 按修订构建视图索引(修订不可变,索引可随修订缓存);
    ``ref`` 非 working 时 ``system`` 必填(ref 是系统作用域的)。
    """
    if ref and ref != "working":
        from gimbal_plate.release import read as release_read

        if not system:
            raise PlateHTTPError(
                http_status=400, code=ErrorCode.INVALID_REF,
                message="query-views 的 ref 需要 system 参数(版本线是系统作用域的)")
        root = _artifacts_root_or_503(request)
        try:
            ln, nn, _m = release_read.resolve_revision(root, system, ref)
            snap = release_read.load_snapshot(root, system, ln, nn)
        except release_read.ReleaseReadError as e:
            raise _read_error(e)
        items = build_query_view_index(list(snap.endpoints.values()))
        return ok_response({"items": items, "total": len(items),
                            "ref": snap.ref})
    reg = _registry(request)
    spec = reg.index_for("endpoint")
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message="dim 'endpoint' is not registered",
        )
    items = build_query_view_index(spec.index.list_global())
    return ok_response({"items": items, "total": len(items)})


# ── Global /full (must precede /{dim}/{id}) ──────────────────────


@router.get("/{dim}/full")
def list_full_dim_global(dim: str, request: Request) -> dict[str, Any]:
    """Global full list (every schema field per item)."""
    reg = _registry(request)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    _require_full_factory(spec, dim)
    raw_items = spec.index.list_global()
    items = [_to_full_view(spec, it) for it in raw_items]
    return ok_response({"items": items, "total": len(items)}, dim=dim)


@router.get("/{dim}/{id}/full")
def get_full_dim_item_global(
    dim: str, id: str, request: Request  # noqa: A002
) -> dict[str, Any]:
    """Global full detail for one item."""
    reg = _registry(request)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    _require_full_factory(spec, dim)
    item = spec.index.get(id)
    if item is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"{dim} '{id}' not found",
        )
    return ok_response(
        {"item": _to_full_view(spec, item), "total": 1},
        dim=dim,
    )


# ── /references (Phase β, ADR 0002 §D-D2) ─────────────────────────
#
# Answers "who references this item" without inventing a full cross-dim
# edge graph (Phase γ candidate). For each dim the answers we can give
# *reliably* from existing registry data are listed in
# ``_references_for_dim``. A 404 is returned if the item doesn't exist;
# otherwise we return whatever signals the dim exposes (may be empty
# for dims where references aren't tracked, e.g. ``system``).


@router.get("/{dim}/{id}/references")
def get_dim_item_references(
    dim: str, id: str, request: Request  # noqa: A002
) -> dict[str, Any]:
    """Reverse-lookup: which systems / cross-dim signals reference this item."""
    reg = _registry(request)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    item = spec.index.get(id)
    if item is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"{dim} '{id}' not found",
        )
    references = _references_for_dim(dim, item, id, reg)
    return ok_response(
        {"item": {"dim": dim, "id": id}, "references": references},
        dim=dim,
    )


def _references_for_dim(
    dim: str, item: Any, item_id: str, reg: PlateRegistry
) -> dict[str, Any]:
    """Return the per-dim reference signals we can answer from registry data.

    Phase β honest scope (ADR 0002 §D-D2):
        - systems: which systems own this item
        - service / module / tags / endpoint_count: dim-specific metadata
          signals already available without building a new edge index
        - scenarios: empty for now; Phase γ will scan scenario.config /
          scenario.resource refs to populate it.
    """
    out: dict[str, Any] = {"systems": [], "dim": dim}
    if dim == "endpoint":
        out["systems"] = [item.system]
        out["service"] = item.service
        out["module"] = item.metadata.module
        out["tags"] = list(item.metadata.tags or [])
    elif dim == "service":
        s = reg.system_of_service(item.name)
        out["systems"] = [s] if s else []
        out["endpoint_count"] = reg.count_endpoints_for_service(item.name)
    elif dim == "system":
        # ``SystemIndex.get`` returns a summary dict (not a model), so we
        # address its fields by key. System dim items don't have inbound
        # references — they're containers, not targets.
        out["systems"] = [item["id"]]
        out["endpoint_count"] = item["endpoint_count"]
        out["service_count"] = item["service_count"]
    elif dim == "config":
        # Item id is ``{system}.{name}``; the system is the leading segment.
        out["systems"] = [item_id.split(".", 1)[0]] if "." in item_id else []
        out["service_count"] = len(item.services or {})
    elif dim == "meta":
        out["systems"] = list(item.system or [])
    elif dim == "resource":
        # Item id is ``{system}.{name}`` — same prefix trick as config.
        out["systems"] = [item_id.split(".", 1)[0]] if "." in item_id else []
        out["kind"] = str(item.kind)
    elif dim == "scenario":
        out["systems"] = list(item.meta.system or [])
        # scenarios referencing a config / resource via id: future Phase γ.
        out["scenarios_referenced_by"] = []
    else:
        out["systems"] = []
    return out


# ── Handlers — global ────────────────────────────────────────────


@router.get("/{dim}")
def list_dim_global(
    dim: str,
    request: Request,
    service: str | None = Query(None),
    module: str | None = Query(None),
    method: str | None = Query(None),
    q: str | None = Query(None),
    tag: str | None = Query(None),
) -> dict[str, Any]:
    reg = _registry(request)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    filters: dict[str, Any] = {
        k: v for k, v in {
            "service": service, "module": module, "method": method,
            "q": q, "tag": tag,
        }.items() if v is not None
    }
    raw_items = spec.index.list_global(filters=filters)
    items = [spec.index.to_view(it) for it in raw_items]
    return ok_response({"items": items, "total": len(items)}, dim=dim)


@router.get("/{dim}/{id}")
def get_dim_item_global(
    dim: str, id: str, request: Request  # noqa: A002
) -> dict[str, Any]:
    reg = _registry(request)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    item = spec.index.get(id)
    if item is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"{dim} '{id}' not found",
        )
    return ok_response(
        {"item": spec.index.to_view(item), "total": 1},
        dim=dim,
    )


@router.get("/{dim}/{id}/action/{name}")
def run_item_action_get(
    dim: str, id: str, name: str, request: Request  # noqa: A002
) -> dict[str, Any]:
    reg = _registry(request)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    item = spec.index.get(id)
    if item is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"{dim} '{id}' not found",
        )
    return _dispatch_action(
        reg=reg,
        spec=spec,
        dim=dim,
        name=name,
        item=item,
        body=None,
        request=request,
    )


@router.post("/{dim}/{id}/action/{name}")
def run_item_action_post(
    dim: str,
    id: str,  # noqa: A002
    name: str,
    request: Request,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reg = _registry(request)
    spec = reg.index_for(dim)
    if spec is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_NOT_FOUND,
            message=f"unknown dim '{dim}'",
        )
    item = spec.index.get(id)
    if item is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"{dim} '{id}' not found",
        )
    return _dispatch_action(
        reg=reg,
        spec=spec,
        dim=dim,
        name=name,
        item=item,
        body=body,
        request=request,
    )


# ── Action dispatcher ─────────────────────────────────────────────


def _dispatch_action(
    *,
    reg: PlateRegistry,
    spec: Any,
    dim: str,
    name: str,
    item: Any | None,
    body: dict[str, Any] | None,
    request: Request | None = None,
) -> dict[str, Any]:
    """Dispatch to the per-dim action callable (registered on the DimSpec).

    Forwards ``item`` (the resolved dim item), ``body`` (request payload),
    ``index`` (the dim's :class:`BaseIndex` instance), and ``request`` (the
    FastAPI ``Request``) to the action callable. Actions that don't care
    about ``index`` or ``request`` simply ignore them.
    """
    actions: dict[str, Any] = spec.actions or {}
    handler = actions.get(name)
    if handler is None:
        raise PlateHTTPError(
            http_status=400,
            code=ErrorCode.INVALID_ACTION,
            message=f"unknown action '{name}' for dim '{dim}'",
        )
    return handler(item=item, body=body, index=spec.index, request=request)


# ── Concrete action callables (registered via DimSpec.actions) ──
# These are module-level callables wired into the lifespan in app.py via
# ``register_dim(..., actions={...})``. Keeping them here (rather than
# inlined into the dispatch) means per-dim actions are observable in one place.


def action_endpoint_field_defaults(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """A5 — compute field default suggestions for the endpoint."""
    _ = body, index, request
    return ok_response(compute_field_defaults(item), dim="endpoint")


def action_endpoint_resolve_paths(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """B1 — derive JSONPath candidates from a response body sample.

    Body (dict): ``{"response_body_sample": Any, "path_prefix": str | None}``.
    """
    _ = item, index, request
    body = body or {}
    sample = body.get("response_body_sample")
    prefix = body.get("path_prefix")
    return ok_response(
        {"paths": resolve_paths(sample, path_prefix=prefix)},
        dim="endpoint",
    )


def action_endpoint_failed_criteria(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """B2 — failed_criteria × assertable_fields linkage."""
    _ = body, index, request
    return ok_response(resolve_failed_criteria(item), dim="endpoint")


def action_endpoint_find(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """Endpoint route-lookup action.

    Body (dict): ``{"service": str, "method": str, "path": str}``.
    Returns the matching endpoint view, or 404 if no match.

    ``item`` is ignored for this dim-node action (no item id is required).
    ``index`` is the :class:`EndpointIndex` instance injected by
    :func:`_dispatch_action`.
    """
    _ = item  # dim-node action — no item id involved
    body = body or {}
    svc = body.get("service")
    mth = body.get("method")
    pth = body.get("path")
    if not (svc and mth and pth):
        raise PlateHTTPError(
            http_status=400,
            code=ErrorCode.INVALID_ACTION,
            message="'find' action requires body {service, method, path}",
        )
    ep = index.find_by_route(service=svc, method=mth, path=pth)
    if ep is None:
        raise PlateHTTPError(
            http_status=404,
            code=ErrorCode.DIM_ITEM_NOT_FOUND,
            message=f"no endpoint for {svc} {mth} {pth}",
        )
    return ok_response(
        {"item": index.to_view(ep), "total": 1},
        dim="endpoint",
    )



# ── system 动作的系统名解析(B1/J2,第五轮评审)───────────────────
# 安全纪律:系统名**只**来自路径参数(/api/systems/{system}/...);
# 绝不接受请求体(评审 B1:_system 注入曾可路径穿越并在任意位置写
# manifest)。校验链 = 名字格式 → 跨 loader 根查找 → resolve 包含性
# (防 ../ 与符号链接逃逸);不存在返回 404(此前 nonexistent 返回
# 200 ok:true 的假绿)。数据根与查询面同源(loader.systems_roots,
# 认 PLATE_SYSTEMS_PATH)——评审 J2:此前 HTTP 动作用包位置推导,
# 服务设 PLATE_SYSTEMS_PATH 时会出现「查询读 A 树、发版冻 B 树」。
# O4:名字规则单一定义于 loader.SYSTEM_NAME_RE(_resolve_action_system
# 函数内 import——loader 模块级反向 import 本模块,顶层引用会循环)


def _resolve_action_system(request: Any) -> "Path":
    from gimbal_plate.loader import SYSTEM_NAME_RE, systems_roots

    system = request.path_params.get("system") or ""
    if not system:
        raise PlateHTTPError(
            http_status=400, code=ErrorCode.INVALID_ACTION,
            message="system required: use /api/systems/{system}/system/action/{name}",
        )
    if not SYSTEM_NAME_RE.match(system):
        raise PlateHTTPError(
            http_status=400, code=ErrorCode.INVALID_ACTION,
            message=f"invalid system name {system!r} (expected ^[a-z][a-z0-9_-]*$)",
        )
    for root in systems_roots():
        candidate = (root / system).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue  # 解析后逃出根(符号链接等)——不在此根命中
        if candidate.is_dir():
            return candidate
    raise PlateHTTPError(
        http_status=404, code=ErrorCode.SYSTEM_NOT_FOUND,
        message=f"system {system!r} not found under any systems root",
    )


def action_system_gaps(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """G6:定义完整性缺口清单(判定项与交付件清单共用,8p)。

    dim-node action:``POST /api/system/{id}/system/action/gaps``。
    """
    _ = item, body, index
    from gimbal_plate.dialect.gaps import gaps_report
    from gimbal_plate.dialect.parser import DialectError
    from gimbal_plate.dialect.validation import collect_system_tree

    # B1/J2:系统名只认路径参数,经 _resolve_action_system 统一校验
    # (格式/跨 loader 根存在性/包含性);数据根与查询面同源。
    system_root = _resolve_action_system(request)
    try:
        tree = collect_system_tree(system_root, with_common=False)
    except DialectError as e:
        raise PlateHTTPError(
            http_status=422, code=ErrorCode.INVALID_ACTION,
            message=f"system tree parse error: {e}",
        ) from e
    # J2:0 接口且 0 片段 0 词条 → 大概率数据根配错(如 wheel 部署未设
    # PLATE_SYSTEMS_PATH),静默返回零报表比报错更危险
    if not (tree.endpoints or tree.statements or tree.terms):
        raise PlateHTTPError(
            http_status=422, code=ErrorCode.INVALID_ACTION,
            message=f"system {system_root.name!r} tree is empty "
                    f"(no endpoints/statements/terms) — wrong systems root?",
        )
    return ok_response(
        gaps_report(tree.endpoints, tree.statements, tree.terms), dim="system")


def action_system_check(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """校验报告(``check``,规则编号即错误码;与 CLI 同一引擎,G2/R10)。"""
    _ = item, body, index
    from gimbal_plate.dialect.validation import validate_system_tree
    # B1/J2:系统名只认路径参数,统一走 _resolve_action_system;
    # 与 CLI 同一 validate_system_tree(R10),方言错误在引擎内转 F0(J5),
    # 不再裸 500。
    system_root = _resolve_action_system(request)
    report = validate_system_tree(system_root)
    return ok_response(report.to_dict(), dim="system")


def action_system_resolve(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """Release 4.4:生效修订解析(版本模型 4.2 可用集合语义,D-5)。

    Body: ``{"meta_plate": {系统: "<line>#<n>" | "working"},
    "endpoints": {系统: [endpoint_id, ...]}}`` → 每系统
    ``{effective, available, changed_endpoints}``。声明 working 原样返回;
    计算只依赖 manifest 的 shape_hash(I-5:plate 不知道谁在用哪个版本)。
    """
    _ = item, index
    from gimbal_plate.release import read as release_read

    body = body or {}
    meta_plate = body.get("meta_plate") or {}
    endpoints = body.get("endpoints") or {}
    root = _artifacts_root_or_503(request)
    out: dict[str, Any] = {}
    for system, declared in meta_plate.items():
        if declared == "working":
            out[system] = {"effective": "working",
                           "available": [], "changed_endpoints": []}
            continue
        try:
            out[system] = release_read.resolve_effective(
                root, system, str(declared),
                list(endpoints.get(system) or []))
        except release_read.ReleaseReadError as e:
            raise _read_error(e)
    return ok_response({"item": out, "total": len(out)}, dim="system")


def action_system_from_service(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """B3 — parse system id from a ``<system>.<service>`` string.

    Body (dict): ``{"services": list[str]}``.
    """
    _ = item, index, request
    body = body or {}
    services = body.get("services") or []
    return ok_response(system_from_service(services), dim="system")


def action_system_register(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """C1 — **已停用**（S1-0 B4，2026-10-07）。

    与「Markdown 方言为唯一真源」（P1）冲突：内存态系统注册重启即失，
    主线下系统必须对应 ``systems/<系统>/`` 下的文件（附录 C X4）。
    平台侧无调用（已核实）。随 HTTP 写入路径重新设计时再评估替代。
    """
    _ = item, body, index, request
    raise PlateHTTPError(
        http_status=410,
        code=ErrorCode.INVALID_ACTION,
        message=(
            "action 'system-register' is disabled (S1-0 B4): in-memory system "
            "registration conflicts with Markdown-as-single-source (P1); "
            "declare systems as systems/<id>/ files instead"
        ),
    )


def action_system_sync(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """C2 — **已停用**（S1-0 B4，2026-10-07；原为 501 占位 stub）。"""
    _ = item, body, index, request
    raise PlateHTTPError(
        http_status=410,
        code=ErrorCode.ADMIN_NOT_IMPLEMENTED,
        message=(
            "action 'system-sync' is disabled (S1-0 B4): structure sync is "
            "superseded by the unified loader over systems/<id>/ files"
        ),
    )


def action_scenario_convert(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """结构转换 —— 把调用方传入的 Scenario dict 转换为目标 consumer 的 dict。

    这是一个 dim-node action(不针对已注册的 scenario id),挂载在 ``scenario``
    dim 下面。**复用** ``gimbal_plate.export.dispatch`` 现有的声明式 dispatch
    入口,不再重新实现任何转换逻辑。

    Body (dict):
        ``{"consumer": "gimbal" | "platform", "scenario": {...平台组装的
        Scenario dict...}, "endpoints": [...]?, "sections": [...]?}``

    - 缺失 ``scenario`` 字段 → 400 ``invalid_action``
    - ``Scenario.model_validate`` 失败 → 400 ``invalid_action``
    - ``consumer`` 未注册 → 400 ``invalid_action``(export.dispatch 抛
      ``ValueError``,错误信息会列出可用 consumer)
    - 未知 ``**kwargs``(如 ``endpoints`` 给 gimbal 用)→ 400
      ``invalid_action``(consumer request model 的 ``extra="forbid"`` 校验)

    Returns
    -------
    dict
        ``{"consumer": <str>, "converted": <dict>}`` —— 由 envelope 层包
        上标准 ``ok`` 信封。
    """
    _ = item, index, request  # dim-node action -- no item id involved
    body = body or {}

    # Step 1: validate the incoming dict and coerce it to the neutral Scenario
    # model. A failure here (missing field / wrong type) is a 400; we never
    # let an invalid structure reach export.dispatch(). Scenario-level
    # model_validators (id consistency, etc.) also kick in naturally here.
    raw_scenario = body.get("scenario")
    if raw_scenario is None:
        raise PlateHTTPError(
            http_status=400,
            code=ErrorCode.INVALID_ACTION,
            message="'convert' action requires body.scenario",
        )
    # ── RS2(Release 4.5):meta.plate 原值重投影 ──
    # 平台入队时已把生效修订写入执行副本的 meta.plate;此处按原值取修订
    # 合并 call(解析只在一处发生)。不带 meta.plate(过渡期/预览)照旧。
    # (B-7/W24:strict_ref 收口面已删 —— 平台 M1 起全量传修订,该参数
    # 全仓零发送方;REF_REQUIRED 错误码保留在注册表,接收逻辑退役)
    meta_plate = None
    if isinstance(raw_scenario, dict):
        meta = raw_scenario.get("meta")
        if isinstance(meta, dict):
            meta_plate = meta.get("plate") or None
    # ⑥(2026-10-13):「不带 meta.plate 照旧」的过渡期兼容分支退役 ——
    # 平台保存闸(scenario_store 唯一写入口)已强制锚定系统声明,所有
    # 正常入库场景都带声明;不带声明的锚定场景只剩绕过写入口的旁路,
    # 按版本模型 I 系不变量必须拒绝,不再按存储 binding 静默放行。
    if isinstance(raw_scenario, dict):
        # 2-3(2026-10-13):逐系统校验,与平台 enforce_meta_plate 同口径
        # —— 此前只拦"整个 meta.plate 缺失",声明了 fin 但步骤还锚定
        # abc 的部分声明载荷仍被放行(只剩旁路可达)。
        anchored = {
            str(st.get("endpoint")).split(".")[0]
            for st in (raw_scenario.get("steps") or [])
            if isinstance(st, dict) and st.get("endpoint")
            and not str(st.get("endpoint")).startswith("ext:")
        }
        anchored.discard("")
        declared = meta_plate or {}
        undeclared = sorted(s for s in anchored if not declared.get(s))
        if undeclared:
            raise PlateHTTPError(
                http_status=422,
                code=ErrorCode("version_undeclared"),
                message=(f"锚定系统 {undeclared} 未声明 meta.plate —— "
                         "平台保存闸已强制声明,不带/缺声明的载荷属旁路写入"),
            )
        # 归一方案 v1.0 §1.4(D-K/D-O):声明域合法集 = working |
        # <line>#<n> | integration,逐系统经 parse_ref 类别裁决 ——
        # ①裸线(取数域合法、声明域拒,消除「平台拒、plate 收」双口径);
        # ②integration 双向绑定:仅 kind=integration 系统可声明,反之
        # 亦然(绑定违例不是形状问题,invalid_ref 不带 reason)。
        # 线存在性/修订号范围由 reproject 的 resolve_revision 兜底。
        from gimbal_plate.release.read import (
            ReleaseReadError as _RRE,
            parse_ref as _parse_ref,
        )
        for sys_name, raw_ref in declared.items():
            ref = str(raw_ref or "")
            try:
                kind = _parse_ref(ref)[0]
            except _RRE as e:
                raise PlateHTTPError(
                    http_status=422,
                    code=ErrorCode("invalid_ref"),
                    message=e.message,
                    details={"reason": e.reason} if e.reason else None,
                ) from e
            if kind == "line":
                raise PlateHTTPError(
                    http_status=422,
                    code=ErrorCode("invalid_ref"),
                    message=(f"{sys_name}={ref!r} 缺修订号"
                             "(声明须为 <line>#<n> / working / integration)"),
                    details={"reason": "missing_revision"},
                )
            if kind == "integration":
                _sd = _registry(request).get_service(
                    _service_of_system(_registry(request), sys_name))
                _sys_kind = _sd.kind if _sd is not None else None
                if _sys_kind != "integration":
                    raise PlateHTTPError(
                        http_status=422,
                        code=ErrorCode("invalid_ref"),
                        message=(f"{sys_name}={ref!r} 仅可用于 "
                                 f"kind=integration 的系统(实为 "
                                 f"{_sys_kind or '未登记'});"
                                 "sut 系统请声明 <line>#<n> 或 working"),
                    )
    used_refs: dict[str, str] | None = None
    if meta_plate:
        from gimbal_plate.release.reproject import (
            ReprojectError,
            reproject_raw,
        )

        # C 批修带(2026-10-13):构件根只在存在**非 working**修订时必需
        # —— reproject_raw 对 working 声明只用当前树。此前 meta.plate
        # 非空即 503,全 working 场景(保存闸 C-2 起缺省声明)在未配
        # 构件根的环境(进程内 plate/新检出)一律拒转。
        # 归一方案 v1.0 §3.1:按 parse_ref 类别判断 —— integration 与
        # working 同走当前树,不触发构件根(否则含 integration 声明的
        # convert 在无构件根时 503)。
        from gimbal_plate.release.read import parse_ref as _parse_ref
        _needs_root = any(
            str(v) and _parse_ref(str(v))[0] not in ("working", "integration")
            for v in (meta_plate or {}).values())
        root = (_artifacts_root_or_503(request) if _needs_root else None)
        try:
            raw_scenario, used_refs = reproject_raw(
                raw_scenario, meta_plate,
                root=root, working_registry=_registry(request))
        except ReprojectError as e:
            raise PlateHTTPError(
                http_status=422,
                code=ErrorCode(str(e.code)),
                message=e.message,
            ) from e
    try:
        scenario = Scenario.model_validate(raw_scenario)
    except ValidationError as exc:
        raise PlateHTTPError(
            http_status=400,
            code=ErrorCode.INVALID_ACTION,
            message=f"scenario payload failed validation: {exc}",
        ) from exc

    # Step 2: dispatch via export.dispatch(), forwarding only the consumer-
    # specific kwargs the caller actually sent (see _pass_through_kwargs).
    consumer = body.get("consumer", "gimbal")
    extra_kwargs = _pass_through_kwargs(body, ("endpoints", "sections"))
    try:
        result = export.dispatch(consumer, scenario, **extra_kwargs)
    except ValueError as exc:  # unknown consumer
        raise PlateHTTPError(
            http_status=400,
            code=ErrorCode.INVALID_ACTION,
            message=str(exc),
        ) from exc
    except ValidationError as exc:  # bad kwargs for the consumer (e.g. unknown section)
        raise PlateHTTPError(
            http_status=400,
            code=ErrorCode.INVALID_ACTION,
            message=f"convert kwargs failed validation for consumer {consumer!r}: {exc}",
        ) from exc

    payload_out: dict[str, Any] = {"consumer": consumer, "converted": result}
    if used_refs is not None:
        # 4.5:响应带回实际使用的修订表(平台写入 plate_pins)
        payload_out["used"] = used_refs
        payload_out["meta_plate"] = meta_plate
    # M2 §5.1/§9.5:响应附带构建身份(平台随执行请求转交执行器,
    # 代际门比对「哪份 M2 校验」与「执行器按哪份构建」)
    _m2 = _cached_m2_export()
    payload_out["m2"] = {"hash": _m2.m2_hash,
                         "generation": _m2.m2_generation}
    return ok_response(payload_out, dim="scenario")


# Public exports.
__all__ = [
    "router",
    "action_endpoint_field_defaults",
    "action_endpoint_resolve_paths",
    "action_endpoint_failed_criteria",
    "action_endpoint_find",
    "action_system_from_service",
    "action_system_register",
    "action_system_sync",
    "action_scenario_convert",
]