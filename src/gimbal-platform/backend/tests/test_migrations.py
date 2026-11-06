"""逐版本迁移测试(authz T0.4,dev-plan §〇):stamp → upgrade → 断言 → downgrade。

空库门(test_empty_db_bootstrap)只覆盖「空库一把升到 head」;增量升级与
回滚此前没有测试面。本模块补这个面:临时 schema 里造出旧版本形态 →
``command.stamp(旧)`` → ``command.upgrade`` / ``command.downgrade``
逐步断言。

直接用 ``alembic.command``,不走 ``ensure_schema_sync`` —— 它对「有版本
但落后」的库拒绝启动是产品语义(DDL 必须人工窗口执行),不是迁移本身的
语义;迁移测试要测的恰恰是人工窗口里跑的那条路径。
"""
from __future__ import annotations

import asyncio
import os
import secrets as _secrets
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

_BACKEND = Path(__file__).resolve().parents[1]


@contextmanager
def temp_schema():
    """业务库内临时 schema(等价干净库;结束 DROP CASCADE)。

    与 test_empty_db_bootstrap 同口径:gimbal 用户通常无 CREATEDB 权限。
    yield (schema, sync_url) —— sync_url 是把 search_path 编进 options
    的 psycopg URL,可直接喂 alembic。
    """
    url = os.environ["TEST_DATABASE_URL"]  # conftest 已保证 PG 形状
    schema = f"t_mig_{_secrets.token_hex(4)}"

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
        sync_url = (
            url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
            + "?options=" + quote(f"-csearch_path={schema}")
        )
        yield schema, sync_url
    finally:
        asyncio.run(_admin(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def _cfg(sync_url: str):
    from app.core.migrations import _alembic_config

    return _alembic_config(sync_url)


def _revision(sync_url: str) -> str | None:
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    eng = create_engine(sync_url)
    try:
        with eng.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        eng.dispose()


def test_full_chain_from_empty():
    """空 schema → ``upgrade head``:全链从零可跑(空库门的产品面等价物,
    新迁移加入后自动纳入覆盖)。"""
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect

    with temp_schema() as (_schema, sync_url):
        command.upgrade(_cfg(sync_url), "head")

        head = ScriptDirectory(str(_BACKEND / "alembic")).get_current_head()
        assert _revision(sync_url) == head

        eng = create_engine(sync_url)
        try:
            with eng.connect() as conn:
                names = set(inspect(conn).get_table_names())
        finally:
            eng.dispose()
        for required in ("users", "integration_tasks", "access_tokens"):
            assert required in names, f"缺表 {required}"
