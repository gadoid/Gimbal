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
from gimbal_plate.systems.common.dimensions import register_common_dims
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
    3. ``register_dim`` 8 个 dim(7 数据: endpoint / service / system / config / meta /
           resource / scenario;1 语法: strategy —— kind 描述符,2026-08-17)。
    4. 给 4 个 storage-backed dim 写入 1 条 seed,保证 ``GET /api/config`` 等返回非空。
    """
    if getattr(app.state, "registry_owned", True):
        # Reset the default registry before re-registering so a stale
        # singleton from a prior process / test session doesn't raise
        # "endpoint already registered" on restart.
        default_registry.reset()
        try:
            from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS as FIN_ENDPOINTS
        except Exception:  # pragma: no cover - defensive: lazy import guard
            FIN_ENDPOINTS = ()
        # platform 是自举被测系统,定义形态与 fin 同构(每端点一个 .py);平台侧
        # 故意不吞异常 —— 端点文件坏了要在启动时炸,不是静默少注册一半。
        from gimbal_plate.systems.platform.endpoint import (
            ALL_ENDPOINTS as PLATFORM_ENDPOINTS,
        )

        default_registry.register_endpoints((*FIN_ENDPOINTS, *PLATFORM_ENDPOINTS))

        # system 自检:仅在 owned 默认 registry 时执行,尊重外部注入。
        # 已知 system 白名单(而非"必须等于 FIN_SYSTEM")—— platform 是自举
        # 被测系统,common 是通用层;拼错 system 名仍会在启动时炸。
        from gimbal_plate.systems.common.dimensions import COMMON_SYSTEM
        from gimbal_plate.systems.fin.system_info import FIN_SYSTEM
        from gimbal_plate.systems.platform.system_info import PLATFORM_SYSTEM

        known_systems = {FIN_SYSTEM, PLATFORM_SYSTEM, COMMON_SYSTEM}
        wrong = [
            ep for ep in default_registry.list_endpoints()
            if ep.system not in known_systems
        ]
        if wrong:
            ids = ", ".join(repr(ep.id) for ep in wrong[:5])
            raise RuntimeError(
                f"plate lifespan sanity check failed: "
                f"{len(wrong)} endpoint(s) have system outside "
                f"{sorted(known_systems)} (first: {ids}). "
                f"请检查各 systems/*/ 下的 system 名是否与 system_info 一致。"
            )

        # M6 grammar: 注册 8 个 dim(7 数据 + 1 语法 strategy)+ 4 条 seed(ADR 0002 §D-D4,
        # 共享入口见 ``gimbal_plate.systems.fin.dimensions``)。
        register_fin_dims(default_registry)

        # common 通用层:声明式系统 + ``common.default`` config/meta 通用默认
        # (编排页"选系统 → 场景骨架预填"的默认源;meta 在通用层管理,
        # 不放业务系统下)。须在 register_fin_dims 之后(dim 已就位才可播种)。
        register_common_dims(default_registry)
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