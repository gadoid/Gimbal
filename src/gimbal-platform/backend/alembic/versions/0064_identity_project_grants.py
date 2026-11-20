"""promotion 身份授权表(决策 1 阶段 4;identity-registry §5)。

``identity_project_grants``:条目 × 项目授权行(共享即授权)。条目本体
不拷贝(alias_name 全局唯一 + 引用键稳定,拷贝是死路);本表 = 授权的
管理面事实 —— analyze 裁决面板身份分区 / 项目呈现「共享带来的条目」/
source_promotion_id 溯源。执行解析不查本表(拍板 2026-11-20:照默认
口径,身份按全局注册表解析)。

fresh 链守卫:空库走 baseline create_all(模型已含本表)+ stamp head,
表已存在时整体空转。downgrade 删表(纯新表,无存量数据语义)。
"""
import sqlalchemy as sa
from alembic import op

revision = "0064_identity_project_grants"
down_revision = "0063_carry_instance_key"
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if _has_table(op.get_bind(), "identity_project_grants"):
        return  # fresh 链:baseline create_all 已含本表
    op.create_table(
        "identity_project_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("identity_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("source_promotion_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["identity_id"], ["service_identities.id"],
            ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_promotion_id"], ["project_promotions.id"],
            ondelete="SET NULL"),
        sa.UniqueConstraint("identity_id", "project_id",
                            name="uq_identity_grant_identity_project"),
    )
    op.create_index("ix_identity_project_grants_identity_id",
                    "identity_project_grants", ["identity_id"])
    op.create_index("ix_identity_project_grants_project_id",
                    "identity_project_grants", ["project_id"])


def downgrade() -> None:
    op.drop_table("identity_project_grants")
