"""适配批次注册表(spec §3.4)。status: open|applying|completed|rolled_back。"""
from __future__ import annotations

from datetime import datetime

from ._types import UtcDateTime
from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class AdaptationBatch(Base):
    __tablename__ = "adaptation_batches"

    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(String(255), nullable=False)
    from_version: Mapped[str] = mapped_column(String(64), nullable=False)
    to_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    # SET NULL + 姓名快照(§2.2):全局资产上的操作者溯源,行不连坐
    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    operator_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
