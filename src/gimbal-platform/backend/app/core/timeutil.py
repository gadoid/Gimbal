"""Naive-UTC clock helper shared by dispatcher + routers.

M2(timestamptz 结构修法)后:PG(asyncpg)读回 aware;写入侧统一仍走
:func:`utcnow`(naive UTC,按 UTC 解释,经 UtcDateTime 绑定矫正);
**比较/规范化边界**
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

    统一归一到 UTC 再剥 tz(读回恒 aware;历史双方言形状差异的
    口径延续),
    与既有 naive-UTC 字符串口径(时间线/看板卡)保持一致。
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat()


def iso_utc_z(dt: datetime | None) -> str | None:
    """回调契约的时间格式:UTC、带 Z 后缀(``...T14:06:27.735108Z``)。

    M3(修复方案 2026-11-01 §4):此前用 ``dt.isoformat() + "Z"``,而
    PG 读回的是 aware(``+00:00``),拼出 ``...216788+00:00Z`` —— 双
    后缀,按 ISO 8601 解析失败。先经 :func:`iso_naive_utc` 归一去
    offset 再补 Z(复用同一归一口径,不另立格式规则)。
    """
    s = iso_naive_utc(dt)
    return None if s is None else s + "Z"
