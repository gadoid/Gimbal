"""plate 目录版本戳(派生层,spec §3.3)。synced_at 只在适配批次完成时推进。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class CatalogVersion(Base):
    __tablename__ = "catalog_versions"

    endpoint_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
