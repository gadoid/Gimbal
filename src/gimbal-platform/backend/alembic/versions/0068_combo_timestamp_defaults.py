"""补齐账户组合时间戳默认值,收敛 0067 与模型的迁移漂移。"""
import sqlalchemy as sa
from alembic import op

revision = "0068_combo_timestamp_defaults"
down_revision = "0067_account_combos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("created_at", "updated_at"):
        op.alter_column(
            "account_combos", column,
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        )


def downgrade() -> None:
    for column in ("created_at", "updated_at"):
        op.alter_column(
            "account_combos", column,
            existing_type=sa.DateTime(timezone=True),
            server_default=None,
        )
