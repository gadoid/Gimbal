"""FastAPI app factory.

Exposes ``create_app()`` for tests + ASGI servers, plus a ``uvicorn``-friendly
``app`` module-level instance.  Wires CORS, the lifespan that runs ``init_db``
on startup, and the spec-1 router set (``auth`` + ``cases`` + ``users``).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.convertors import Convertor, register_url_convertor


# ── V3 case_id path-converter ────────────────────────────────────
# The V3 composer uses ``case-`` prefixed ids (e.g. ``case-001``).  We
# register a custom path-converter so the composer's GET/PATCH/DELETE
# /{case_id} only matches V3 ids, and the legacy ``app.routers.cases``
# ``/{case_id:path}`` catch-all (registered AFTER the composer) still
# serves legacy paths like ``/mine`` / ``/public`` / ``/upload`` /
# free-form ids.
class _V3CaseIdConverter(Convertor[str]):
    # 接受 case- 前缀 (手动命名) 或 sc- 前缀 (自动命名 `${scenarioId}-case-001`)
    # 不接受 legacy 静态路径 mine/public/upload (都不以 case-/sc- 开头)
    regex = r"(?:case|sc)-[a-z0-9-]+"

    def convert(self, value: str) -> str:
        return value

    def to_string(self, value: str) -> str:
        return value


register_url_convertor("v3_case_id", _V3CaseIdConverter())

from .core.config import settings
from .core.db import init_db
from .routers import (
    auth,
    auth_sessions,
    cases,
    cases_composer,
    data_sets,
    endpoint_catalog,
    envs,
    executions,
    hidden_profiles,
    runs,
    scenarios,
    strategy_catalog,
    users,
)


async def _log_hub_sweeper() -> None:
    """Background task: every ``LOG_HUB_SWEEP_INTERVAL_MIN`` minutes,
    drop DONE channels whose age exceeds ``LOG_HUB_TTL_HOURS``.

    Stops cleanly when the event loop is cancelled (lifespan teardown).
    """
    from .services.log_hub import hub

    interval = max(60, settings.LOG_HUB_SWEEP_INTERVAL_MIN * 60)
    ttl_seconds = settings.LOG_HUB_TTL_HOURS * 3600
    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return
        try:
            evicted = hub.sweep(ttl_seconds)
            if evicted:
                logger.info(
                    "log_hub: swept {} expired channel(s) (TTL={}h)",
                    evicted, settings.LOG_HUB_TTL_HOURS,
                )
        except Exception as e:  # noqa: BLE001  never let the sweeper die silently
            logger.warning("log_hub sweeper error: {}", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run schema creation on startup.  Also reconcile orphan exec rows
    left behind by a previous worker instance (uvicorn --reload restarts,
    OOMs, …) so /executions doesn't display permanently-stuck rows."""
    await init_db()
    from .routers.executions import (
        drain_in_flight_runners,
        reconcile_orphan_runs,
    )
    from .services import plate_client as plate_client_module
    from .services.run_dispatcher import drain_in_flight_dispatches

    await reconcile_orphan_runs()
    sweeper_task = asyncio.create_task(_log_hub_sweeper())
    try:
        yield
    finally:
        # Cancel + await all in-flight orchestrators so subprocess
        # children get a clean kill (each _safe_run already has
        # try/except that catches CancelledError) before the event
        # loop is torn down.  ``drain_in_flight_runners`` also flips
        # the module's ``_shutting_down`` flag so any in-flight
        # ``create_execution`` request returns a structured error
        # instead of starting a task that would vanish a moment later.
        n_drained = await drain_in_flight_runners()
        if n_drained:
            logger.info("lifespan: drained {} in-flight execution runner(s)", n_drained)
        # V3 scenario composer: also drain the per-row dispatch tasks.
        n_dispatched = await drain_in_flight_dispatches()
        if n_dispatched:
            logger.info("lifespan: drained {} in-flight dispatcher(s)", n_dispatched)
        # Close the shared Plate httpx client (graceful socket close).
        try:
            await plate_client_module.aclose()
        except Exception as e:  # noqa: BLE001
            logger.debug("lifespan: plate_client.aclose raised {}", e)
        sweeper_task.cancel()
        try:
            await sweeper_task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    """Build a fresh FastAPI app.  Safe to call multiple times (e.g. in tests)."""
    app = FastAPI(title="Gimbal Platform", version="0.1.0", lifespan=lifespan)

    # ── TEMP: CORS 全放开 (局域网调试) ────────────────────────────────
    # 原配置: 从 .env 读取 allow_origins, allow_credentials=True
    # 注意: Starlette 不允许 allow_origins=["*"] 与 credentials=True 共存,
    #       因此这里显式把 credentials 关掉。JWT 走 Authorization 头,
    #       不会被 CORS 视为 credentials,不受影响。
    # 恢复生产请改回上面的 env 读取 + allow_credentials=True。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(auth_sessions.router, prefix="/api")
    # hidden_profiles MUST come before cases (cases owns {case_id:path} which
    # would otherwise shadow the more-specific /hidden suffix route).
    app.include_router(hidden_profiles.router, prefix="/api")
    # V3 composer cases MUST be registered BEFORE the legacy cases
    # router: the composer's GET/PATCH/DELETE /{case_id} all require
    # the V3 ``case-`` pattern (Path(pattern=...)), so a request to
    # /api/cases/mine, /public, /upload falls through to the legacy
    # router, but a request to /api/cases/case-001 hits the composer
    # first.  Same for POST /cases/{case_id}/data-sets which has no
    # legacy equivalent.
    app.include_router(cases_composer.router, prefix="/api")
    app.include_router(cases.router, prefix="/api")
    app.include_router(executions.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    # New V3 composer routers (registered in order so static suffixes
    # precede ``/{id}`` catch-alls).
    app.include_router(envs.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(data_sets.router, prefix="/api")
    app.include_router(endpoint_catalog.router, prefix="/api")
    app.include_router(strategy_catalog.router, prefix="/api")
    app.include_router(scenarios.router, prefix="/api")  # MUST be last — has /{scenario_id}

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


# Module-level instance for ``uvicorn app.main:app`` style runners.
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

