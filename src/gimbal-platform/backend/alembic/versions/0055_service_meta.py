"""服务级元数据表(service_meta)—— 服务注册页「说明」列的落库点。

读全员 / 写 Admin+(ops.write);service_name PK 对齐 plate 目录服务名
(不设外键:目录来自 plate 代理,平台侧只存说明文本)。

fresh 链守卫(同 0032 口径):baseline create_all 已含本表时空转。
downgrade 直接删表(本表纯平台侧说明,无下游依赖)。

Revision ID: 0055_service_meta
Revises: 0054_exec_config_migration
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0055_service_meta"
down_revision = "0054_exec_config_migration"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    # fresh 链守卫(同 0032 口径):baseline create_all 已含本表时空转
    if _has_table(op.get_bind(), "service_meta"):
        return
    op.create_table(
        "service_meta",
        sa.Column("service_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False,
                  server_default=""),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("service_name"),
    )


def downgrade() -> None:
    op.drop_table("service_meta")
