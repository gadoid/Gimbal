"""账户组合表(账户组合设计方案 §4.1,定稿 05)。

``account_combos``:服务 → 已登记身份条目的映射集(引用语义,零明文
零地址零池),(scope, scope_id) 同 exec_configs 口径 —— scope 管「谁能
治理这份映射」,credentialSource 管执行时从哪个池取账户,两维正交。
``revision`` 仅条目变化 +1(元数据只动 updated_at + 审计);执行快照
与订阅指纹记录 id+name+revision 溯源。

fresh 链守卫:空库走 baseline create_all(模型已含本表)+ stamp head,
表已存在时整体空转。downgrade 删表(纯新表,无存量数据语义)。

迁移纪律(§4.1):部署前置 pg_dump(runbook §4,备份窗口)。
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0067_account_combos"
down_revision = "0066_incremental_model_align"
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if _has_table(op.get_bind(), "account_combos"):
        return  # fresh 链:baseline create_all 已含本表
    op.create_table(
        "account_combos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        # {"entries": [{"service": ..., "alias": ...}]} —— jsonb(模型口径
        # JsonVar,0053 的 sa.JSON 漂移不重蹈,0066 已收敛同款)
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("scope", "scope_id", "name",
                            name="uq_account_combos_scope_name"),
    )
    op.create_index("ix_account_combos_scope_id",
                    "account_combos", ["scope_id"])
    # 默认组合每 (scope, scope_id) 至多一行(partial unique,模型同款)
    op.create_index(
        "uq_account_combos_default", "account_combos",
        ["scope", "scope_id"], unique=True,
        postgresql_where=sa.text("is_default"))


def downgrade() -> None:
    op.drop_table("account_combos")
