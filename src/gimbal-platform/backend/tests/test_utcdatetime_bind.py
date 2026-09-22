"""UtcDateTime 绑定矫正单测(asyncpg naive 本地时区陷阱)。

背景:asyncpg 对 timestamptz 的 naive 绑定按**客户端本地时区**编码 —
timeutil.utcnow()(naive UTC)在 UTC+8 主机上整体 -8h 落库(executions
finished_at 切 PG 后首单实测,2026-09-22)。UtcDateTime 在 PG 方言的
绑定路径把 naive 一律按 UTC 补 tzinfo;SQLite 维持 naive 往返不变。

SQLite 集成套件无法复现该陷阱(其 DATETIME 无时区语义),故此处直接
对 bind_processor 做方言级单测;线上探针负责端到端验证。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects import postgresql, sqlite

from app.models._types import UtcDateTime

UTC8 = timezone(timedelta(hours=8))  # 宿主机本地时区(陷阱触发条件)


def _pg_processor():
    return UtcDateTime().bind_processor(postgresql.dialect())


def _sqlite_processor():
    return UtcDateTime().bind_processor(sqlite.dialect())


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


def test_sqlite_keeps_naive_roundtrip():
    naive = datetime(2026, 9, 22, 2, 52, 41)
    proc = _sqlite_processor()
    if proc is None:  # 基类无处理器 = 原样透传,naive 保持 naive
        return
    out = proc(naive)
    assert out is naive or out.tzinfo is None


def test_sqlite_aware_not_broken():
    # SQLite 侧沿用基类处理器(现状行为),不因装饰器改变
    aware = datetime.now(timezone.utc)
    proc = _sqlite_processor()
    if proc is None:
        return
    out = proc(aware)
    assert out is not None
