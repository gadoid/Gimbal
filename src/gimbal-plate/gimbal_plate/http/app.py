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
from gimbal_plate.http.grammar import (
    ConfigIndex,
    DimSpec,
    EndpointIndex,
    MetaIndex,
    ResourceIndex,
    ScenarioIndex,
    ServiceIndex,
    SystemIndex,
)
from gimbal_plate.http.routes_grammar import (
    action_endpoint_failed_criteria,
    action_endpoint_field_defaults,
    action_endpoint_find,
    action_endpoint_resolve_paths,
    action_system_from_service,
    action_system_register,
    action_system_sync,
    router as grammar_router,
)
from gimbal_plate.http.views import (
    ConfigDetailView,
    ConfigView,
    EndpointDetailView,
    EndpointView,
    MetaDetailView,
    MetaView,
    ResourceDetailView,
    ResourceView,
    ScenarioDetailView,
    ScenarioView,
    ServiceDetailView,
    ServiceView,
    SystemDetailView,
    SystemView,
)
from gimbal_plate.registry import PlateRegistry, registry as default_registry
from gimbal_plate.systems.fin.config import fin_config_template
from gimbal_plate.systems.fin.meta import fin_meta_template
from gimbal_plate.systems.fin.resource import fin_resource_template
from gimbal_plate.systems.fin.scenario import fin_scenario_template


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

        # M6 grammar: 注册 7 个 dim + 4 条 seed(ADR 0002 §D-D4)
        _register_fin_dims(default_registry)
    yield


def _register_fin_dims(reg: PlateRegistry) -> None:
    """Register the 7 M6 dims + seed the 4 storage-backed dims (fin only)."""
    reg.register_dim(
        "endpoint",
        DimSpec(
            name="endpoint",
            index=EndpointIndex(registry=reg),
            view_factory=EndpointView.from_spec,
            full_view_factory=EndpointDetailView.from_spec,
            actions={
                "field-defaults":  action_endpoint_field_defaults,
                "resolve-paths":   action_endpoint_resolve_paths,
                "failed-criteria": action_endpoint_failed_criteria,
                "find":            action_endpoint_find,
            },
        ),
    )
    reg.register_dim(
        "service",
        DimSpec(
            name="service",
            index=ServiceIndex(registry=reg),
            view_factory=ServiceView.from_definition,
            full_view_factory=ServiceDetailView.from_definition,
            actions={},
        ),
    )
    reg.register_dim(
        "system",
        DimSpec(
            name="system",
            index=SystemIndex(registry=reg),
            view_factory=SystemView.from_summary,
            full_view_factory=SystemDetailView.from_summary,
            actions={
                "from-service": action_system_from_service,
                "register":     action_system_register,
                "sync":         action_system_sync,
            },
        ),
    )

    cfg_idx = ConfigIndex(registry=reg)
    meta_idx = MetaIndex(registry=reg)
    res_idx = ResourceIndex(registry=reg)
    scen_idx = ScenarioIndex(registry=reg)
    reg.register_dim(
        "config",
        DimSpec(
            name="config",
            index=cfg_idx,
            view_factory=ConfigView.from_config,
            full_view_factory=ConfigDetailView.from_config,
            actions={},
        ),
    )
    reg.register_dim(
        "meta",
        DimSpec(
            name="meta",
            index=meta_idx,
            view_factory=MetaView.from_meta,
            full_view_factory=MetaDetailView.from_meta,
            actions={},
        ),
    )
    reg.register_dim(
        "resource",
        DimSpec(
            name="resource",
            index=res_idx,
            view_factory=ResourceView.from_resource,
            full_view_factory=ResourceDetailView.from_resource,
            actions={},
        ),
    )
    reg.register_dim(
        "scenario",
        DimSpec(
            name="scenario",
            index=scen_idx,
            view_factory=ScenarioView.minimal,
            full_view_factory=ScenarioDetailView.from_scenario,
            actions={},
        ),
    )

    # Seeds (Phase α). id 命名 = "<system>.<name>",scenario 用自身 scenarioId 作 key。
    from gimbal_plate.systems.fin.system_info import FIN_SYSTEM

    cfg_idx.register(fin_config_template(),   item_id=f"{FIN_SYSTEM}.default")
    meta_idx.register(fin_meta_template(),    item_id=f"{FIN_SYSTEM}.default")
    res_idx.register(fin_resource_template(), item_id=f"{FIN_SYSTEM}.tidb_test")
    scen_idx.register(fin_scenario_template())


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
            code="internal_error",
            message=str(exc) or exc.__class__.__name__,
            http_status=500,
        )
        return JSONResponse(status_code=status, content=body)

    @app.get("/healthz", include_in_schema=False)
    async def _healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(grammar_router)

    return app


__all__ = ["create_app", "_register_fin_dims"]