"""authz 收尾:删 integration_tasks.identity_mode 列。

0038 已把全部行收敛为 personal 并加 CHECK 约束(``ck_integration_
identity_personal``),代码侧不再读写该列 —— 按 C1 约定「下一次迁移
删列」。先删约束再删列(约束依附列,PG 删列会连带删,显式写出更清楚)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0039_drop_identity_mode"
down_revision = "0038_platform_retire"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "ALTER TABLE integration_tasks "
        "DROP CONSTRAINT IF EXISTS ck_integration_identity_personal"))
    bind.execute(sa.text(
        "ALTER TABLE integration_tasks DROP COLUMN IF EXISTS identity_mode"))


def downgrade() -> None:
    # 还原为 0038 终态:列回填 personal + 约束
    op.add_column("integration_tasks", sa.Column(
        "identity_mode", sa.String(16), nullable=False,
        server_default="personal"))
    bind = op.get_bind()
    bind.execute(sa.text(
        "ALTER TABLE integration_tasks "
        "ADD CONSTRAINT ck_integration_identity_personal "
        "CHECK (identity_mode = 'personal')"))
