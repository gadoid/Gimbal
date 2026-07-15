"""SQLAlchemy async engine + session factory."""
from __future__ import annotations

from typing import AsyncGenerator

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .config import settings  # noqa: E402

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Schema-only changes that need ALTER TABLE ADD COLUMN when an existing
# DB predates the new column.  Append-only — never edit a released entry.
_COLUMN_ADDITIONS: dict[str, dict[str, str]] = {
    "exec_runs": {
        "log_path": "TEXT",
        "command_line": "TEXT",
    },
}


async def _auto_add_columns() -> None:
    """Back-fill columns declared in ``_COLUMN_ADDITIONS`` for any DB
    that already has the table from a previous deployment.  No-op when
    the table is fresh (create_all already wrote every column)."""
    async with engine.begin() as conn:
        for table, cols in _COLUMN_ADDITIONS.items():
            try:
                rows = await conn.run_sync(
                    lambda sync_conn: list(
                        sync_conn.execute(
                            text(
                                f"PRAGMA table_info({table})"  # noqa: S608
                            )
                        ).fetchall()
                    )
                )
                existing = {row[1] for row in rows}
            except Exception as e:  # noqa: BLE001
                logger.debug(
                    "auto-migrate: skip {} ({}); will be created", table, e
                )
                continue
            for col, decl in cols.items():
                if col in existing:
                    continue
                stmt = text(
                    f"ALTER TABLE {table} ADD COLUMN {col} {decl}"  # noqa: S608
                )
                try:
                    await conn.execute(stmt)
                    logger.info("auto-migrate: added {}.{}", table, col)
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "auto-migrate: failed to add {}.{} ({}): {}",
                        table,
                        col,
                        decl,
                        e,
                    )


async def init_db() -> None:
    """Create tables; idempotent.  Also back-fills any new columns
    declared in ``_COLUMN_ADDITIONS`` so existing DBs don't need a wipe."""
    from .. import models  # noqa: F401  注册所有模型

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _auto_add_columns()
