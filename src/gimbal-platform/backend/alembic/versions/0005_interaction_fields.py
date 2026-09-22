"""交互字段与口径统一(方案 2026-09-22-join-projection-and-caliber-unification)。

三件事一车:
* **row_count 生成列化(G3/C5)**:composer_data_sets.row_count 由应用
  双写改为 STORED 生成列(rows 数组长度),写侧三点已停写;PG 表达式带
  jsonb_typeof 守卫防脏数据炸写入。SQLite 的 ALTER 不能补 STORED 生成列,
  走 DROP+ADD(VIRTUAL,读时计算,语义等价;新建表仍是 STORED)。
* **冗余索引清理(方案 §6 另案合车)**:六个单列索引是既有复合/唯一
  索引的前缀(或无读消费),纯写放大;executions 的 owner 单列索引原地
  升级为 (owner_id, id) 复合。
* **G5 轻档视图(PG-only)**:v_scenarios_readable —— 可见性策略首次
  落进 DB 目录(security_invoker;直连消费前 SET app.uid/app.role;
  应用侧不消费,仍走 ORM + 应用谓词)。

ETL 适配:生成列 INSERT 排除是通用逻辑,row_count 自动进排除集;
migrate_sqlite_to_pg.py 的 generated_columns_sampled 已随加 row_count。
"""
from __future__ import annotations

from alembic import op

revision = "0005_interaction_fields"
down_revision = "0004_drop_is_admin"
branch_labels = None
depends_on = None

# 冗余前缀索引:被哪个复合/唯一索引覆盖
_REDUNDANT_INDEXES = (
    ("execution_rows", "ix_execution_rows_execution_id"),        # uq_execution_row_seq(execution_id, seq)
    ("notifications", "ix_notifications_user_id"),               # ix_notifications_user(user_id, id)
    ("composer_scenarios", "ix_composer_scenarios_visibility"),  # ix_composer_vis_updated(visibility, updated_at)
    ("composer_scenarios", "ix_composer_scenarios_owner_name"),  # 展示快照列,无读消费
    ("carry_service_bindings", "ix_carry_service_bindings_service_name"),  # uq_carry_svc_path(service_name, field_path)
    ("composer_run_schemes", "ix_composer_run_schemes_scenario_id"),       # uq_run_scheme_scenario_name(scenario_id, name)
)

_PG_ROWCOUNT_EXPR = (
    "(CASE WHEN jsonb_typeof(rows) = 'array' "
    "THEN jsonb_array_length(rows) ELSE 0 END)"
)
_SQLITE_ROWCOUNT_EXPR = "json_array_length(rows)"


def _drop_redundant() -> None:
    for table, idx in _REDUNDANT_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {idx}")


def _restore_redundant() -> None:
    # 与 0001/0002 基线的单列索引面一致(downgrade 回到旧形状)
    op.execute("CREATE INDEX IF NOT EXISTS ix_execution_rows_execution_id"
               " ON execution_rows (execution_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_id"
               " ON notifications (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_composer_scenarios_visibility"
               " ON composer_scenarios (visibility)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_composer_scenarios_owner_name"
               " ON composer_scenarios (owner_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_carry_service_bindings_service_name"
               " ON carry_service_bindings (service_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_composer_run_schemes_scenario_id"
               " ON composer_run_schemes (scenario_id)")


def _rowcount_is_generated(bind) -> bool:
    """row_count 当前是否已是生成列。

    0001 基线是 models 驱动的 create_all —— 全新库直接按当前模型建出
    生成列,本 revision 的转换分支只该作用于存量库(0005 之前的普通列)。
    PG 看 information_schema.is_generated;SQLite 看 table_xinfo.hidden
    (0=普通,2=VIRTUAL,3=STORED)。
    """
    if bind.dialect.name == "postgresql":
        v = bind.exec_driver_sql(
            "SELECT is_generated FROM information_schema.columns "
            "WHERE table_name = 'composer_data_sets' "
            "AND column_name = 'row_count'"
        ).scalar()
        return v == "ALWAYS"
    row = bind.exec_driver_sql(
        "SELECT hidden FROM pragma_table_xinfo('composer_data_sets') "
        "WHERE name = 'row_count'"
    ).scalar()
    return bool(row)


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # ── 1) row_count 生成列化(存量库;全新库 0001 已按模型建成)───
    if not _rowcount_is_generated(bind):
        op.execute("ALTER TABLE composer_data_sets DROP COLUMN row_count")
        if is_pg:
            op.execute(
                "ALTER TABLE composer_data_sets ADD COLUMN row_count INTEGER "
                f"GENERATED ALWAYS AS {_PG_ROWCOUNT_EXPR} STORED"
            )
        else:
            # SQLite:ALTER 只能补 VIRTUAL 生成列(STORED 需重建表);
            # 读时计算,语义与 STORED 等价。
            op.execute(
                "ALTER TABLE composer_data_sets ADD COLUMN row_count INTEGER "
                f"GENERATED ALWAYS AS ({_SQLITE_ROWCOUNT_EXPR})"
            )

    # ── 2) 冗余索引清理 + owner 复合升级 ──────────────────────────
    _drop_redundant()
    op.execute("DROP INDEX IF EXISTS ix_executions_owner_id")
    op.execute("CREATE INDEX ix_executions_owner_id"
               " ON executions (owner_id, id)")

    # ── 3) G5 轻档视图(PG-only)─────────────────────────────────
    if is_pg:
        op.execute(
            "CREATE OR REPLACE VIEW v_scenarios_readable WITH "
            "(security_invoker = true) AS "
            "SELECT * FROM composer_scenarios "
            "WHERE visibility = 'public' "
            "   OR owner_id = NULLIF(current_setting('app.uid', true), '')::int "
            "   OR current_setting('app.role', true) = 'admin'"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        op.execute("DROP VIEW IF EXISTS v_scenarios_readable")

    # owner 复合索引退回单列
    op.execute("DROP INDEX IF EXISTS ix_executions_owner_id")
    op.execute("CREATE INDEX ix_executions_owner_id"
               " ON executions (owner_id)")
    _restore_redundant()

    # row_count 退回普通列,回填 len(rows)。SQLite 不允许 DROP 生成列,
    # 走 batch 重建(batch 反射现表形状 → 去掉生成列 → 补普通列)。
    if is_pg:
        op.execute("ALTER TABLE composer_data_sets DROP COLUMN row_count")
        op.execute(
            "ALTER TABLE composer_data_sets ADD COLUMN row_count INTEGER "
            "NOT NULL DEFAULT 0"
        )
        op.execute(
            "UPDATE composer_data_sets SET row_count = "
            "CASE WHEN jsonb_typeof(rows) = 'array' "
            "THEN jsonb_array_length(rows) ELSE 0 END"
        )
    else:
        import sqlalchemy as sa

        with op.batch_alter_table("composer_data_sets",
                                  recreate="always") as batch:
            batch.drop_column("row_count")
            batch.add_column(
                sa.Column("row_count", sa.Integer(), nullable=False,
                          server_default=sa.text("0"))
            )
        op.execute(
            "UPDATE composer_data_sets "
            "SET row_count = json_array_length(rows)"
        )
