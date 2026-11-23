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

import asyncio
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
from app.models import AuthAccount, ServiceIdentity  # noqa: E402,F401  explicit re-export to register tables
from app.core import db as db_module  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.main import create_app  # noqa: E402
# B6③:真 ServerSession 类在此捕获(fresh_db 垫片安装前)——
# 真实引擎 e2e 用 real_engine_session fixture 还原垫片。
from app.services.gimbal_server_session import (  # noqa: E402
    ServerSession as _REAL_SESSION_CLS,
)

# ── 套件提速(2026-11-21):bcrypt 轮数钉 4 ─────────────────────────
# 缺省 12 轮 ≈ 哈希/校验各 ~170ms;大量用例每测注册+登录(哈希 1 次 +
# 校验 1 次)≈ 0.34s/测,2164 用例仅此一项 ≈ 12 分钟。钉 4 轮后各
# ~1ms —— 仍是真 bcrypt(格式/校验语义不变;authz 用例覆盖的是流程
# 与令牌,不是计算成本)。显式传 rounds 的调用不受影响(只抬缺省)。
import bcrypt as _bcrypt  # noqa: E402

_gensalt_real = _bcrypt.gensalt


def _gensalt_fast(rounds: int = 4, prefix: bytes = b"2b", **kw):  # noqa: ANN001, ANN002
    return _gensalt_real(rounds=max(rounds, 4), prefix=prefix, **kw)


_bcrypt.gensalt = _gensalt_fast  # type: ignore[assignment]

# P1-7 迁移期垫片(旧模块名 service_alias/auth_session/service_meta →
# 新模型)已随 Phase 3 文案清账删除 —— 全部消费方已切 ServiceIdentity/
# AuthAccount 直连导入;如再被引用即 ImportError,不做静默兜底。
logger = logging.getLogger(__name__)


async def seed_identity_fixture(
    db, *, alias: str, username: str, password: str,
    service: str = "fin-service", system: str | None = None,
    env_name: str = "测试", login_url: str = "https://svc.internal",
    base_url: str | None = "https://svc-deploy.internal",
    owner_id: "int | None" = None, project_id: "int | None" = None,
    is_default: bool = True, ref_mode: str = "username",
    account_fields: dict | None = None,
    token_type: str = "Bearer", expires_in: int = 7200,
) -> int:
    """四件套一键布景(重构 §4.1 测试范式):环境 + 主档 + 账户 + 身份
    条目。旧「单建 AuthSession 行」的测试布景在此收敛 —— 新解析链
    (条目→ref→账户)要求四件齐全。返回账户 id。

    M3 §8.5(2026-11-17)补第五件:部署行(``base_url``,幂等;传
    ``base_url=None`` 跳过)—— 派发硬门要求地址落点,布景不再依赖
    「引擎缺口报错」兜底。"""
    from sqlalchemy import select

    from app.core.security import fernet_encrypt
    from app.models import (
        AuthAccount, Deployment, Environment, Service, ServiceIdentity,
        SystemEnvInstance,
    )

    env = (await db.execute(
        select(Environment.id).where(
            Environment.name == env_name))).scalar_one_or_none()
    if env is None:
        db.add(Environment(name=env_name, is_default=True))
        await db.flush()
        env = (await db.execute(
            select(Environment.id).where(
                Environment.name == env_name))).scalar_one()
    from sqlalchemy import select as _sel

    if (await db.execute(_sel(Service.id).where(
            Service.name == service))).scalar() is None:
        db.add(Service(name=service, system=system or service, kind="plate"))
    if login_url:
        from sqlalchemy import select as _sel2

        have_inst = (await db.execute(_sel2(SystemEnvInstance.id).where(
            SystemEnvInstance.system == (system or service),
            SystemEnvInstance.env_id == env))).scalar()
        if have_inst is None:
            db.add(SystemEnvInstance(
                system=system or service, env_id=env, login_url=login_url))
    if base_url:
        from sqlalchemy import select as _sel3

        have_dep = (await db.execute(_sel3(Deployment.id).where(
            Deployment.base_service == service,
            Deployment.env_id == env))).scalar()
        if have_dep is None:
            db.add(Deployment(base_service=service, env_id=env,
                              base_url=base_url))
    acc = AuthAccount(
        owner_id=owner_id, project_id=project_id,
        system=system or service, env_id=env, username=username,
        password_enc=fernet_encrypt(password), token_type=token_type,
        expires_in=expires_in, account_fields=account_fields or {},
        is_default=is_default)
    db.add(acc)
    db.add(ServiceIdentity(
        alias_name=alias, base_service=service, env_id=env,
        ref_mode=ref_mode,
        ref_username=(username if ref_mode == "username" else "")))
    await db.commit()
    return acc.id



async def _make_pg_engine(dsn: str, search_path: str | None = None):
    connect_args = (
        {"server_settings": {"search_path": search_path}} if search_path else {}
    )
    return create_async_engine(dsn, echo=False, future=True,
                               connect_args=connect_args)


# ── schema 池(2026-11-21 套件提速)───────────────────────────────
# 原「每测试 CREATE SCHEMA + create_all(几十张表)+ DROP SCHEMA
# CASCADE」≈ 0.6s/测,是 30 分钟套件的最大单项。PG16 无 CREATE
# SCHEMA ... TEMPLATE(17 才有)→ 进程内单池:每进程一个池 schema
# (首次进入建全套结构),此后每测一条 ``TRUNCATE ... RESTART
# IDENTITY CASCADE`` 复位 —— 行清零 + 序列归 1 + 公共项目种子重种
# = 与「每测新 schema」同一张白纸。fresh_db 消费面只把 schema 当
# 行存储:迁移/空库自举测试自建独立 schema 不经此池。池 schema
# 会话结束(sessionfinish)落删;硬崩溃残留由下次会话启动清扫
# (pid 已死的才删,活进程的池不动 —— 并行 pytest 会话安全)。
_POOL_SCHEMA = f"t_pool_{os.getpid()}"
_pool_built = False

# M2a S1.1:公共项目行是运行时依赖(迁移链 0040/0041 种子;测试走
# create_all 不跑迁移 → 补同一颗种子,幂等)。建池与每测复位共用。
_PUBLIC_PROJECT_SEED_SQL = (
    "INSERT INTO projects (name, kind, description, created_at) "
    "SELECT '公共', 'public', '', now() WHERE NOT EXISTS ("
    "  SELECT 1 FROM projects WHERE kind = 'public')")


async def _drop_schemas(names: list[str]) -> None:
    if not names:
        return
    admin = await _make_pg_engine(TEST_DATABASE_URL)
    try:
        async with admin.begin() as conn:
            for n in names:
                await conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{n}" CASCADE')
    finally:
        await admin.dispose()


def _pid_alive(pid: int) -> bool:
    """Windows 侧活进程探测(清扫只删死 pid 的残留池)。"""
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    try:
        h = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    except Exception:  # noqa: BLE001 — 探测失败按死处理(残留惰性,不急)
        return False


async def _sweep_stale_pools() -> None:
    """清扫硬崩溃残留的池 schema(t_pool_<pid>,pid 已死才删)。

    只在非 xdist worker 进程执行:xdist 下 controller 收集期先于
    worker spawn 导入本文件 → controller 扫一次,worker 不扫,
    避免互删活跃池。"""
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    admin = await _make_pg_engine(TEST_DATABASE_URL)
    try:
        async with admin.begin() as conn:
            rows = (await conn.exec_driver_sql(
                "SELECT nspname FROM pg_namespace "
                "WHERE nspname LIKE 't\\_pool\\_%' "
                "   OR nspname ~ '^t_[0-9a-f]{32}$'")).scalars().all()
    finally:
        await admin.dispose()
    stale = []
    for name in rows:
        name = str(name)
        # 旧 uuid 格式(t_<32hex>)是上一代隔离设计的残留 —— 该设计已
        # 随池化退役,一律视为死物;池格式按 pid 探活。
        if name.startswith("t_pool_"):
            try:
                pid = int(name.rsplit("_", 1)[-1])
            except ValueError:
                continue
            if pid == os.getpid() or _pid_alive(pid):
                continue
        stale.append(name)
    if stale:
        logger.info("清扫死进程残留池 schema:%s", ", ".join(stale))
        await _drop_schemas(stale)


