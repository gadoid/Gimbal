"""2026-09-28 S5(P0):executions 补 skipped 计数列。

run.finished 终态事件携带 skipped(引擎 blocked/skip 口径),此前只留在
per-case result.json 工件,台账列缺失。本迁移给 executions 加一列:

* ``skipped INTEGER NOT NULL DEFAULT 0`` — 存量行 0 = 无跳过口径,不回填;
* 加法、纯元数据(PG ADD COLUMN 毫秒级);单元级台账迁移(0008,P2-01)
  会再动这张表,届时 unit_id/branch/attempts 一并处理;
* fresh 链守卫:baseline 对空库走 ``Base.metadata.create_all``,当前模型
  已含该列 → 本 revision 内省后空转(与 0006 同款处理);
* 部署硬顺序:先 upgrade 再起新代码(反向 ORM SELECT 带新列 →
  UndefinedColumn → 执行记录接口 500)。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_execution_skipped"
down_revision = "0006_iteration_batch"
branch_labels = None
depends_on = None


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if "skipped" in _cols("executions"):
        return  # fresh 链:baseline 已从当前模型建出该列
    op.execute(
        "ALTER TABLE executions ADD COLUMN skipped INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    if "skipped" not in _cols("executions"):
        return
    op.execute("ALTER TABLE executions DROP COLUMN skipped")
