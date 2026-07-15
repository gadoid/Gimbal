"""HiddenFieldProfile model (Spec-2 §4.3 C2).

Per-(user, case) list of dot-paths the user wants hidden in the case
config view.  Lives separately from the case file so the L1/L2/L3
state is per-user (privacy + custom defaults).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class HiddenFieldProfile(Base):
    __tablename__ = "hidden_field_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "case_id", name="uq_hidden_user_case"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[str] = mapped_column(String(256), index=True)
    # List of dot-paths the user has hidden (L1 + L2 + their L3 toggles)
    hidden_paths: Mapped[list] = mapped_column(JSON, default=list)
    # User-chosen scope: 'global' applies across all cases; 'case' is per-case
    scope: Mapped[str] = mapped_column(String(16), default="case")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )