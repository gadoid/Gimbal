"""空库建库门(2026-10-13 A-1):首次部署起不来的回归网。

此前 0001 baseline 的 fresh 路径按**当前**模型 create_all 建全部表,
0013+ 的 create_table/add_column 无守卫即撞已存在 —— 空库
`alembic upgrade head` 必炸,而存量库走增量升级、测试走 conftest
create_all,双双覆盖不到。本门三段:

1. 真空库(SQLite 临时文件,env.py 的 URL 透传修好后才指得动目标库)
   → ``ensure_schema_sync`` → 成功即建到 head;
2. ``compare_metadata`` 为空 —— 迁移终态 == 当前模型,无漂移;
3. alembic_version 落在 head。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]


def _assert_head_and_no_drift(engine):
    from alembic.runtime.migration import MigrationContext
    from alembic.autogenerate import compare_metadata
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect
    from app.core.db import Base

    with engine.connect() as conn:
        diff = compare_metadata(
            MigrationContext.configure(conn), Base.metadata)
        # ⑤(2026-10-13):PG 面的 JSON/JSONB 同义比较 —— sa.JSON 与
        # JSONB 在 compare 里报类型差;漂移收口(0022)后按字面等价
        def _same(d):
            if not isinstance(d, tuple) or len(d) < 4:
                return False
            change = d[3]
            if isinstance(change, list) and change and isinstance(change[0], tuple):
                old, new = change[0][2], change[0][3]
                return str(old).startswith("JSON") and str(new).startswith("JSON")
            return False
        real = [d for d in diff if not _same(d)]
        assert real == [], f"迁移终态与模型漂移: {real[:5]}"
        current = MigrationContext.configure(conn).get_current_revision()
        head = ScriptDirectory(
            str(_BACKEND / "alembic")).get_current_head()
        assert current == head, f"{current} != {head}"
        names = set(inspect(conn).get_table_names())
        for required in ("users", "composer_scenarios", "executions",
                         "share_refs", "suites", "integration_tasks",
                         "external_endpoints"):
            assert required in names, f"缺表 {required}"


def test_empty_db_bootstraps_to_head(tmp_path, monkeypatch):
    # app.core.config 的 settings 在 import 期读 .env;env.py 已改为
    # Config URL 优先,但保险起见把 settings.DATABASE_URL 也指到临时库
    # —— 防 env.py 回退分支读到 dev PG。
    from app.core.config import settings

    db_file = tmp_path / "empty.db"
    monkeypatch.setattr(
        settings, "DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")

    from app.core.migrations import ensure_schema_sync

    ensure_schema_sync(f"sqlite+aiosqlite:///{db_file}")

    from alembic.runtime.migration import MigrationContext
    from alembic.autogenerate import compare_metadata
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine
    from app.core.db import Base

    engine = create_engine(f"sqlite:///{db_file}")
    try:
        with engine.connect() as conn:
            # ① 终态 == 当前模型(类型/键全比对)
            diff = compare_metadata(
                MigrationContext.configure(conn), Base.metadata)
            assert diff == [], f"迁移终态与模型漂移: {diff[:5]}"

            # ② 版本钉在 head
            current = MigrationContext.configure(conn).get_current_revision()
            head = ScriptDirectory(
                str(_BACKEND / "alembic")).get_current_head()
            assert current == head, f"{current} != {head}"

            # ③ 业务表真的建出来了(非空壳)
            names = set(
                __import__("sqlalchemy").inspect(conn).get_table_names())
            for required in ("users", "composer_scenarios", "executions",
                             "share_refs", "suites", "integration_tasks",
                             "external_endpoints"):
                assert required in names, f"缺表 {required}"
    finally:
        engine.dispose()


def test_empty_db_pg_face():
    """⑤(2026-10-13):空库门 PG 面 —— 仅 TEST_DATABASE_URL 提供时跑。

    SQLite 两态同型看不出 json/jsonb 漂移,PG 面是唯一能拦 0022 类
    回归的门。gimbal 用户通常无 CREATEDB 权限 → 用业务库内**临时
    schema**(search_path 单指)等价"空库";结束 DROP SCHEMA。
    """
    import asyncio
    import os

    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        import pytest
        pytest.skip("TEST_DATABASE_URL 未提供(设 postgresql+asyncpg://… 启用 PG 面)")

    import secrets as _secrets
    schema = f"t_emptydb_{_secrets.token_hex(4)}"

    async def _admin(stmt: str) -> None:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        eng = create_async_engine(url, isolation_level="AUTOCOMMIT")
        try:
            async with eng.connect() as c:
                await c.execute(text(stmt))
        finally:
            await eng.dispose()

    asyncio.run(_admin(f'CREATE SCHEMA "{schema}"'))
    try:
        from urllib.parse import quote
        from app.core.migrations import ensure_schema_sync, _sync_url

        sync_target = (_sync_url(url)
                       + "?options=" + quote(f"-csearch_path={schema}"))
        ensure_schema_sync(sync_target)

        from sqlalchemy import create_engine
        engine = create_engine(sync_target)
        # PG 面专项断言(全量 compare 由 SQLite 面把守;PG 的既有非阻断
        # 噪音 = trgm 索引未进模型 + environments 可空性,不属本门)
        from alembic.runtime.migration import MigrationContext
        from alembic.autogenerate import compare_metadata
        from alembic.script import ScriptDirectory
        from sqlalchemy import inspect
        import app.models  # noqa: F401 注册元数据
        from app.core.db import Base
        with engine.connect() as conn:
            diff = compare_metadata(
                MigrationContext.configure(conn), Base.metadata)
            type_drift = [
                d for d in diff
                if isinstance(d, tuple) and len(d) >= 4 and isinstance(d[3], list)
                and any(str(getattr(x[2], 'name', x[2])) != str(getattr(x[3], 'name', x[3]))
                        for x in d[3] if isinstance(x, tuple) and len(x) >= 4)
            ]
            assert type_drift == [], f"PG 类型漂移(json/jsonb 等): {type_drift[:4]}"
            current = MigrationContext.configure(conn).get_current_revision()
            head = ScriptDirectory(
                str(_BACKEND / "alembic")).get_current_head()
            assert current == head, f"{current} != {head}"
            names = set(x for x in inspect(conn).get_table_names())
        for required in ("users", "composer_scenarios", "executions",
                         "integration_tasks", "external_endpoints"):
            assert required in names, f"缺表 {required}"
        # ⑤ 核心回归面:JSON 列必须是 jsonb(不是 json)—— 唯一例外 =
        # external_endpoints.request_schema(2-4:顺序敏感列,JSONB 会按
        # 键长/字节序重排打乱表单字段序,x-order 盖章 + 列留 json 兜底)
        with engine.connect() as conn:
            rows = conn.exec_driver_sql(
                "select table_name, column_name from information_schema.columns "
                "where table_schema = %s and data_type = 'json'",
                (schema,)).fetchall()
        rows = [r for r in rows if r != ("external_endpoints", "request_schema")]
        assert rows == [], f"仍是 json 的列: {rows[:6]}"
        engine.dispose()
    finally:
        asyncio.run(_admin(
            f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
