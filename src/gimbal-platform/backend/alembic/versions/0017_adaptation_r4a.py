"""0017: RS4a 适配中心批次模型调整（Release v4.4 §5.9）。

- adaptation_batches 加 kind（cross_line / correction / carry）、
  from_revisions（JSON 数组）、to_revision、save_mode 列
- 存量行回填：kind='carry'（原批次全部为 carry 类）
- catalog_versions 表删除（Release §8 切换窗口内删除）
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_adaptation_r4a"
down_revision = "0016_environments"


def upgrade() -> None:
    # ── adaptation_batches 新列 ──
    op.add_column("adaptation_batches",
                  sa.Column("kind", sa.String(16), nullable=False,
                            server_default="carry"))
    op.add_column("adaptation_batches",
                  sa.Column("from_revisions", sa.JSON(), nullable=True))
    op.add_column("adaptation_batches",
                  sa.Column("to_revision", sa.String(64), nullable=True))
    op.add_column("adaptation_batches",
                  sa.Column("save_mode", sa.String(16), nullable=True))

    # ── catalog_versions 删除（Release §8）──
    op.drop_table("catalog_versions")


def downgrade() -> None:
    # 恢复 catalog_versions（最小骨架——实际无法恢复数据）
    op.create_table(
        "catalog_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("endpoint_id", sa.String(255), nullable=False),
        sa.Column("version", sa.String(64)),
        sa.Column("spec_json", sa.JSON()),
    )
    op.drop_column("adaptation_batches", "save_mode")
    op.drop_column("adaptation_batches", "to_revision")
    op.drop_column("adaptation_batches", "from_revisions")
    op.drop_column("adaptation_batches", "kind")
