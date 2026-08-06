"""C-group routes: admin/system management (C1, C2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from gimbal_plate.http.envelope import PlateHTTPError

router = APIRouter(prefix="/api", tags=["admin"])


@router.post("/systems")
def register_system(request: Request) -> dict[str, Any]:
    """C1: register / update a system. Not implemented in plate (deferred)."""
    _ = request
    raise PlateHTTPError(
        http_status=501,
        code="admin_not_implemented",
        message=(
            "system registration is not implemented in plate; "
            "C1 is deferred to the platform backend"
        ),
    )


@router.post("/systems/{system_id}/sync")
def sync_system(system_id: str, request: Request) -> dict[str, Any]:
    """C2: sync structure version. Not implemented in plate (deferred)."""
    _ = request
    raise PlateHTTPError(
        http_status=501,
        code="admin_not_implemented",
        message=(
            f"structure sync for system '{system_id}' is not implemented in plate; "
            "C2 is deferred to the platform backend"
        ),
    )


__all__ = ["router"]
