"""Pytest configuration: per-test isolated DB + ASGI client fixture.

The spec-1 tests share an ``AsyncClient``-per-test instance but the ``engine``
in :mod:`app.core.db` is module-global and points at ``./data/app.db``.  Without
isolation, consecutive tests in the same ``pytest`` invocation will collide on
unique-username and similar constraints.

This conftest swaps ``app.core.db.engine`` and ``SessionLocal`` for a per-test
in-memory-style SQLite engine (backed by a tempfile in ``tmp_path`` so the
file is cleaned up automatically) and runs ``Base.metadata.create_all`` to
provision the schema before each test.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app import models  # noqa: F401  register all models on Base.metadata
from app.models import AuthSession  # noqa: F401  explicit re-export to register table
from app.core import db as db_module
from app.core.db import Base
from app.main import create_app

logger = logging.getLogger(__name__)


@pytest.fixture
async def fresh_db(monkeypatch, tmp_path) -> AsyncGenerator[None, None]:
    """Swap the global DB engine for a per-test SQLite file + create schema."""
    db_file = tmp_path / "test.db"
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        echo=False,
        future=True,
    )
    test_session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )
    monkeypatch.setattr(db_module, "engine", test_engine, raising=True)
    monkeypatch.setattr(db_module, "SessionLocal", test_session_factory, raising=True)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield
    finally:
        await test_engine.dispose()


@pytest.fixture(autouse=True)
def _isolate_marks(tmp_path, monkeypatch):
    """Point the marks store (stars) at the per-test tmp dir.

    Without this, marks written by one test pollute the next test in the
    same pytest run (and any local ``data/stars.json`` from prior runs).
    """
    from app.services.marks_store import stars

    stars.path = tmp_path / "stars.json"
    stars.clear_for_tests()
    yield
    stars.clear_for_tests()


@pytest.fixture(autouse=True)
def _default_plate_stub():
    """Hermeticity default: safe plate stub for tests without an explicit mock.

    ``plate_client.get_client`` lazily builds a real client against
    ``settings.PLATE_BASE_URL`` (localhost:8765) — since T9 any un-mocked
    test that reaches ``build_carry_context`` (POST /api/runs, preview-plate
    overlay) would hit the real network through ``catalog_service_names`` /
    ``_carry_face``. This autouse fixture installs a MockTransport default
    FIRST; explicit mocks (``plate_mock`` / ``plate`` / per-test
    ``set_client_for_tests``) overwrite it later — autouse fixtures are
    instantiated before same-scope explicitly-requested ones, so the
    explicit mock always wins. Teardown is LIFO: the explicit mock's
    ``set_client_for_tests(None)`` runs before ours (idempotent reset).

    Responses mirror the degraded path these callers already take on real
    plate failure: ``/api/service`` → empty catalog (``catalog_service_names``
    → set()), ``/api/endpoint/*/full`` → 404 (``_carry_face`` → {}), anything
    else (convert) → 503 → ``PlateUnavailableError`` (same 502 the router
    already returns on connection-refused).
    """
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/service":
            return httpx.Response(200, json={
                "ok": True, "dim": "service",
                "data": {"items": [], "total": 0},
            })
        if path.startswith("/api/endpoint/") and path.endswith("/full"):
            return httpx.Response(404, json={"ok": False})
        return httpx.Response(503, json={"ok": False})

    from app.services import plate_client

    # 与既有 mock 桩同款:AsyncClient 不走 socket,uninstall 也不 aclose。
    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://plate-test-default",
    ))
    try:
        yield
    finally:
        plate_client.set_client_for_tests(None)


@pytest.fixture
async def client(fresh_db) -> AsyncGenerator[AsyncClient, None]:
    """ASGI test client wired to a freshly-built FastAPI app.

    ``ASGITransport`` does not trigger lifespan by default; the schema is
    already provisioned by ``fresh_db`` so the app can serve requests
    immediately.
    """
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class EndpointPlateMock:
    """Programmable plate mock for the endpoint dim(适配域测试共享)。

    ``items``:GET /api/endpoint 轻量列表(id/version/updated_at);
    ``fulls``:endpoint_id → full spec(GET /api/endpoint/{id}/full);
    ``full_down``:这些 id 的 /full 抛 ConnectError(单端点级故障);
    ``down=True``:一切请求抛 ConnectError(plate 不可达)。
    """

    def __init__(self) -> None:
        self.items: list[dict] = []
        self.fulls: dict[str, dict] = {}
        self.full_down: set[str] = set()
        self.down = False

    def install(self) -> None:
        mock = self

        def handler(request: httpx.Request) -> httpx.Response:
            if mock.down:
                raise httpx.ConnectError("connection refused", request=request)
            path = request.url.path
            if path == "/api/endpoint":
                return httpx.Response(200, json={
                    "ok": True, "dim": "endpoint",
                    "data": {"items": mock.items, "total": len(mock.items)},
                })
            if path.endswith("/full"):
                eid = path.rsplit("/", 2)[-2]
                if eid in mock.full_down:
                    raise httpx.ConnectError("connection refused",
                                             request=request)
                if eid in mock.fulls:
                    return httpx.Response(200, json={
                        "ok": True, "dim": "endpoint",
                        "data": {"item": mock.fulls[eid], "total": 1},
                    })
            return httpx.Response(404, json={"ok": False})

        from app.services import plate_client

        plate_client.set_client_for_tests(httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://plate-test",
        ))

    def uninstall(self) -> None:
        from app.services import plate_client

        plate_client.set_client_for_tests(None)


@pytest.fixture
def plate():
    mock = EndpointPlateMock()
    mock.install()
    try:
        yield mock
    finally:
        mock.uninstall()
