"""A-group routes: structural reads (A1-A5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, Request

from gimbal_plate.service.field_defaults import compute_field_defaults
from gimbal_plate.http.envelope import (
    PlateHTTPError,
    err_response,
    ok_response,
)
from gimbal_plate.registry import PlateRegistry

router = APIRouter(prefix="/api", tags=["structure"])


def _registry(request: Request) -> PlateRegistry:
    reg: PlateRegistry | None = getattr(request.app.state, "registry", None)
    if reg is None:
        raise PlateHTTPError(
            http_status=503,
            code="registry_unavailable",
            message="plate registry is not initialised",
        )
    return reg


@router.get("/systems")
def list_systems(request: Request) -> dict[str, Any]:
    """A1: list registered systems with service/endpoint counts."""
    reg = _registry(request)
    endpoints = list(reg._index.by_id.values())  # noqa: SLF001 - internal index

    by_system: dict[str, dict[str, Any]] = {}
    for ep in endpoints:
        bucket = by_system.setdefault(
            ep.system,
            {
                "service_names": set(),
                "endpoint_count": 0,
                "updated_at_max": None,
            },
        )
        bucket["service_names"].add(ep.service)
        bucket["endpoint_count"] += 1
        ts = ep.updated_at
        if bucket["updated_at_max"] is None or ts > bucket["updated_at_max"]:
            bucket["updated_at_max"] = ts

    systems: list[dict[str, Any]] = []
    for system_id in sorted(by_system):
        b = by_system[system_id]
        updated: datetime | None = b["updated_at_max"]
        systems.append(
            {
                "id": system_id,
                "name": system_id,
                "service_count": len(b["service_names"]),
                "endpoint_count": b["endpoint_count"],
                "registered_at": (
                    updated.isoformat().replace("+00:00", "Z")
                    if updated is not None
                    else None
                ),
            }
        )
    return ok_response({"systems": systems})


@router.get("/systems/{system_id}/tree")
def system_tree(
    system_id: str,
    request: Request,
    depth: int = Query(2, ge=1, le=3),
) -> dict[str, Any]:
    """A2: list services (and modules when ``depth >= 2``) under a system."""
    _ = depth
    reg = _registry(request)
    endpoints = [ep for ep in reg._index.by_id.values() if ep.system == system_id]  # noqa: SLF001

    if not endpoints:
        # Distinguish "no such system" from "system with no services": a system
        # is treated as present when at least one endpoint references it, so
        # empty here means truly unknown.
        raise PlateHTTPError(
            http_status=404,
            code="not_found",
            message=f"system '{system_id}' has no registered endpoints",
        )

    by_service: dict[str, dict[str, Any]] = {}
    for ep in endpoints:
        bucket = by_service.setdefault(
            ep.service,
            {"module_names": set(), "endpoint_count": 0},
        )
        bucket["module_names"].add(ep.metadata.module or "")
        bucket["endpoint_count"] += 1

    services_payload: list[dict[str, Any]] = []
    for service_id in sorted(by_service):
        b = by_service[service_id]
        modules = [
            {"id": mod, "endpoint_count": sum(
                1
                for ep in endpoints
                if ep.service == service_id and (ep.metadata.module or "") == mod
            )}
            for mod in sorted(b["module_names"])
        ]
        services_payload.append(
            {
                "id": service_id,
                "name": service_id,
                "modules": modules,
            }
        )

    return ok_response({"services": services_payload})


@router.get("/systems/{system_id}/services/{service}/endpoints")
def list_endpoints(
    system_id: str,
    service: str,
    request: Request,
    module: str | None = Query(None),
    method: str | None = Query(None),
    q: str | None = Query(None),
) -> dict[str, Any]:
    """A3: list endpoints under a service with optional filters."""
    reg = _registry(request)
    candidates = [
        ep
        for ep in reg._index.by_id.values()  # noqa: SLF001
        if ep.system == system_id and ep.service == service
    ]

    if not candidates:
        # surface 404 only when the service has no endpoints at all
        raise PlateHTTPError(
            http_status=404,
            code="not_found",
            message=(
                f"no endpoints under system='{system_id}' service='{service}'"
            ),
        )

    if module is not None:
        candidates = [ep for ep in candidates if (ep.metadata.module or "") == module]
    if method is not None:
        candidates = [ep for ep in candidates if ep.api.method.upper() == method.upper()]
    if q:
        needle = q.lower()
        candidates = [
            ep
            for ep in candidates
            if needle in ep.id.lower()
            or needle in ep.name.lower()
            or needle in (ep.description or "").lower()
            or needle in ep.api.path.lower()
        ]

    out = [
        {
            "id": ep.id,
            "name": ep.name,
            "method": ep.api.method,
            "path": ep.api.path,
            "description": ep.description,
            "system": ep.system,
            "service": ep.service,
            "module": ep.metadata.module or "",
            "tags": list(ep.metadata.tags or []),
            "priority": ep.metadata.priority,
            "version": ep.version,
        }
        for ep in candidates
    ]
    return ok_response({"endpoints": out, "total": len(out)})


@router.get("/endpoints/{endpoint_id}")
def endpoint_detail(endpoint_id: str, request: Request) -> dict[str, Any]:
    """A4: full EndpointSpec contract as a JSON dict."""
    reg = _registry(request)
    try:
        endpoint = reg.get_endpoint(endpoint_id)
    except KeyError as exc:
        raise PlateHTTPError(
            http_status=404,
            code="not_found",
            message=f"endpoint '{endpoint_id}' not found",
        ) from exc
    return ok_response(endpoint.model_dump(mode="json", exclude_none=True))


@router.get("/endpoints/{endpoint_id}/field-defaults")
def field_defaults(
    endpoint_id: str,
    request: Request,
) -> dict[str, Any]:
    """A5: field default suggestions for the field editor."""
    reg = _registry(request)
    try:
        endpoint = reg.get_endpoint(endpoint_id)
    except KeyError as exc:
        raise PlateHTTPError(
            http_status=404,
            code="not_found",
            message=f"endpoint '{endpoint_id}' not found",
        ) from exc
    return ok_response(compute_field_defaults(endpoint))


__all__ = ["router"]
