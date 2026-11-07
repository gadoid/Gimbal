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
    """报告定义(私有/公共分立 visibility;owner = 维护者,恒非空)。

    authz W9-2:公共定义有维护者(owner_id 不再置 None —— 公共 ≠ 无主);
    编辑权 = 维护者,Admin+ 仅可下架(delete,steward)。遗留无主公共行
    (owner_id NULL)由 0037 回填 visibility='public',保持全员可读、
    编辑面冻结(无人是维护者)。"""
    __tablename__ = "report_definitions"
    __table_args__ = (
        Index("ix_report_definitions_owner", "owner_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    # 定义 payload(ReportDefinition.model_dump;camelCase wire 形态)
    definition: Mapped[dict] = mapped_column(JsonVar, default=dict)
    # 维护者(新建恒非空;遗留无主公共行保持 NULL)
    owner_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True)
    # 公共态标记(W9-2 起;private | public)
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
