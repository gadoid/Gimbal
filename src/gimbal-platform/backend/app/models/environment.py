"""环境组表（Release v4.4 §11 V5 已定按 B / D-7）。

环境声明「每个系统部署的是哪条版本线」，支撑：
- 环境比对告警（执行时场景版本线 ≠ 环境版本线 → 告警）
- 保存推荐（有环境仍声明起点版本线 → 保存为副本）
- 版本线退役判定（没有任何环境声明 → 退役）
- 新建场景默认版本线（按所选环境）

必要性（对「不新增模块」原则的豁免依据，v4.2 补）：
四处功能依赖同一事实，分散成各别名上的字段必然不一致；
落地只是一张表加一个外键。

authz M2a S2:环境是地址链的选择维度 —— 部署表 ``deployments`` 按
(基础服务, 环境) 给出地址;``is_default`` = Admin 指定的默认环境
(D2:环境链末位兜底,至多一行,部分唯一索引钉死)。``visibility``
列随 0044 删除(零逻辑消费,环境是团队共享配置)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text

from ._types import JsonVar, UtcDateTime
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class Environment(Base):
    """环境组（一组服务别名 + 各系统部署的版本线声明）。"""

    __tablename__ = "environments"
    __table_args__ = (
        # 默认环境至多一行(D2;置默认由路由原子切换)
        Index("uq_environments_default", "is_default", unique=True,
              postgresql_where=text("is_default")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(256), default="")
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True)
    # lines: {系统名: 版本线}（如 {"fin": "1.0", "platform": "1.0"}）
    lines: Mapped[dict] = mapped_column(JsonVar, default=dict)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow)
