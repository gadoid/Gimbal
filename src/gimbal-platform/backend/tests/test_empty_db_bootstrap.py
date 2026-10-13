"""空库建库门(2026-10-13 A-1):首次部署起不来的回归网。

此前 0001 baseline 的 fresh 路径按**当前**模型 create_all 建全部表,
0013+ 的 create_table/add_column 无守卫即撞已存在 —— 空库
`alembic upgrade head` 必炸,而存量库走增量升级、测试走 conftest
create_all,双双覆盖不到。本门三段(2026-10-14 SQLite 退役后 PG 单面,
temp schema 单搜索路径等价"干净空库",CI postgres:16 同口径):

1. 真空库(临时 schema,search_path 单指)→ ``ensure_schema_sync``
   → 成功即建到 head;
2. ``compare_metadata`` 为空 —— 迁移终态 == 当前模型,无漂移;
3. alembic_version 落在 head。
"""
from __future__ import annotations

from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]


def test_empty_db_pg_face():
    """⑤(2026-10-13):空库门 PG 面 —— SQLite 退役(2026-10-14)后
    唯一面。临时 schema(search_path 单指)等价"干净空库",CI 的
    postgres:16 service 同口径;gimbal 用户通常无 CREATEDB 权限,
    用业务库内临时 schema,结束 DROP SCHEMA。
    """
    import asyncio
    import os

    url = os.environ["TEST_DATABASE_URL"]   # conftest 已保证 PG 形状

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
        # PG 面专项断言(全量 compare 由 metadata 不变量测试把守;PG 的
        # 既有非阻断噪音 = trgm 索引未进模型 + environments 可空性,不属本门)
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
