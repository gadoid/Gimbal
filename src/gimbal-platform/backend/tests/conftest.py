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
import os
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

# PG 测试隔离(PG迁移方案 §3.4,M0-3 选型定案:schema-per-test):
# 设 TEST_DATABASE_URL(postgresql+asyncpg://...)时,每测试 CREATE SCHEMA +
# 钉 search_path + create_all,结束 DROP SCHEMA CASCADE——语义最贴近现行
# 「每测试一个临时 SQLite 库」,不碰被测代码的事务/commit 语义(事务回滚
# 路线与 run_dispatcher 后台线程的独立 session 相冲,未选)。不设则维持
# sqlite 临时文件路径,双方言自律。
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


async def _make_pg_engine(dsn: str, search_path: str | None = None):
    connect_args = (
        {"server_settings": {"search_path": search_path}} if search_path else {}
    )
    return create_async_engine(dsn, echo=False, future=True,
                               connect_args=connect_args)


@pytest.fixture
async def fresh_db(monkeypatch, tmp_path) -> AsyncGenerator[None, None]:
    """Swap the global DB engine for a per-test isolated DB + create schema.

    sqlite(默认): 每测试一个临时文件库;PG(设 TEST_DATABASE_URL 时):
    每测试一个独立 schema,连进来的会话 search_path 钉在该 schema 上。
    """
    if TEST_DATABASE_URL.startswith("postgresql"):
        import uuid

        schema = f"t_{uuid.uuid4().hex}"
        admin = await _make_pg_engine(TEST_DATABASE_URL)
        async with admin.begin() as conn:
            await conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        await admin.dispose()

        test_engine = await _make_pg_engine(
            TEST_DATABASE_URL, search_path=f"{schema},public"
        )
        test_session_factory = async_sessionmaker(
            test_engine, expire_on_commit=False, class_=AsyncSession
        )
        monkeypatch.setattr(db_module, "engine", test_engine, raising=True)
        monkeypatch.setattr(db_module, "SessionLocal", test_session_factory,
                            raising=True)

        async with test_engine.begin() as conn:
            # checkfirst 必须关:search_path 含 public 时,checkfirst 会把
            # public 里的同名表误判为"已存在"→ 一张不建 → 读写全部穿透
            # 到 public(生产表)。全新 schema 无需 checkfirst。
            await conn.run_sync(
                lambda ddl: Base.metadata.create_all(ddl, checkfirst=False),
            )

        try:
            yield
        finally:
            # dispatcher 后台行落库与 DROP SCHEMA 的互锁防御:先等收尾
            from app.services.run_dispatcher import wait_dispatchers_quiescent

            await wait_dispatchers_quiescent()
            await test_engine.dispose()
            cleaner = await _make_pg_engine(TEST_DATABASE_URL)
            try:
                async with cleaner.begin() as conn:
                    await conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            finally:
                await cleaner.dispose()
        return

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
def _isolate_plate_contract_caches():
    """Reset the process-wide ``/full`` contract caches between tests.

    Two caches hold the same plate contract: ``endpoint_declarations``
    (declarations + projection) and ``plate_client`` (the whole item).

    Since the carry / declared-paths merge, ``carry_injection`` and the
    dangling-path judgement share ONE process cache (TTL
    ``settings.DECLARED_PATHS_TTL_SEC``).  Several tests mock the *same*
    endpoint id with *different* declarations, so whichever runs first
    poisons the rest for the rest of the TTL — the same discipline the
    frontend already applies per case to its ``/full`` cache.  Reset both
    before every test so each observes only its own plate mock.
    """
    from app.services import plate_client
    from app.services.endpoint_declarations import _reset_declared_paths_cache

    _reset_declared_paths_cache()
    plate_client._reset_full_cache_for_test()
    # M5 目录聚合的 30s TTL 是模块级 —— 测试间必须重置(否则上个测试的
    # plate mock 目录泄漏到下一个)。
    from app.routers.catalog import reset_catalog_cache_for_tests
    from app.services.auth_references import reset_counts_cache_for_tests

    reset_catalog_cache_for_tests()
    reset_counts_cache_for_tests()
    yield


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
    ``services``:GET /api/service 目录(service dim,data.items[].name —
    服务名别名推导的输入;缺省空 = plate 无目录,catalog 降级空集);
    ``down=True``:一切请求抛 ConnectError(plate 不可达)。
    """

    def __init__(self) -> None:
        self.items: list[dict] = []
        self.fulls: dict[str, dict] = {}
        self.full_down: set[str] = set()
        self.services: list[dict] = []
        self.down = False

    def install(self) -> None:
        mock = self

        def handler(request: httpx.Request) -> httpx.Response:
            if mock.down:
                raise httpx.ConnectError("connection refused", request=request)
            path = request.url.path
            if path == "/api/service":
                return httpx.Response(200, json={
                    "ok": True, "dim": "service",
                    "data": {"items": mock.services, "total": len(mock.services)},
                })
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
