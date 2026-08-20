"""FastAPI app factory.

Exposes ``create_app()`` for tests + ASGI servers, plus a ``uvicorn``-friendly
``app`` module-level instance.  Wires CORS, the lifespan that runs ``init_db``
on startup, and the V3 router set (auth/scenarios/runs/executions/…).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .core.config import settings
from .core.db import init_db
from .routers import (
    auth,
    auth_sessions,
    data_sets,
    endpoint_catalog,
    envs,
    executions,
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
    # Loud, actionable warnings when crypto secrets are ephemeral — every
    # restart silently rotates them otherwise (all sessions dropped, all
    # Fernet-encrypted credentials undecryptable).
    if settings.JWT_SECRET_EPHEMERAL:
        logger.warning(
            "JWT_SECRET not configured — generated a random secret for THIS "
            "process only. Every restart invalidates all issued tokens. "
            "Set JWT_SECRET in backend/.env for persistent sessions."
        )
    if settings.FERNET_KEY_EPHEMERAL:
        logger.warning(
            "FERNET_KEY not configured — generated a random key for THIS "
            "process only. Every restart makes previously stored auth-"
            "session ciphertexts undecryptable. Set FERNET_KEY in "
            "backend/.env (keep a backup)."
        )
    from .services import gimbal_client as gimbal_client_module
    from .services import plate_client as plate_client_module
    from .services.run_dispatcher import drain_in_flight_dispatches

    sweeper_task = asyncio.create_task(_log_hub_sweeper())
    try:
        yield
    finally:
        # V3 场景编排:取消并等待所有在途的逐行 dispatch 任务。
        # (P4 起 V1 子进程 orchestrator/孤儿回收已随 executor.py 退役)
        n_dispatched = await drain_in_flight_dispatches()
        if n_dispatched:
            logger.info("lifespan: drained {} in-flight dispatcher(s)", n_dispatched)
        # Close the shared Plate httpx client (graceful socket close).
        try:
            await plate_client_module.aclose()
        except Exception as e:  # noqa: BLE001
            logger.debug("lifespan: plate_client.aclose raised {}", e)
        # …and the Gimbal runner client (#4 run chain).
        try:
            await gimbal_client_module.aclose()
        except Exception as e:  # noqa: BLE001
            logger.debug("lifespan: gimbal_client.aclose raised {}", e)
        sweeper_task.cancel()
        try:
            await sweeper_task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    """Build a fresh FastAPI app.  Safe to call multiple times (e.g. in tests)."""
    app = FastAPI(title="Gimbal Platform", version="0.1.0", lifespan=lifespan)

    # ── CORS ─────────────────────────────────────────────────────
    # Origins come from .env (CORS_ORIGINS, comma-separated); the
    # Vite dev server (5173) is allowed by default.  JWT rides the
    # Authorization header, not cookies, so ``allow_credentials`` is
    # kept False — Starlette rejects ``origins=["*"]`` together with
    # ``credentials=True`` and we never need cookie-mode CORS here.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(auth_sessions.router, prefix="/api")
    app.include_router(executions.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    # New V3 composer routers (registered in order so static suffixes
    # precede ``/{id}`` catch-alls).
    app.include_router(envs.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(data_sets.router, prefix="/api")
    # Dataset-create lives on a scenario-nested path but in the
    # data_sets module; register BEFORE scenarios' /{scenario_id}
    # catch-all.
    app.include_router(data_sets.create_router, prefix="/api")
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