async def _ensure_pool_schema() -> None:
    """首次进入建池:全套 DDL + 公共项目种子 + suite 触发器(幂等)。"""
    global _pool_built
    if _pool_built:
        return
    from sqlalchemy import text

    from app.services.zone import SUITE_ZONE_TRIGGER_DDL

    admin = await _make_pg_engine(TEST_DATABASE_URL)
    try:
        async with admin.begin() as conn:
            await conn.exec_driver_sql(
                f'DROP SCHEMA IF EXISTS "{_POOL_SCHEMA}" CASCADE')
            await conn.exec_driver_sql(f'CREATE SCHEMA "{_POOL_SCHEMA}"')
    finally:
        await admin.dispose()

    build = await _make_pg_engine(
        TEST_DATABASE_URL, search_path=f"{_POOL_SCHEMA},public")
    try:
        async with build.begin() as conn:
            # checkfirst 必须关(同旧口径:search_path 含 public 时同名
            # 误判「已存在」→ 一张不建 → 读写穿透到 public 生产表)。
            await conn.run_sync(
                lambda ddl: Base.metadata.create_all(ddl, checkfirst=False))
            await conn.execute(text(_PUBLIC_PROJECT_SEED_SQL))
            # M2a S1.5:suite_members 同区触发器(迁移链由 0042 挂;
            # 测试库走 create_all → 同一 DDL 单源补挂)
            for stmt in SUITE_ZONE_TRIGGER_DDL:
                await conn.execute(text(stmt))
    finally:
        await build.dispose()
    _pool_built = True


class ShimServerSession:
    """B6③(2026-11-23):server 链测试垫片 —— 生产恒 server 链后,
    引擎行为统一走 ``tests/_fake_engine.launch`` 缝。

    ``run_case`` 以 legacy 期同款 kwargs(step_to/report_dir/cwd/
    engine_log_path/on_event/on_log/log_counters/n_runs)委托假引擎,
    各用例 monkeypatch 的 fake(写工件/发事件/返回 LaunchResult)
    形状不变;``start`` 捕获池侧透传的 ``on_log/log_counters``(AD2)
    原样转发,日志事件路径保持。``slot`` 读写均吞(池 _spawn 会盖章,
    垫片不具备 per-slot 引擎日志,维持 ``server_slot=None`` 工件路由)。
    需要真 server 会话语义(取消握手/能力位/SSE/真引擎)的专项用例
    自行 monkeypatch ``gimbal_server_session.ServerSession`` 覆盖本垫片
    (先例 test_graph_cancel_unit / test_plate_gimbal_contract)。
    """

    server_version = "shim-legacy-launch"
    cancel_scopes = ("step", "unit")

    def __init__(self) -> None:
        self._on_log = None
        self._log_counters = None

    # 池 _spawn 无条件 s.slot = slot;垫片不具备槽位语义(读恒 None,
    # 写吞掉)—— server_slot 不盖章,case 工件路由与 legacy 期一致。
    @property
    def slot(self):  # noqa: ANN201 — 测试垫片,类型从简
        return None

    @slot.setter
    def slot(self, _v) -> None:
        return None

    async def start(self, *, engine_log_path=None, cwd=None,
                    on_log=None, log_counters=None, **_kw) -> None:
        self._on_log = on_log
        self._log_counters = log_counters

    async def close(self) -> None:
        return None

    async def cancel(self, *, scope: str = "step") -> bool:
        return False   # 垫片不模拟取消握手;取消语义用例自带 FakeServerSession

    async def run_case(self, case_path, *, halt_at=None, n_runs: int = 1,
                       parallel: int = 1, debug=None, m2_info=None,
                       timeout=None, on_event=None):
        from pathlib import Path

        from tests import _fake_engine

        case_dir = Path(case_path).parent
        return await _fake_engine.launch(
            case_path,
            step_to=halt_at,
            report_dir=case_dir / "reports",
            cwd=case_dir,
            engine_log_path=case_dir / "engine.log",
            on_event=on_event,
            on_log=self._on_log,
            log_counters=self._log_counters,
            n_runs=n_runs,
        )


@pytest.fixture
def real_engine_session(monkeypatch):
    """还原 conftest 垫片 → 真 ServerSession(真引擎 server 形态)。

    供真实引擎 e2e 用(r6 按值掩码 / p35 对账五形态 / plate↔gimbal
    契约):dispatch 经真会话 spawn ``gimbal run server`` 并以
    POST /runs + SSE 驱动 —— B6③ 前这些用例走 legacy 真子进程,
    现统一切 server 形态。"""
    from app.services import gimbal_server_session as gss

    monkeypatch.setattr(gss, "ServerSession", _REAL_SESSION_CLS,
                        raising=True)


