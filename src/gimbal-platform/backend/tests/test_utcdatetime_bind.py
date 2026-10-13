"""UtcDateTime 绑定矫正单测(asyncpg naive 本地时区陷阱)。

背景:asyncpg 对 timestamptz 的 naive 绑定按**客户端本地时区**编码 —
timeutil.utcnow()(naive UTC)在 UTC+8 主机上整体 -8h 落库(executions
finished_at 切 PG 后首单实测,2026-09-22)。UtcDateTime 在 PG 方言的
绑定路径把 naive 一律按 UTC 补 tzinfo。此处直接对 bind_processor 做
方言级单测;线上探针负责端到端验证。(SQLite 方言 2026-10-14 退役,
其 naive 往返用例随之删除。)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects import postgresql

from app.models._types import UtcDateTime

UTC8 = timezone(timedelta(hours=8))  # 宿主机本地时区(陷阱触发条件)


def _pg_processor():
    return UtcDateTime().bind_processor(postgresql.dialect())


def test_pg_naive_gets_utc_tzinfo():
    naive = datetime(2026, 9, 22, 2, 52, 41)
    out = _pg_processor()(naive)
    # asyncpg 见到 aware(UTC)才按绝对时刻编码,不再吃本地时区
    assert out.tzinfo is not None
    assert out.utcoffset() == timezone.utc.utcoffset(None)
    assert (out.astimezone(timezone.utc) - naive.replace(tzinfo=timezone.utc)).total_seconds() == 0


def test_pg_aware_passthrough():
    aware = datetime.now(timezone.utc)
    out = _pg_processor()(aware)
    assert out is aware


def test_pg_none_passthrough():
    assert _pg_processor()(None) is None
