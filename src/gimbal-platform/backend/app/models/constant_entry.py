"""ConstantEntry model — per-user 常量池条目(常量池设计 2026-08-26)。

两类条目互斥:
* literal — ``value`` 存 str/int/float/bool 字面值(JSON 列);
* generator — ``spec`` 存引擎生成器声明(dict,必须含字符串 ``kind``)。

平台只存配置阶段内容、绝不求值;引擎 preprocess 是唯一求值点。
owner 隔离: 跨 owner 一律 404;同名约束在 DB(owner_id, name)。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ConstantEntry(Base):
    __tablename__ = "constant_entries"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_constant_owner_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(256), default="")
    # "literal" | "generator" —— 创建后不可变(PATCH 拒改)
    entry_kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[Any] = mapped_column(JSON, nullable=True, default=None)
    spec: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
