"""回调投递行(webhook 设计 v3 P2 §7.5)

``webhook_deliveries`` = outbox:与终态写入同事务落库;``id`` 即对外
deliveryId / ``X-Gimbal-Delivery`` 去重键。不建别名外键(台账不随
别名删除消失);execution / integration_tasks 外键 SET NULL(目标行
删除后投递台账保留)。

Revision ID: 0032_webhook_deliveries
Revises: 0031_inbound_identity
Create Date: 2026-11-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0032_webhook_deliveries"
down_revision = "0031_inbound_identity"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    # fresh 链守卫(同 0031 口径):baseline create_all 已含本表时空转
    if _has_table(op.get_bind(), "webhook_deliveries"):
        return
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("alias_name", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.BigInteger(), nullable=True),
        sa.Column("instance_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(length=768), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False,
                  server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["instance_id"], ["integration_tasks.id"],
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_delivery_due", "webhook_deliveries",
                    ["status", "next_retry_at"])


def downgrade() -> None:
    op.drop_index("ix_webhook_delivery_due", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
