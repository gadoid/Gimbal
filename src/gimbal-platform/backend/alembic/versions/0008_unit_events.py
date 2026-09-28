"""2026-09-28 P2-01/P2-02:单元级台账 + 统一事件表。

P2-01(C8):``execution_rows`` 行级 → 单元级 —— 加 ``unit_id``(别名+展开
序号,与执行器一致)、``branch``(分支维度)、``attempts``(乘法执行次数);
dataset/injection/row_index 保留为单元属性。存量行不回填语义(unit_id
留空串 = 行级时代写入,读侧兼容),新写入由事件投影(P2-04)设置。

P2-02(C2):新表 ``execution_events`` —— 执行器事件与日志的统一落库面:

* 字段:execution_id / seq / ts / kind(event|log) / level / category /
  module / service / protocol / unit / attempt / step / event_type /
  message / payload(原始内容 JSONB);
* 索引:(execution_id, seq) 唯一(与执行器 jsonl 行对账);标签列
  (execution_id, category, unit) 复合 + event_type + ts(保留期清扫);
* ``call.exchange`` 证据体拆 ``execution_event_evidence``(主表只留
  摘要 message,证据体整存 JSONB);
* 保留期限:配置 ``EXEC_EVENTS_RETENTION_DAYS``(默认 14,0=永久),
  清扫函数见 execution_store.purge_expired_events。

fresh 链守卫:baseline 对空库 ``Base.metadata.create_all`` 已含全部新列/
新表 → 内省后空转;部署硬顺序:先 upgrade 再起新代码。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_unit_events"
down_revision = "0007_execution_skipped"
branch_labels = None
depends_on = None


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    # ── P2-01:execution_rows 单元化 ──────────────────────────
    row_cols = _cols("execution_rows")
    if "unit_id" not in row_cols:
        op.execute(
            "ALTER TABLE execution_rows ADD COLUMN unit_id "
            "VARCHAR(255) NOT NULL DEFAULT ''")
    if "branch" not in row_cols:
        op.execute(
            "ALTER TABLE execution_rows ADD COLUMN branch "
            "VARCHAR(16) NOT NULL DEFAULT 'main'")
    if "attempts" not in row_cols:
        op.execute(
            "ALTER TABLE execution_rows ADD COLUMN attempts "
            "INTEGER NOT NULL DEFAULT 1")

    # ── P2-02:统一事件表 + 证据表 ───────────────────────────
    if "execution_events" not in _tables():
        op.create_table(
            "execution_events",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("execution_id", sa.Integer,
                      sa.ForeignKey("executions.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("seq", sa.Integer, nullable=False),
            sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("kind", sa.String(8), nullable=False),
            sa.Column("level", sa.String(16), nullable=True),
            sa.Column("category", sa.String(24), nullable=True),
            sa.Column("module", sa.String(128), nullable=True),
            sa.Column("service", sa.String(128), nullable=True),
            sa.Column("protocol", sa.String(64), nullable=True),
            sa.Column("unit", sa.String(255), nullable=True),
            sa.Column("attempt", sa.String(16), nullable=True),
            sa.Column("step", sa.String(64), nullable=True),
            sa.Column("event_type", sa.String(64), nullable=True),
            sa.Column("message", sa.Text, nullable=True),
            sa.Column("payload", sa.JSON, nullable=False),
        )
        op.create_index("uq_execution_event_seq", "execution_events",
                        ["execution_id", "seq"], unique=True)
        op.create_index("ix_execution_events_labels", "execution_events",
                        ["execution_id", "category", "unit"])
        op.create_index("ix_execution_events_type", "execution_events",
                        ["execution_id", "event_type"])
        op.create_index("ix_execution_events_ts", "execution_events", ["ts"])

    if "execution_event_evidence" not in _tables():
        op.create_table(
            "execution_event_evidence",
            sa.Column("execution_id", sa.Integer,
                      sa.ForeignKey("executions.id", ondelete="CASCADE"),
                      primary_key=True),
            sa.Column("seq", sa.Integer, primary_key=True),
            sa.Column("evidence", sa.JSON, nullable=False),
        )


def downgrade() -> None:
    if "execution_event_evidence" in _tables():
        op.drop_table("execution_event_evidence")
    if "execution_events" in _tables():
        op.drop_index("ix_execution_events_ts", table_name="execution_events")
        op.drop_index("ix_execution_events_type", table_name="execution_events")
        op.drop_index("ix_execution_events_labels", table_name="execution_events")
        op.drop_index("uq_execution_event_seq", table_name="execution_events")
        op.drop_table("execution_events")
    row_cols = _cols("execution_rows")
    for col in ("attempts", "branch", "unit_id"):
        if col in row_cols:
            op.execute(f"ALTER TABLE execution_rows DROP COLUMN {col}")
