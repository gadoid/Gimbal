"""RS4a：adaptation_batches 补 scope 列（Release v4.4 §5.9）。

scope = 批次作用的场景/Suite id 列表（JSON）。线上两表 0 行,无存量迁移面。
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_adaptation_scope"
down_revision = "0017_adaptation_r4a"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # fresh 链守卫(2026-10-13 A-1):baseline 已含本列 → 空转。
    if not _has_column("adaptation_batches", "scope"):
        op.add_column(
            "adaptation_batches",
            sa.Column("scope", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("adaptation_batches", "scope")
