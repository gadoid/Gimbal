"""drop external_endpoints(归一方案 v1.0 C1/b3-6)

外部接口登记目录退役:定义真源归 plate(kind=integration)。审计表
audit_logs 中历史行保留(action 文案映射前端已标「已退役」)。

Revision ID: 0029_drop_external_endpoints
Revises: 0028_exec_bigint
Create Date: 2026-10-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0029_drop_external_endpoints"
down_revision = "0028_exec_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_external_endpoints_alias_name"),
        table_name="external_endpoints",
        if_exists=True)
    op.drop_table("external_endpoints")


def downgrade() -> None:
    # 历史回滚路径:重建 X1 目录表(0021 形状;不含数据恢复)
    op.create_table(
        "external_endpoints",
        sa.Column("alias_name", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("auth", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("query_safe", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("request_schema", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["alias_name"], ["service_aliases.alias_name"],
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("alias_name", "name"),
    )
    op.create_index(
        op.f("ix_external_endpoints_alias_name"),
        "external_endpoints", ["alias_name"], unique=False)
