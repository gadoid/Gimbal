"""适配批次存档(spec §3.4/D3):受影响实体的 before 整像,回滚安全网。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar


class AdaptationSnapshot(Base):
    __tablename__ = "adaptation_snapshots"
    __table_args__ = (Index("ix_snap_batch", "batch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # scenario|dataset|carry_binding(按服务)|carry_default(全局默认)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    before_json: Mapped[dict] = mapped_column(JsonVar, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
