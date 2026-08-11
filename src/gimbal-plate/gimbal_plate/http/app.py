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
from gimbal_plate.http.grammar import ErrorCode
from gimbal_plate.http.routes_grammar import router as grammar_router
from gimbal_plate.registry import PlateRegistry, registry as default_registry
from gimbal_plate.systems.fin.dimensions import register_fin_dims


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Ensure the bundled fin system + 7 dims are registered on startup.

    When an external registry is injected via ``create_app(registry=...)`` this
    step is skipped so the caller controls its own state.

    启动流程(owned 模式):
    1. ``ALL_ENDPOINTS`` 注册到默认 registry(产生 system / service / endpoint 三个 dim 的数据)。
    2. ``system == FIN_SYSTEM`` 自检:若有人改了某个 endpoint 但忘了同步 system_info,
       服务启动即失败,便于尽早暴露问题。
    3. ``register_dim`` 7 个 dim(endpoint / service / system / config / meta / resource / scenario)。
    4. 给 4 个 storage-backed dim 写入 1 条 seed,保证 ``GET /api/config`` 等返回非空。
    """
    if getattr(app.state, "registry_owned", True):
        try:
            from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS
        except Exception:  # pragma: no cover - defensive: lazy import guard
            ALL_ENDPOINTS = ()
        for ep in ALL_ENDPOINTS:
            default_registry.register_endpoint(ep)

        # system 自检:仅在 owned 默认 registry 时执行,尊重外部注入。
        from gimbal_plate.systems.fin.system_info import FIN_SYSTEM
        wrong = [
            ep for ep in default_registry.list_endpoints()
            if ep.system != FIN_SYSTEM
        ]
        if wrong:
            ids = ", ".join(repr(ep.id) for ep in wrong[:5])
            raise RuntimeError(
                f"plate lifespan sanity check failed: "
                f"{len(wrong)} endpoint(s) have system != FIN_SYSTEM "
                f"(first: {ids}). "
                f"请检查 fin/endpoint/*.py 是否与 system_info.FIN_SYSTEM 一致。"
            )

        # M6 grammar: 注册 7 个 dim + 4 条 seed(ADR 0002 §D-D4,
        # 共享入口见 ``gimbal_plate.systems.fin.dimensions``)。
        register_fin_dims(default_registry)
    yield


def create_app(
    *,
    registry: PlateRegistry | None = None,
    mount_prefix: str = "",
) -> FastAPI:
    """Create a FastAPI app exposing the M6 grammar surface (ADR 0002 §D1).

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
            code=ErrorCode.INTERNAL_ERROR,
            message=str(exc) or exc.__class__.__name__,
            http_status=500,
        )
        return JSONResponse(status_code=status, content=body)

    @app.get("/healthz", include_in_schema=False)
    async def _healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(grammar_router)

    return app


__all__ = ["create_app"]