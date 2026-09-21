"""列类型变体(PG迁移方案 §2.1 原则 5:JSON 一律 JSONB)。

``JsonVar`` 在 PG 上渲染 JSONB(可索引/GIN、去空白),其余方言(SQLite)
保持普通 JSON。所有模型的 JSON 列统一走它,避免逐列 import 方言类型。
"""
from __future__ import annotations

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

JsonVar = JSON().with_variant(JSONB(), "postgresql")

__all__ = ["JsonVar"]
