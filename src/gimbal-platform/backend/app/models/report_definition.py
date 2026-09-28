"""报告定义模型(P3-07/C7):定义按用户/团队存储复用。

schema 与执行器侧 ``gimbal.schema.report_definition.ReportDefinition``
同构(dict payload 存储);执行时可选择定义,报告作为执行工件存储。
"""
from __future__ import annotations

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime
from datetime import datetime
from sqlalchemy import func


class ReportDefinitionRow(Base):
    """报告定义(私有区 owner_id / 公共区 owner_id=NULL)。"""
    __tablename__ = "report_definitions"
    __table_args__ = (
        Index("ix_report_definitions_owner", "owner_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    # 定义 payload(ReportDefinition.model_dump;camelCase wire 形态)
    definition: Mapped[dict] = mapped_column(JsonVar, default=dict)
    # 私有 = owner_id 非 NULL;公共 = NULL(全团队可读,仅 admin 可改)
    owner_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
