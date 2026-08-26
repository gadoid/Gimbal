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
    adaptations,
    auth,
    auth_sessions,
    constants,
    data_sets,
    endpoint_catalog,
    envs,
    executions,
    generator_catalog,
    runs,
    scenarios,
    strategy_catalog,
    users,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: run schema creation and warn on ephemeral crypto secrets.
    Shutdown: drain in-flight dispatches and close the shared Plate /
    Gimbal httpx clients."""
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
    from .services import plate_client as plate_client_module
    from .services.run_dispatcher import (
        drain_in_flight_dispatches,
        reset_shutdown_state,
        startup_recovery,
    )

    # Same-process app reuse (tests) needs the shutdown flag cleared,
    # or dispatches silently skip their fan-out.
    reset_shutdown_state()
    # P3:重启后把丢失 _fanout 的 queued 僵尸单收敛为 failed。
    try:
        n_stale, _swept = await startup_recovery()
        if n_stale:
            logger.warning("lifespan: reconciled {} stale execution(s)", n_stale)
    except Exception as e:  # noqa: BLE001
        logger.error("lifespan: startup recovery failed: {}", e)
    try:
        yield
    finally:
        # V3 场景编排:取消并等待所有在途的逐行 dispatch 任务。
        # (P4 起 V1 子进程 orchestrator/孤儿回收已随 executor.py 退役;
        #  V3.2 起执行调用走 gimbal_launcher 子进程,无 HTTP 引擎客户端。)
        n_dispatched = await drain_in_flight_dispatches()
        if n_dispatched:
            logger.info("lifespan: drained {} in-flight dispatcher(s)", n_dispatched)
        # Close the shared Plate httpx client (graceful socket close).
        try:
            await plate_client_module.aclose()
        except Exception as e:  # noqa: BLE001
            logger.debug("lifespan: plate_client.aclose raised {}", e)


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
    app.include_router(constants.router, prefix="/api")
    app.include_router(generator_catalog.router, prefix="/api")
    app.include_router(adaptations.router, prefix="/api")
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

