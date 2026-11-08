"""authz M2a S1.9:删 visibility 列(场景/suite/报告定义/集成模板)。

读写已全切 project 谓词(S1.1-S1.8 各切片);API 的 visibility 入参
(列表镜头/模板公开切换)语义不变,由路由层翻译为项目谓词;响应的
visibility 字段由 zone.derive_visibility / project_id 近似派生。

fresh 链守卫:baseline 按当前模型建表(列已不存在)→ 空转。
downgrade:回加列(private 默认)—— 公共项目行回填 public,
普通项目/私有区回填 private(近似,不保证精确还原历史值)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0043_drop_visibility"
down_revision = "0042_suite_member_zone"
branch_labels = None
depends_on = None

_TABLES = ("composer_scenarios", "suites", "report_definitions",
           "integration_tasks")


def _has_column(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    # 0005 的轻档视图依赖 visibility 列 —— 先删(列删后无人消费;
    # 如需保留可在 0044 重建为项目谓词版)
    bind.execute(sa.text("DROP VIEW IF EXISTS v_scenarios_readable"))
    # 索引守卫删(PG:一旦语句失败事务即中止,不能用 try/except 兜)
    bind.execute(sa.text(
        "DROP INDEX IF EXISTS ix_composer_vis_updated"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_suites_vis"))
    for table in _TABLES:
        if _has_column(bind, table, "visibility"):
            op.drop_column(table, "visibility")


def downgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        if not _has_column(bind, table, "visibility"):
            op.add_column(table, sa.Column(
                "visibility", sa.String(16), nullable=False,
                server_default="private"))
    # 公共项目行回填 public
    for table in _TABLES:
        bind.execute(sa.text(f"""
            UPDATE {table} SET visibility = 'public'
            WHERE project_id = (SELECT id FROM projects
                                WHERE kind = 'public')
        """))
