"""列类型变体(PG迁移方案 §2.1 原则 5:JSON 一律 JSONB)。

``JsonVar`` 在 PG 上渲染 JSONB(可索引/GIN、去空白),其余方言(SQLite)
保持普通 JSON。所有模型的 JSON 列统一走它,避免逐列 import 方言类型。

``UtcDateTime`` 是 DateTime(timezone=True) 的 naive 绑定矫正
(asyncpg 时区陷阱):DDL 两者完全一致,仅绑定行为不同。
"""
from __future__ import annotations

from datetime import timezone

from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

JsonVar = JSON().with_variant(JSONB(), "postgresql")


class UtcDateTime(TypeDecorator):
    """timestamptz 列 + naive-UTC 绑定矫正(asyncpg 按客户端本地时区编码)。

    asyncpg 对 timestamptz 的 **naive** 绑定按客户端本地时区编码:
    ``timeutil.utcnow()``(naive UTC)在 UTC+8 主机上整体 -8h 落库
    (executions.finished_at 切 PG 后首单实测)。ORM 属性赋值与
    WHERE 比较的绑定都走列类型 —— 绑定侧把 naive 一律按 UTC 补
    tzinfo,与 timeutil「naive 视为 UTC」的既有口径对齐;aware 原样
    通过;SQLite 维持 naive 往返不变(其 DATETIME 无时区语义)。

    DDL 与 ``DateTime(timezone=True)`` 逐字相同,无需任何迁移。
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def bind_processor(self, dialect):
        base = super().bind_processor(dialect)
        if dialect.name != "postgresql":
            return base

        def process(value):
            if value is not None and value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return base(value) if base is not None else value

        return process


__all__ = ["JsonVar", "UtcDateTime"]
