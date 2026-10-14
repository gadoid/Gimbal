"""集成线 v2 / I3.5:删除 integration_tasks.last_status 旧口径列。

I2 双出过渡(D11)收尾:前端(工作台卡片 + 集成中心)已全部切换
run_status / check_status 新字段并验收(vitest 四模板 × 四态 +
vue-tsc 零错),旧投影列与出参一并移除 —— 全库不再有 lastStatus
消费方。

单独成批(方案 §5):删除性迁移不与加列混批,出问题可单点回滚。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_drop_integration_last"
down_revision = "0024_integration_run_check"


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # fresh 链守卫:baseline(当前模型)已无本列 → 空转
    if _has_table("integration_tasks") \
            and _has_column("integration_tasks", "last_status"):
        op.drop_column("integration_tasks", "last_status")


def downgrade() -> None:
    if _has_table("integration_tasks") \
            and not _has_column("integration_tasks", "last_status"):
        op.add_column("integration_tasks", sa.Column(
            "last_status", sa.String(16), nullable=False,
            server_default=""))
