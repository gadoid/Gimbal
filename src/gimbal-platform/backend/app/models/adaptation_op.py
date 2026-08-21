"""适配 op 逐条状态(spec §3.4 / P3+P4 裁定,2026-08-21)。

ops 草案"逐条确认应用"要求每条 op 的状态跨会话持久化,batches 表无此
结构。数据集类 op 亦填所属 scenario_id(回滚寻址);payload 存 op 参数
(step/from/to/map…),op 类型本体在 op_type 列。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class AdaptationOp(Base):
    __tablename__ = "adaptation_ops"
    __table_args__ = (Index("ix_aop_batch", "batch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    op_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
