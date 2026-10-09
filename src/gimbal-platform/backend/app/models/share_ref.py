"""share_refs — 引用分享(权限域二期 P2,《Suite成员层、引用分享与
浏览镜头-设计方案》§7.2)。

只存当前生效的引用:撤销/退订 = 删行;不存 owner_id —— 分享者由资源
当前属主推导,处置转让时引用天然随行(§7.10)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint,
)
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime


class ShareRef(Base):
    __tablename__ = "share_refs"
    __table_args__ = (
        CheckConstraint(
            "(scenario_id IS NULL) <> (suite_id IS NULL)",
            name="ck_share_refs_exactly_one"),
        UniqueConstraint("grantee_user_id", "scenario_id",
                         name="uq_share_refs_user_scenario"),
        UniqueConstraint("grantee_user_id", "suite_id",
                         name="uq_share_refs_user_suite"),
        Index("ix_share_refs_grantee", "grantee_user_id"),
        Index("ix_share_refs_scenario", "scenario_id"),
        Index("ix_share_refs_suite", "suite_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    grantee_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scenario_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("composer_scenarios.scenario_id", ondelete="CASCADE"),
        nullable=True)
    suite_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("suites.id", ondelete="CASCADE"), nullable=True)
    granted_by_name: Mapped[str] = mapped_column(String(128), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, server_default=func.now())
