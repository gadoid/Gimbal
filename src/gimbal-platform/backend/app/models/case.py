from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class Case(Base):
    """用例元数据；实际定义在磁盘 YAML/JSON 文件中（file_path）。"""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    module: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    # 'public' — public dir, readable by all; 'private' — users dir under owner
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    tags: Mapped[str] = mapped_column(Text, default="")  # comma-joined for now
    file_path: Mapped[str] = mapped_column(String(512))  # absolute path
    audited: Mapped[bool] = mapped_column(default=False)  # admin-marked audited public case
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

