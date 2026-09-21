"""启动分叉的 schema 策略(M2,PG迁移方案 §2.1 第七轮)。

create_all 时代结束;本模块是 lifespan 唯一的 schema 入口:

* **空库**(无业务表)→ ``alembic upgrade head`` 从零建起(baseline 的
  fresh 路径);
* **已有 alembic_version**:SQLite/本地 → 自动 ``upgrade head``;**PG →
  只校验不迁移**(current ≠ head 拒绝启动并打印待执行 revision —— DDL
  永远由人在带备份的窗口里手动执行,启动自动 upgrade 是脚枪);
* **存量 pre-alembic 库**(有业务表、无版本表)→ ``upgrade head`` 走
  baseline 的 **legacy-adapt** 路径原地适配(列改名/补列/新表/快照搬
  家,数据全保留)。设计稿原文是「跳过直跑」,但 M2 改列名后新代码读
  不到旧列,跳过即起不来;原地适配保住全部数据且不违「alembic 必经」
  (偏离说明见 alembic/versions/0001_baseline.py)。

conftest 的新建临时库仍走 create_all(测试专用,不进本模块)。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

_BACKEND_ROOT = Path(__file__).resolve().parents[2]  # backend/


def _sync_url(url: str) -> str:
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    url = url.replace("sqlite+aiosqlite://", "sqlite://")
    return url


def _alembic_config(sync_url: str) -> Config:
    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    return cfg


def _sync_engine(url: str) -> Engine:
    return create_engine(_sync_url(url), future=True)


def _has_business_tables(engine: Engine) -> bool:
    names = set(inspect(engine).get_table_names())
    names.discard("alembic_version")
    return bool(names)


def ensure_schema_sync(async_url: str) -> None:
    engine = _sync_engine(async_url)
    is_pg = engine.dialect.name == "postgresql"
    try:
        has_version = inspect(engine).has_table("alembic_version")
        has_tables = _has_business_tables(engine)

        if not has_version and not has_tables:
            logger.info("schema: 空库 → alembic upgrade head 建库")
            command.upgrade(_alembic_config(engine.url.render_as_string(hide_password=False)), "head")
            return

        if has_version:
            with engine.connect() as conn:
                current = MigrationContext.configure(conn).get_current_revision()
            head = ScriptDirectory(
                str(_BACKEND_ROOT / "alembic")).get_current_head()
            if current == head:
                return
            if is_pg:
                raise RuntimeError(
                    f"pg_schema_behind: 库版本 {current} != head {head} —— "
                    "PG 启动只校验不迁移;请在带备份的窗口执行 "
                    "`alembic upgrade head`(runbook-pg.md §4)"
                )
            logger.info("schema: sqlite 落后({} < {})→ 自动 upgrade",
                        current, head)
            command.upgrade(_alembic_config(engine.url.render_as_string(hide_password=False)), "head")
            return

        # 存量 pre-alembic 库:legacy-adapt(baseline 内省适配)
        logger.warning(
            "schema: 检测到 pre-alembic 存量库 → baseline legacy-adapt "
            "原地适配(列改名/补列/新表;数据保留)"
        )
        command.upgrade(_alembic_config(engine.url.render_as_string(hide_password=False)), "head")
        logger.info("schema: legacy-adapt 完成,已打 alembic 版本戳")
    finally:
        engine.dispose()


async def ensure_schema(async_url: str) -> None:
    await asyncio.to_thread(ensure_schema_sync, async_url)
