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
