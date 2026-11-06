"""步骤结果落库 + server 链槽位(日志报告整理 B3/B6,2026-11-06)

* ``execution_steps``:每个 ``step.end`` 一行。报告从本表渲染;保留期随
  执行行(执行删除 CASCADE,无独立清扫)。唯一键含 ``row_seq`` 与
  ``attempt``——逐行链按行号归属、重试的每次尝试各占一行。
* ``execution_rows.server_slot``:server 链执行该行的槽位号,定位
  ``server-engine[-N].log``(R11 轻量版)。

Revision ID: 0035_execution_steps
Revises: 0034_access_token_fks
Create Date: 2026-11-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0035_execution_steps"
down_revision = "0034_access_token_fks"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_column(bind, table: str, column: str) -> bool:
    return any(c["name"] == column for c in sa.inspect(bind).get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    # fresh 链守卫(同 0031/0032 口径):baseline create_all 已含时空转
    if not _has_column(bind, "execution_rows", "server_slot"):
        op.add_column("execution_rows",
                      sa.Column("server_slot", sa.Integer(), nullable=True))
    if _has_table(bind, "execution_steps"):
        return
    op.create_table(
        "execution_steps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("execution_id", sa.BigInteger(), nullable=False),
        sa.Column("row_seq", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("unit", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("attempt", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("step_id", sa.String(length=64), nullable=False),
        sa.Column("event_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("step_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("call_summary", sa.String(length=1024), nullable=False,
                  server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("assertion_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assertion_passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assertions", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("extracts", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("failure_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"],
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_execution_step_key", "execution_steps",
                    ["execution_id", "row_seq", "unit", "attempt", "step_id"],
                    unique=True)


def downgrade() -> None:
    op.drop_index("uq_execution_step_key", table_name="execution_steps")
    op.drop_table("execution_steps")
    op.drop_column("execution_rows", "server_slot")
