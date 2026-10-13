"""Alembic 环境(M2:双方言统一,async 驱动 → 同步驱动执行)。

* 连接串来自 ``settings.DATABASE_URL``,asyncpg/aiosqlite 翻译为
  psycopg/sqlite3(迁移用同步连接即可);
* ``target_metadata`` 指向 app 模型 —— 只服务 autogenerate 起草,
  revision 一经定稿即自带全部 DDL(冻结于落笔时)。
"""
from __future__ import annotations

import re
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.core.config import settings
from app.core.db import Base
from app import models  # noqa: F401  注册全部模型

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    # URL 优先级:Config 显式携带(ensure_schema_sync / 测试注入的目标库)
    # > settings.DATABASE_URL(CLI `alembic upgrade` 直跑)。此前无条件
    # 用 settings —— ensure_schema_sync(url) 的入参被静默吞掉,空库门
    # 测试跑到了 .env 指向的库上(2026-10-13 A-1)。
    url = context.config.get_main_option("sqlalchemy.url")
    if not url:
        url = settings.DATABASE_URL
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    url = url.replace("sqlite+aiosqlite://", "sqlite://")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # SQLite 的 ALTER 面窄:统一 batch(建新表→拷数据→换名)
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
