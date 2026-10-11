"""环境组表（Release v4.4 §11 V5 已定按 B / D-7）。

环境声明「每个系统部署的是哪条版本线」，支撑：
- 环境比对告警（执行时场景版本线 ≠ 环境版本线 → 告警）
- 保存推荐（有环境仍声明起点版本线 → 保存为副本）
- 版本线退役判定（没有任何环境声明 → 退役）
- 新建场景默认版本线（按所选环境）

必要性（对「不新增模块」原则的豁免依据，v4.2 补）：
四处功能依赖同一事实，分散成各别名上的字段必然不一致；
落地只是一张表加一个外键。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class Environment(Base):
    """环境组（一组服务别名 + 各系统部署的版本线声明）。"""

    __tablename__ = "environments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(256), default="")
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    # lines: {系统名: 版本线}（如 {"fin": "1.0", "platform": "1.0"}）
    lines: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow)
