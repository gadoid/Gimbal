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
from gimbal_plate.service.system_from_service import system_from_service


router = APIRouter(prefix="/api", tags=["grammar"])


# ── Helpers ──────────────────────────────────────────────────────


def _registry(request: Request) -> PlateRegistry:
    reg: PlateRegistry | None = getattr(request.app.state, "registry", None)
    if reg is None:
        raise PlateHTTPError(
            http_status=503,
            code=ErrorCode.REGISTRY_UNAVAILABLE,
            message="plate registry is not initialised",
        )
    return reg


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
    reg = _registry(request)
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
# *full* contract (every schema field, including IOFieldBinding metadata,
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
    reg = _registry(request)
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
    reg = _registry(request)
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
    items = spec.index.list_for_system(system)
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
    reg = _registry(request)
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
    """C1 — system registration stub."""
    _ = item, body, index, request
    raise PlateHTTPError(
        http_status=501,
        code=ErrorCode.ADMIN_NOT_IMPLEMENTED,
        message=(
            "system registration is not implemented in plate; "
            "C1 is deferred to the platform backend"
        ),
    )


def action_system_sync(
    *, item: Any, body: Any, index: Any, request: Any
) -> dict[str, Any]:
    """C2 — structure sync stub."""
    _ = item, index, request
    body = body or {}
    system = body.get("_system") or "<unknown>"
    raise PlateHTTPError(
        http_status=501,
        code=ErrorCode.ADMIN_NOT_IMPLEMENTED,
        message=(
            f"structure sync for system '{system}' is not implemented in plate; "
            f"C2 is deferred to the platform backend"
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

    return ok_response(
        {"consumer": consumer, "converted": result},
        dim="scenario",
    )


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