@pytest.fixture
async def fresh_db(monkeypatch) -> AsyncGenerator[None, None]:
    """Swap the global DB engine onto the process's pooled schema(每测行级白纸).

    PG-only(SQLite 已退役):连进来的会话 search_path 钉在池 schema
    上;TEST_DATABASE_URL 缺失在 conftest 导入期即中止会话。
    """
    # B6③(2026-11-23):legacy 链退役,EXEC_CHAIN 键已删 —— 生产恒
    # server 链。server 会话以 ShimServerSession 垫片替换(引擎行为走
    # tests/_fake_engine.launch 缝);真会话语义(SSE/取消握手/能力位)
    # 由专项用例自带 FakeServerSession 或还原真 ServerSession 覆盖
    # (先例 test_graph_cancel_unit / test_plate_gimbal_contract)。
    from app.core.config import settings as _settings
    from app.services import gimbal_server_session as _gss

    monkeypatch.setattr(_gss, "ServerSession", ShimServerSession, raising=True)

    # 阶段 3(2026-11-21):生产 .env 已切 enforce —— 套件与 .env 取值
    # 解耦(同 EXEC_CHAIN 先例):缺省钉回 off,登记/同 base 闸行为由
    # 专项用例显式 monkeypatch 三态(identity_registry_gate /
    # auth_drafts / admin_cleanup_survey 等),不受环境配置漂移影响。
    monkeypatch.setattr(_settings, "REGISTRY_ONLY_IDENTITIES", "off",
                        raising=True)
    # 服务引用注册化同款(架构终态,2026-11-21):生产 .env 已切
    # enforce —— 套件缺省钉 off,闸行为由专项用例显式三态
    # (test_service_reference_gate.py),不受环境配置漂移影响。
    monkeypatch.setattr(_settings, "REGISTRY_ONLY_SERVICES", "off",
                        raising=True)

    await _ensure_pool_schema()

    # 引擎仍每测新建:asyncpg 连接绑定事件循环,pytest-asyncio 每测
    # 一个 loop → 池跨 loop 复用必炸。每测一次 connect(~10ms),
    # 相比原 3 引擎 + 全套 DDL 已省 95%+。
    test_engine = await _make_pg_engine(
        TEST_DATABASE_URL, search_path=f"{_POOL_SCHEMA},public")
    test_session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr(db_module, "engine", test_engine, raising=True)
    monkeypatch.setattr(db_module, "SessionLocal", test_session_factory,
                        raising=True)

    async with test_engine.begin() as conn:
        # 白纸复位:一条 TRUNCATE(CASCADE 解 FK;RESTART IDENTITY
        # 归序列)—— 语义等价「每测新 schema」。
        tables = ", ".join(
            f'"{t.name}"' for t in Base.metadata.sorted_tables)
        await conn.exec_driver_sql(
            f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
        from sqlalchemy import text

        await conn.execute(text(_PUBLIC_PROJECT_SEED_SQL))

    try:
        yield
    finally:
        # dispatcher 后台行落库与下一测 TRUNCATE 的互锁防御:先等收尾
        # (后台尾巴若晚到,写的是已复位的行表,不再与 DDL 互锁)。
        from app.services.run_dispatcher import wait_dispatchers_quiescent

        await wait_dispatchers_quiescent()
        await test_engine.dispose()


def pytest_sessionfinish(session, exitstatus) -> None:
    """池 schema 落删:每测不删、会话统一删(新起循环;失败不盖结果
    —— 硬崩溃残留由下次会话启动清扫兜底)。"""
    global _pool_built
    if not _pool_built:
        return
    _pool_built = False
    try:
        asyncio.run(_drop_schemas([_POOL_SCHEMA]))
    except Exception:  # noqa: BLE001 — 清理失败不盖测试结果
        logger.warning("池 schema 落删失败(下次启动清扫兜底)",
                       exc_info=True)


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


# 启动清扫(硬崩溃残留的死进程池;xdist:controller 收集期先于 worker
# spawn 执行,worker 侧自短路 —— 见 _sweep_stale_pools)。失败不阻断会话。
try:
    asyncio.run(_sweep_stale_pools())
except Exception:  # noqa: BLE001 — 清扫失败不阻断测试
    logger.warning("池残留清扫失败(不影响测试;残留 schema 下次再清)",
                   exc_info=True)
