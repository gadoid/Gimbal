"""baseline = 第一个 revision,携带 §2 全部新 schema(PG迁移方案 §0 原则 4)。

无 stamp 步骤:空库 ``alembic upgrade head`` 从零建库(切换的人工第一
步),此后任何 schema 变更没有 revision 不合入。

两条执行路径(按库状态内省分发):

* **fresh**(无业务表):``Base.metadata.create_all`` 建全部表 + PG 侧
  ``users.role`` 生成列(不进 models 的方向翻转形态,M2 期间代码零读
  零写,回滚物理安全)。
* **legacy-adapt**(已有业务表、无 alembic_version —— 本地开发库/切换
  前的 SQLite 库):**原地适配**而非跳过 —— M2 改了列名(owner →
  owner_name 等),设计稿的「跳过直跑」会让新代码读不到列;baseline
  在此路径里做列改名/补列/新表/快照数据搬家,数据全保留。设计偏离
  说明见本文件尾部注释。

revision 内容冻结于落笔时的模型;此后变更走新 revision。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

# 与 app.core.db.Base 同源 —— baseline 落笔时冻结其形态
from app.core.db import Base  # noqa: E402
from app import models  # noqa: E402,F401  注册全部模型

# composer 七个生成列的表达式与模型同源(_json_path 双方言渲染)
from app.models._json_path import json_path_json, json_path_text  # noqa: E402
from sqlalchemy import cast, Integer, literal  # noqa: E402


def _meta(*keys: str):
    return (literal("definition"), literal("meta"), *(literal(k) for k in keys))


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "composer_scenarios"):
        # ── fresh:空库从零建起(切换链的人工第一步)──────────────────
        Base.metadata.create_all(bind=bind)
        # users.role(M6-3 后):models 已是平列 + DEFAULT 'member'(
        # create_all 建好);M2 期间的「is_admin 生成列」过渡形态已随
        # is_admin 删列退役,不再需要 ALTER。
        op.execute("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)")
        _create_composer_gin_indexes(pg_only=True)
        return

    # ── legacy-adapt:存量 pre-alembic 库(仅 SQLite;PG 在切换时为空库)
    _upgrade_legacy_sqlite(bind)


def _create_composer_gin_indexes(*, pg_only: bool) -> None:
    bind = op.get_bind()
    if pg_only and bind.dialect.name != "postgresql":
        return
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_composer_tags_gin "
            "ON composer_scenarios USING gin (tags jsonb_path_ops)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_composer_system_gin "
            "ON composer_scenarios USING gin (system jsonb_path_ops)"
        )
    else:
        # SQLite:普通 btree(本地量小,无害)
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_composer_tags_gin "
            "ON composer_scenarios (tags)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_composer_system_gin "
            "ON composer_scenarios (system)"
        )


def _upgrade_legacy_sqlite(bind) -> None:
    # 1) 新表先建(execution_snapshots 建好后才有快照搬家的目的地)
    Base.metadata.create_all(bind=bind, checkfirst=True)

    # 2) 快照数据搬家:executions.scenario_snapshot → execution_snapshots
    if _has_column(bind, "executions", "scenario_snapshot"):
        bind.execute(text(
            "INSERT OR IGNORE INTO execution_snapshots (execution_id, snapshot) "
            "SELECT id, scenario_snapshot FROM executions "
            "WHERE scenario_snapshot IS NOT NULL"
        ))
        with op.batch_alter_table("executions") as batch:
            batch.drop_column("scenario_snapshot")

    # 3) executions:台账快照列
    with op.batch_alter_table("executions") as batch:
        if not _has_column(bind, "executions", "scenario_name"):
            batch.add_column(
                sa.Column("scenario_name", sa.String(255), nullable=False,
                          server_default=""))
        if not _has_column(bind, "executions", "owner_name"):
            batch.add_column(
                sa.Column("owner_name", sa.String(128), nullable=False,
                          server_default=""))

    # 4) composer_scenarios:owner → owner_name + 七个生成列
    with op.batch_alter_table("composer_scenarios") as batch:
        if _has_column(bind, "composer_scenarios", "owner"):
            batch.alter_column("owner", new_column_name="owner_name")
        if not _has_column(bind, "composer_scenarios", "name"):
            batch.add_column(sa.Column(
                "name", sa.String(64),
                sa.Computed(json_path_text(
                    sa.text("payload"), *_meta("name")), persisted=True)))
        if not _has_column(bind, "composer_scenarios", "description"):
            batch.add_column(sa.Column(
                "description", sa.Text(),
                sa.Computed(json_path_text(
                    sa.text("payload"), *_meta("description")), persisted=True)))
        if not _has_column(bind, "composer_scenarios", "module"):
            batch.add_column(sa.Column(
                "module", sa.String(64),
                sa.Computed(json_path_text(
                    sa.text("payload"), *_meta("module")), persisted=True)))
        if not _has_column(bind, "composer_scenarios", "author"):
            batch.add_column(sa.Column(
                "author", sa.String(128),
                sa.Computed(json_path_text(
                    sa.text("payload"), *_meta("author")), persisted=True)))
        if not _has_column(bind, "composer_scenarios", "priority"):
            batch.add_column(sa.Column(
                "priority", sa.SmallInteger(),
                sa.Computed(cast(json_path_text(
                    sa.text("payload"), *_meta("priority")), Integer),
                    persisted=True)))
        if not _has_column(bind, "composer_scenarios", "system"):
            batch.add_column(sa.Column(
                "system", sa.JSON(),
                sa.Computed(json_path_json(
                    sa.text("payload"), *_meta("system")), persisted=True)))
        if not _has_column(bind, "composer_scenarios", "tags"):
            batch.add_column(sa.Column(
                "tags", sa.JSON(),
                sa.Computed(json_path_json(
                    sa.text("payload"), *_meta("tags")), persisted=True)))

    # 5) carry 两表:三件套列
    for tbl in ("carry_service_bindings", "carry_global_defaults"):
        with op.batch_alter_table(tbl) as batch:
            if not _has_column(bind, tbl, "updated_by_name"):
                if _has_column(bind, tbl, "updated_by"):
                    batch.alter_column("updated_by",
                                       new_column_name="updated_by_name")
                else:
                    batch.add_column(sa.Column(
                        "updated_by_name", sa.String(128), nullable=False,
                        server_default=""))
            if not _has_column(bind, tbl, "updated_by_id"):
                batch.add_column(sa.Column(
                    "updated_by_id", sa.Integer(), nullable=True))

    # 6) adaptation_batches / board_cards:姓名快照列
    if not _has_column(bind, "adaptation_batches", "operator_name"):
        with op.batch_alter_table("adaptation_batches") as batch:
            batch.add_column(sa.Column(
                "operator_name", sa.String(128), nullable=False,
                server_default=""))
    if not _has_column(bind, "board_cards", "author_name"):
        with op.batch_alter_table("board_cards") as batch:
            batch.add_column(sa.Column(
                "author_name", sa.String(128), nullable=False,
                server_default=""))

    # 7) users:display_name partial unique(双方言)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_display_name "
        "ON users (display_name) WHERE display_name <> ''"
    )
    # 8) composer 列表锚索引(既有表上 create_all 不会补索引)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_composer_vis_updated "
        "ON composer_scenarios (visibility, updated_at)"
    )
    _create_composer_gin_indexes(pg_only=False)


def downgrade() -> None:
    """baseline 无 downgrade:它是链的起点,退回它之前 = 重建库。"""
    raise NotImplementedError("baseline_revision_cannot_downgrade")
