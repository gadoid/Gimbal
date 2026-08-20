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
    "composer_scenarios": {
        "owner_id": "INTEGER DEFAULT 0",
        "visibility": "TEXT DEFAULT 'private'",
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


async def _retire_scenario_mirror_columns() -> None:
    """镜像列退役迁移:composer_scenarios 的 V1 镜像投影列清理。

    V3 建表时照抄了 V1 的字段清单(name/module/priority/author/tags/
    system/version/expire/description/step_count),容器引入后这些列
    沦为 payload 的镜像。create/update 一直双写,镜像与 payload 同步;
    本迁移仅对 meta 缺键的行用列值兜底回填,然后 DROP 镜像列 —
    payload 成为唯一权威(源存果算)。

    新库(新 schema 建表,无镜像列)直接跳过;幂等可重入。
    """
    import json

    mirror_cols = [
        "name", "description", "module", "priority", "author",
        "tags", "system", "version", "expire", "step_count",
    ]
    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda c: list(
                c.execute(
                    text("PRAGMA table_info(composer_scenarios)")  # noqa: S608
                ).fetchall()
            )
        )
        col_names = {r[1] for r in cols}
        present = [c for c in mirror_cols if c in col_names]
        if not present:
            return  # fresh DB (new schema) — nothing to retire

        # Backfill: any meta key the payload lacks gets the column value.
        rows = await conn.execute(
            text("SELECT * FROM composer_scenarios")  # noqa: S608
        )
        for row in rows.mappings():
            payload_raw = row["payload"]
            try:
                payload = json.loads(payload_raw) if isinstance(
                    payload_raw, str
                ) else dict(payload_raw or {})
            except Exception:  # noqa: BLE001 — malformed row: leave as-is
                continue
            definition = payload.get("definition")
            if not isinstance(definition, dict):
                continue
            meta = definition.get("meta")
            if not isinstance(meta, dict):
                meta = {}
            filled = False
            for col in present:
                key = "stepCount" if col == "step_count" else col
                v = row.get(col)
                if v in (None, ""):
                    continue
                if meta.get(key) in (None, ""):
                    meta[key] = bool(v) if col == "expire" else v
                    filled = True
            if filled:
                definition["meta"] = meta
                await conn.execute(
                    text(
                        "UPDATE composer_scenarios SET payload = :p"  # noqa: S608
                        " WHERE scenario_id = :sid"
                    ),
                    {
                        "p": json.dumps(payload, ensure_ascii=False),
                        "sid": row["scenario_id"],
                    },
                )
        for col in present:
            await conn.execute(
                text(
                    f"ALTER TABLE composer_scenarios "  # noqa: S608
                    f"DROP COLUMN {col}"
                )
            )
            logger.info(
                "migrate: dropped composer_scenarios.{} (mirror)", col
            )


async def _migrate_datasets_to_scenario() -> None:
    """Case 层解散迁移:composer_data_sets.case_id → scenario_id。

    一次性数据迁移(create_all 不会改已有表):

    1. 补 ``scenario_id`` 列(老库);
    2. 经 composer_cases.case_id→scenario_id 映射回填存量行;
    3. 删 composer_cases 表(级联孤儿随表消解)。

    新库(表按新 schema 创建)在第 2 步后无 case_id 列或无
    composer_cases 表,各步自然跳过;幂等可重入。
    """
    async with engine.begin() as conn:
        # Fresh DB flag: composer_cases was never created by this
        # deployment's create_all (the model no longer exists).
        tables = await conn.run_sync(
            lambda sync_conn: list(
                sync_conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).fetchall()
            )
        )
        table_names = {row[0] for row in tables}
        if "composer_cases" not in table_names:
            return  # 全新库(或已迁移过且表已删),无事可做

        ds_cols = await conn.run_sync(
            lambda sync_conn: list(
                sync_conn.execute(
                    text("PRAGMA table_info(composer_data_sets)")  # noqa: S608
                ).fetchall()
            )
        )
        ds_col_names = {row[1] for row in ds_cols}
        has_case_id = "case_id" in ds_col_names
        if "scenario_id" not in ds_col_names:
            await conn.execute(
                text(
                    "ALTER TABLE composer_data_sets ADD COLUMN scenario_id "
                    "VARCHAR(128)"
                )
            )
            logger.info("migrate: added composer_data_sets.scenario_id")

        if has_case_id:
            # Backfill via the legacy case → scenario mapping, then drop
            # the old column's rows' dependence by clearing case_id.
            n = await conn.execute(
                text(
                    "UPDATE composer_data_sets SET scenario_id = "
                    "(SELECT scenario_id FROM composer_cases "
                    " WHERE composer_cases.case_id = composer_data_sets.case_id) "
                    "WHERE scenario_id IS NULL OR scenario_id = ''"
                )
            )
            logger.info(
                "migrate: backfilled {} dataset row(s) with scenario_id", n.rowcount
            )
        # Drop the legacy table. SQLite has no DROP COLUMN constraint
        # dance here: FKs aren't enforced by default (PRAGMA
        # foreign_keys=OFF), and the new model never declared case_id.
        await conn.execute(text("DROP TABLE IF EXISTS composer_cases"))
        logger.info("migrate: dropped composer_cases (Case layer dissolved)")


async def _drop_dataset_last_run_columns() -> None:
    """composer_data_sets.last_run_* 假 UI 列删除。

    V1 有"用例上次运行状态"概念,V3 从未接上回写 — 列恒 NULL,
    前端徽章永远渲染不出。执行状态的真实源在 executions/exec_runs。
    """
    drop_cols = ["last_run_status", "last_run_at"]
    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda c: list(
                c.execute(
                    text("PRAGMA table_info(composer_data_sets)")  # noqa: S608
                ).fetchall()
            )
        )
        col_names = {r[1] for r in cols}
        for col in drop_cols:
            if col in col_names:
                await conn.execute(
                    text(
                        f"ALTER TABLE composer_data_sets "  # noqa: S608
                        f"DROP COLUMN {col}"
                    )
                )
                logger.info(
                    "migrate: dropped composer_data_sets.{} (never written)", col
                )


async def _rename_execution_case_id() -> None:
    """executions.case_id → scenario_id(V1→V3 语义收口)。

    列名是 V1 "执行用例" 的遗物;Case 层解散后执行挂载点是场景,
    列名与语义对齐。RENAME COLUMN 保数据;新库直接按新列名建表。
    """
    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda c: list(
                c.execute(
                    text("PRAGMA table_info(executions)")  # noqa: S608
                ).fetchall()
            )
        )
        col_names = {r[1] for r in cols}
        if "case_id" in col_names and "scenario_id" not in col_names:
            await conn.execute(
                text(
                    "ALTER TABLE executions RENAME COLUMN case_id "  # noqa: S608
                    "TO scenario_id"
                )
            )
            logger.info("migrate: executions.case_id renamed to scenario_id")


async def init_db() -> None:
    """Create tables; idempotent.  Also back-fills any new columns
    declared in ``_COLUMN_ADDITIONS`` so existing DBs don't need a wipe."""
    from .. import models  # noqa: F401  注册所有模型

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _auto_add_columns()
    await _retire_scenario_mirror_columns()
    await _migrate_datasets_to_scenario()
    await _drop_dataset_last_run_columns()
    await _rename_execution_case_id()
