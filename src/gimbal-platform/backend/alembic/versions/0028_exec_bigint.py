"""0028:执行面主键/外键与序列改 BIGINT(整体评审 2026-10-15 #10)。

int4 上限约 21.47 亿。``execution_events.id`` 每条事件/日志行消耗一个号
(结构化日志入库后),保留期清扫只删数据不回收号 —— 高执行量下数月到
数年即用尽。执行面统一升 BIGINT:

* 主键:executions / execution_events / execution_rows / execution_jobs,
  及事件型表 adaptation_ops / adaptation_snapshots;
* 指向 executions.id 的外键:execution_events / execution_event_evidence /
  execution_rows / execution_jobs / execution_snapshots 的 execution_id。

**关键:** ``ALTER COLUMN ... TYPE bigint`` 不会改 serial 背后的序列
(PG16 实测:改列后 ``pg_sequences.data_type`` 仍为 integer、max_value
仍为 2147483647),必须同时 ``ALTER SEQUENCE ... AS bigint``。

守卫:逐列内省,已是 bigint 的列/序列跳过(幂等;fresh 链 baseline 已按
当前模型 create_all 建出 bigint 时整段空转)。外键列先于/后于被引用列
改型均可(PG 校验在语句结束时,同类整数族之间外键兼容)。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_exec_bigint"
down_revision = "0027_check_ts_tz"
branch_labels = None
depends_on = None

# (表, 列, 是否为 serial 主键 → 需同步改序列)
_TARGETS: tuple[tuple[str, str, bool], ...] = (
    ("executions", "id", True),
    ("execution_events", "id", True),
    ("execution_rows", "id", True),
    ("execution_jobs", "id", True),
    ("adaptation_ops", "id", True),
    ("adaptation_snapshots", "id", True),
    ("execution_events", "execution_id", False),
    ("execution_event_evidence", "execution_id", False),
    ("execution_rows", "execution_id", False),
    ("execution_jobs", "execution_id", False),
    ("execution_snapshots", "execution_id", False),
)


def _column_type(bind, table: str, column: str) -> str | None:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return None
    for c in insp.get_columns(table):
        if c["name"] == column:
            return str(c["type"]).upper()
    return None


def _owned_sequence(bind, table: str, column: str) -> str | None:
    return bind.execute(
        sa.text("SELECT pg_get_serial_sequence(:t, :c)"),
        {"t": table, "c": column},
    ).scalar()


def _sequence_type(bind, seq: str) -> str | None:
    return bind.execute(
        sa.text("SELECT format_type(seqtypid, NULL) FROM pg_sequence "
                "WHERE seqrelid = CAST(:s AS regclass)"),
        {"s": seq},
    ).scalar()


def _convert(target: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table, column, serial in _TARGETS:
        ctype = _column_type(bind, table, column)
        if ctype is None:
            continue
        want_big = target == "bigint"
        if want_big and ctype != "BIGINT":
            op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE bigint')
        elif not want_big and ctype == "BIGINT":
            op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE integer')
        if serial:
            seq = _owned_sequence(bind, table, column)
            if seq and _sequence_type(bind, seq) != target:
                op.execute(f"ALTER SEQUENCE {seq} AS {target}")


def upgrade() -> None:
    _convert("bigint")


def downgrade() -> None:
    # 仅在号段仍处于 int4 范围内时可逆(超出则 ALTER 报错拒绝,数据不丢)
    _convert("integer")
