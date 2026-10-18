"""Pytest configuration: per-test isolated DB + ASGI client fixture.

The spec-1 tests share an ``AsyncClient``-per-test instance but the ``engine``
in :mod:`app.core.db` is module-global.  Without isolation, consecutive tests
in the same ``pytest`` invocation will collide on unique-username and similar
constraints.

This conftest swaps ``app.core.db.engine`` and ``SessionLocal`` for a
per-test PG schema (``TEST_DATABASE_URL``, created/dropped automatically)
and runs ``Base.metadata.create_all`` to provision the schema before each
test. SQLite 方言已退役(2026-10-14)。
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

# PG 测试隔离(PG迁移方案 §3.4,M0-3 选型定案:schema-per-test):
# 每测试 CREATE SCHEMA + 钉 search_path + create_all,结束 DROP SCHEMA
# CASCADE —— 语义贴近原「每测试一个临时 SQLite 库」,不碰被测代码的
# 事务/commit 语义(事务回滚路线与 run_dispatcher 后台线程的独立
# session 相冲,未选)。
# SQLite 已退役(2026-10-14):不再有 sqlite 回退方言 —— 未提供
# TEST_DATABASE_URL(postgresql+asyncpg://...)即中止整个会话,与
# core/db.py 的运行时口径一致。**必须在任何 app 导入之前执行**:
# app.core.db 在 import 期校验 DATABASE_URL(空/非 PG 即 RuntimeError),
# CI 等无 .env 环境由这里把 DATABASE_URL 兜底指到测试库。
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

if not TEST_DATABASE_URL.startswith("postgresql"):
    pytest.exit(
        "后端测试需要 TEST_DATABASE_URL=postgresql+asyncpg://..."
        "(每测试独立 schema,自动建删)。SQLite 方言已于 2026-10-14 "
        "退役 —— 本地示例:TEST_DATABASE_URL=postgresql+asyncpg://"
        "gimbal:gimbal@127.0.0.1:15432/gimbal(docker compose -f "
        "compose.pg.yml 起库)。", returncode=3)

os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
# 测试面:大量用例自助注册多个账号 → 开放注册;密钥由 settings 临时生成
# (lifespan 不在 ASGITransport 下运行,放行仅为一致口径)。生产默认二者皆关。
os.environ.setdefault("REGISTRATION_OPEN", "true")
os.environ.setdefault("ALLOW_EPHEMERAL_SECRETS", "true")

from app import models  # noqa: E402,F401  register all models on Base.metadata
from app.models import AuthSession  # noqa: E402,F401  explicit re-export to register table
from app.core import db as db_module  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.main import create_app  # noqa: E402

logger = logging.getLogger(__name__)


async def _make_pg_engine(dsn: str, search_path: str | None = None):
    connect_args = (
        {"server_settings": {"search_path": search_path}} if search_path else {}
    )
    return create_async_engine(dsn, echo=False, future=True,
                               connect_args=connect_args)


@pytest.fixture
async def fresh_db(monkeypatch) -> AsyncGenerator[None, None]:
    """Swap the global DB engine for a per-test isolated schema + create_all.

    PG-only(SQLite 已退役):每测试一个独立 schema,连进来的会话
    search_path 钉在该 schema 上;TEST_DATABASE_URL 缺失在 conftest
    导入期即中止会话。
    """
    # P3.6:默认链已切 server(生产),测试钉回 legacy —— 大量用例按
    # legacy 假引擎(monkeypatch gimbal_launcher.launch)编写,默认拉真
    # server 实例会拖爆套件且伪 convert 场景被引擎拒绝。server 链由
    # 显式 chain_override/debug 的专项用例覆盖,不受此钉影响。
    from app.core.config import settings as _settings

    monkeypatch.setattr(_settings, "EXEC_CHAIN", "legacy", raising=True)

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
    plate_client._reset_revision_cache_for_test()
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
        if path == "/api/endpoint":
            # b2-7 唯一访问件(降级面:空目录,与 /api/service 同口径)
            return httpx.Response(200, json={
                "ok": True, "dim": "endpoint",
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
    plate_client.reset_catalog_cache_for_tests()  # b2-7:目录缓存不跨测试
    try:
        yield
    finally:
        plate_client.reset_catalog_cache_for_tests()  # b2-7:目录缓存不跨测试
        plate_client.set_client_for_tests(None)


@pytest.fixture(autouse=True)
async def _isolate_execution_workers():
    """C11：逐测试隔离执行队列 worker。

    worker 承接的 fanout 可能跨测试存活（测试断言完成后仍在收尾）——
    其 teardown 会 pop `_row_states[execution_id]`，而 fresh 库的执行 id
    从 1 重来，晚到的 pop 会砸掉**下一个测试**刚建的同号注册表
    （test_run_baseline + test_execution_rows 组合复现：live 行读回 0）。
    每测收尾停 worker（当前任务收口后再继续），隔离时序确定。
    """
    yield
    from app.services import execution_queue as _eq
    from app.services import run_dispatcher as _rd
    try:
        await _eq.stop_workers(timeout_s=10.0)
    except Exception:  # noqa: BLE001 — 隔离兜底,失败不盖测试结果
        _eq.reset_worker_state()
    _rd.reset_cancel_state()


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
        # (system, ref) → 修订快照的接口列表(GET /api/systems/{s}/endpoint?ref=)
        self.system_scoped: dict[tuple[str, str], list[dict]] = {}

    def install(self) -> None:
        from app.services import plate_client as _pc

        _pc.reset_catalog_cache_for_tests()  # b2-7:换桩先清目录缓存
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
            # (b2-7:/api/endpoint 走下方 mock.items 真行分支 —— 唯一访问件
            #  不改假件形状;kind 缺省由消费方按 sut 处理)
            # 系统作用域接口列表(带 ref → 修订快照;无匹配 → 404)
            if path.startswith("/api/systems/") and path.endswith("/endpoint"):
                system = path.split("/")[3]
                ref = request.url.params.get("ref", "")
                key = (system, ref)
                if key in mock.system_scoped:
                    scoped = mock.system_scoped[key]
                    return httpx.Response(200, json={
                        "ok": True, "dim": "endpoint",
                        "data": {"items": scoped, "total": len(scoped)},
                    })
                return httpx.Response(404, json={
                    "ok": False,
                    "error": {"code": "release_not_found",
                               "message": f"revision {ref!r} not found"},
                })
            if path == "/api/endpoint":
                # b2-7:items 为空但 services 有值(旧式用例只设 services)
                # → 合成扁平行,保持「目录派生」语义可达
                items = mock.items or [
                    {"id": f"{it.get('name')}.mock", "service": it.get("name"),
                     "system": it.get("system", "fin"),
                     "kind": it.get("kind", "sut")}
                    for it in mock.services
                ]
                return httpx.Response(200, json={
                    "ok": True, "dim": "endpoint",
                    "data": {"items": items, "total": len(items)},
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
