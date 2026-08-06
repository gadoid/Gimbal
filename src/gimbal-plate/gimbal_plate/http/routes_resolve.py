"""B-group routes: structural resolve / search (B1-B3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from gimbal_plate.service.failed_resolver import resolve_failed_criteria
from gimbal_plate.service.paths_resolver import resolve_paths
from gimbal_plate.service.system_from_service import system_from_service
from gimbal_plate.http.envelope import (
    PlateHTTPError,
    ok_response,
)
from gimbal_plate.registry import PlateRegistry

router = APIRouter(prefix="/api", tags=["resolve"])


class _ResolvePathsBody(BaseModel):
    response_body_sample: Any
    path_prefix: str | None = None


class _SystemFromServiceBody(BaseModel):
    services: list[str] = Field(default_factory=list)


def _registry(request: Request) -> PlateRegistry:
    reg: PlateRegistry | None = getattr(request.app.state, "registry", None)
    if reg is None:
        raise PlateHTTPError(
            http_status=503,
            code="registry_unavailable",
            message="plate registry is not initialised",
        )
    return reg


@router.post("/endpoints/{endpoint_id}/resolve-paths")
def resolve_paths_endpoint(
    endpoint_id: str,
    body: _ResolvePathsBody,
    request: Request,
) -> dict[str, Any]:
    """B1: enumerate candidate JSONPaths from a response body sample."""
    reg = _registry(request)
    try:
        # Touch the registry to ensure the endpoint exists, but the body sample
        # is the actual input. Failing fast on unknown endpoint_id keeps
        # behaviour consistent with A4.
        reg.get_endpoint(endpoint_id)
    except KeyError as exc:
        raise PlateHTTPError(
            http_status=404,
            code="not_found",
            message=f"endpoint '{endpoint_id}' not found",
        ) from exc

    paths = resolve_paths(
        body.response_body_sample, path_prefix=body.path_prefix
    )
    return ok_response({"paths": paths})


@router.post("/endpoints/{endpoint_id}/failed-criteria-resolved")
def failed_criteria_resolved(
    endpoint_id: str,
    request: Request,
) -> dict[str, Any]:
    """B2: failed_criteria × assertable_fields linkage analysis."""
    reg = _registry(request)
    try:
        endpoint = reg.get_endpoint(endpoint_id)
    except KeyError as exc:
        raise PlateHTTPError(
            http_status=404,
            code="not_found",
            message=f"endpoint '{endpoint_id}' not found",
        ) from exc
    return ok_response(resolve_failed_criteria(endpoint))


@router.post("/resolve/system-from-service")
def system_from_service_endpoint(
    body: _SystemFromServiceBody,
) -> dict[str, Any]:
    """B3: derive system id from a ``<system>.<service>`` string."""
    return ok_response(system_from_service(body.services))


__all__ = ["router"]
