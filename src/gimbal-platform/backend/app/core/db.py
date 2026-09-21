"""SQLAlchemy async engine + session factory."""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .config import settings  # noqa: E402

# Pool 参数仅对 PG 生效（PG迁移方案 §3.1）；aiosqlite 引擎不接受
# QueuePool 系参数，sqlite 路径保持零参构造不变。
_IS_PG = settings.DATABASE_URL.startswith(("postgresql://", "postgresql+"))

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    **(
        {"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True}
        if _IS_PG
        else {}
    ),
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
