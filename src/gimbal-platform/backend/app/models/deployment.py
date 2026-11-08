"""部署表(authz M2a S2):(基础服务, 环境) → 地址。

地址链第 ③ 层的新数据源(D11:键 = plate 基础服务名,比「系统」细
一级)。解析顺序见 ``services/env_chain.py``:按环境查本表,未命中 /
无环境时回退别名 ``base_url``(影子期兜底,S6 删别名地址时退役)。

删环境 → 其部署行级联删除(部署行没有脱离环境的意义)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (
        UniqueConstraint("base_service", "env_id",
                         name="uq_deployments_service_env"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_service: Mapped[str] = mapped_column(String(128), nullable=False)
    env_id: Mapped[int] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow)
