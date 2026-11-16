"""环境组表（Release v4.4 §11 V5 已定按 B / D-7;重构 2026-11-16 收窄）。

环境 = 平台级共享字典(部署面横切,重构决策 3):地址按 (服务, 环境)
在 deployments、登录口/版本线按 (系统, 环境) 在 system_env_instances。
版本线声明原 ``lines`` JSON 列已迁实例表(§1.2 收口),支撑的四个功能
(环境比对告警/保存推荐/退役判定/新建场景默认版本线)读面经
``env_chain.instance_lines`` 聚合,API 形状不变。

authz M2a S2:环境是地址链的选择维度;``is_default`` = Admin 指定的
默认环境(D2:环境链末位兜底,至多一行,部分唯一索引钉死)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text

from ._types import UtcDateTime
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class Environment(Base):
    """环境（平台级共享字典;实例事实见 system_env_instances）。"""

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
    # lines 列已迁 system_env_instances.line(重构 §1.2 版本线收口;
    # 读面经 env_chain.instance_lines 聚合,API 形状不变)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow)
