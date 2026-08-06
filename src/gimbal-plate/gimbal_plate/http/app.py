"""FastAPI application factory for the plate HTTP service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from gimbal_plate.http.envelope import (
    PlateHTTPError,
    err_response,
)
from gimbal_plate.http.routes_admin import router as admin_router
from gimbal_plate.http.routes_resolve import router as resolve_router
from gimbal_plate.http.routes_structure import router as structure_router
from gimbal_plate.registry import PlateRegistry, registry as default_registry


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Ensure the bundled fin system is registered on startup by default.

    When an external registry is injected via ``create_app(registry=...)`` this
    step is skipped so the caller controls its own state.
    """
    if getattr(app.state, "registry_owned", True):
        try:
            from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS
        except Exception:  # pragma: no cover - defensive: lazy import guard
            ALL_ENDPOINTS = ()
        for ep in ALL_ENDPOINTS:
            default_registry.register_endpoint(ep)
    yield


def create_app(
    *,
    registry: PlateRegistry | None = None,
    mount_prefix: str = "",
) -> FastAPI:
    """Create a FastAPI app exposing the plate structure surface.

    Parameters
    ----------
    registry:
        Optional registry instance. When provided, it is stored on
        ``app.state.registry`` and the lifespan hook will NOT auto-register
        the bundled fin system into the global default registry. This is the
        expected integration point for embedding plate into another service.
    mount_prefix:
        Reserved for future use; the routers already use absolute paths.
    """
    _ = mount_prefix  # reserved for future use
    app = FastAPI(
        title="Plate Structure Service",
        version="0.1.0",
        lifespan=_lifespan,
    )

    if registry is None:
        app.state.registry = default_registry
        app.state.registry_owned = True
    else:
        app.state.registry = registry
        app.state.registry_owned = False

    @app.exception_handler(PlateHTTPError)
    async def _plate_http_error_handler(
        _request: Request, exc: PlateHTTPError
    ) -> JSONResponse:
        body, status = err_response(
            code=exc.code,
            message=exc.message,
            http_status=exc.http_status,
            details=exc.details,
        )
        return JSONResponse(status_code=status, content=body)

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        body, status = err_response(
            code="internal_error",
            message=str(exc) or exc.__class__.__name__,
            http_status=500,
        )
        return JSONResponse(status_code=status, content=body)

    @app.get("/healthz", include_in_schema=False)
    async def _healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(structure_router)
    app.include_router(resolve_router)
    app.include_router(admin_router)

    return app


__all__ = ["create_app"]
