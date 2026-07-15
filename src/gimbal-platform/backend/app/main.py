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

from .core.config import settings
from .core.db import init_db
from .routers import auth, auth_sessions, cases, executions, hidden_profiles, users


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
    from .routers.executions import reconcile_orphan_runs
    await reconcile_orphan_runs()
    sweeper_task = asyncio.create_task(_log_hub_sweeper())
    try:
        yield
    finally:
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
    app.include_router(cases.router, prefix="/api")
    app.include_router(executions.router, prefix="/api")
    app.include_router(users.router, prefix="/api")

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


# Module-level instance for ``uvicorn app.main:app`` style runners.
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

