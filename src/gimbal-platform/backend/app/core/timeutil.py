"""Naive-UTC clock helper shared by dispatcher + routers.

M2(timestamptz 结构修法)后双方言并存:SQLite 的时间戳仍按 naive-UTC
往返(方言不存 offset),PG(asyncpg)读回 aware。写入侧统一仍走
:func:`utcnow`(naive UTC,两方言都按 UTC 解释);**比较/规范化边界**
一律先过 :func:`ensure_aware`,naive 一律视为 UTC —— 混比 TypeError
从「静默漏报」变「不可能」。
"""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """UTC clock reading without tzinfo (SQLAlchemy naive-UTC columns)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_aware(dt: datetime | None) -> datetime | None:
    """naive → 视为 UTC 补 tzinfo;aware 原样返回(比较边界专用)。"""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def iso_naive_utc(dt: datetime | None) -> str | None:
    """DB 时间戳的 API 序列化口径:naive-UTC 字符串(不带 offset)。

    SQLite 读回 naive、PG 读回 aware(+00:00)—— 同一列两方言的
    isoformat 形状不同会打进前端契约。一律先归一到 UTC 再剥 tz,
    与既有 naive-UTC 字符串口径(时间线/看板卡)保持一致。
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat()
