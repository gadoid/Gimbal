"""2026-09-29 C11(P3-01)：执行任务持久化队列 execution_jobs。

POST /api/runs 改为入队（Execution 行 + 本表一行）；worker 经
``FOR UPDATE SKIP LOCKED`` 认领，支持多 worker 与重启恢复——进程内
注册表（_in_flight/_cancel_requested/信号量）退役，取消走
``cancel_requested`` DB 位。

* 一执行一任务（execution_id 唯一）；
* 认领即 attempts+1；租约 = heartbeat_at 距今超限视为孤儿（回收策略：
  attempts 未超上限 → 回队重跑，超上限 → 失败收口）；
* payload 存 dispatch_run 校验后的完整配方（worker 不回查请求上下文）。

fresh 链守卫：baseline ``create_all`` 已含本表 → 内省后空转（同 0006/0008）。
部署硬顺序：先 upgrade 再起新代码。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_execution_queue"
down_revision = "0008_unit_events"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "execution_jobs" in _tables():
        return  # fresh 链：baseline 已从当前模型建出本表
    op.create_table(
        "execution_jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("execution_id", sa.Integer,
                  sa.ForeignKey("executions.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("kind", sa.String(16), nullable=False, server_default="cases"),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("claimed_by", sa.String(64), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cancel_requested", sa.Boolean, nullable=False,
                  server_default=sa.false()),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_execution_jobs_status_id", "execution_jobs",
                    ["status", "id"])


def downgrade() -> None:
    if "execution_jobs" not in _tables():
        return
    op.execute("DROP TABLE execution_jobs")
