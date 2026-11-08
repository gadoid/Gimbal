"""authz M2a S7.2:提升流程 —— ``project_promotions`` 表(加入申请)。

场景 / 用例集加入普通项目时的冲突裁决单(有冲突 → pending 申请,
项目管理员批准即以批准那一刻的原件内容复制进项目;Q1 裁定)。
纯建表(fresh 链 create_all 已含同名表 → 内省守卫空转);无存量回填。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0048_project_promotions"
down_revision = "0047_alias_slimming"


def _has_table(bind, name: str) -> bool:
    """按 search_path 解析(不加 public. 前缀):fresh 链 0001 的
    create_all 按当前模型建表 —— 本表已存在时本迁移空转。"""
    return bool(bind.execute(sa.text(
        "SELECT to_regclass(:t) IS NOT NULL"), {"t": name}
    ).scalar())


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "project_promotions"):
        return
    op.create_table(
        "project_promotions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("applicant_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False,
                  server_default="pending"),
        sa.Column("conflicts", postgresql.JSONB(), nullable=True),
        sa.Column("resolution", postgresql.JSONB(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_project_promotions_project_id",
        "project_promotions", ["project_id"])
    op.create_index(
        "ix_project_promotions_applicant_id",
        "project_promotions", ["applicant_id"])
    op.create_index(
        "ix_project_promotions_status",
        "project_promotions", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "project_promotions"):
        return
    op.drop_index("ix_project_promotions_status",
                  table_name="project_promotions")
    op.drop_index("ix_project_promotions_applicant_id",
                  table_name="project_promotions")
    op.drop_index("ix_project_promotions_project_id",
                  table_name="project_promotions")
    op.drop_table("project_promotions")
