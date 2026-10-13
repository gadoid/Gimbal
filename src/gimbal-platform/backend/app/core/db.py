"""SQLAlchemy async engine + session factory(PG-only)。

SQLite 已退役(2026-10-14):引擎构造即校验 URL 必须是 postgresql
方言,空值/sqlite:// 直接 RuntimeError 指路 —— 不再造本地回退库。
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .config import settings  # noqa: E402

if not settings.DATABASE_URL.startswith(("postgresql://", "postgresql+")):
    raise RuntimeError(
        "DATABASE_URL 未配置或不是 PostgreSQL(SQLite 已退役 2026-10-14)。"
        "复制 backend/.env.example 为 .env 并设置 "
        "DATABASE_URL=postgresql+asyncpg://...;测试侧设 TEST_DATABASE_URL"
        "(conftest 同口径 fail-fast)。")

# Pool 参数(PG迁移方案 §3.1)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create tables; idempotent. Schema changes ship as a DB rebuild —
    historical data is migrated out-of-band, never at startup."""
    from .. import models  # noqa: F401  注册所有模型

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
