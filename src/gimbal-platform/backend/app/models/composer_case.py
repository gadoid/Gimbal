"""SQLAlchemy model for the V3 Scenario Composer Case row.

1:1 with a ComposerScenario (each Case is bound to exactly one Scenario).
1:N with ComposerDataSet (each Case owns zero or more DataSets).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ComposerCase(Base):
    """A Case row (V3 composer).  ``payload`` carries the full Case DTO."""

    __tablename__ = "composer_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True
    )  # matches Case.caseId
    scenario_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("composer_scenarios.scenario_id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    env: Mapped[str] = mapped_column(String(64), default="")
    auth: Mapped[dict] = mapped_column(JSON, default=dict)
    retry: Mapped[dict] = mapped_column(JSON, default=dict)
    data_set_ids: Mapped[list] = mapped_column(JSON, default=list)
    last_run_status: Mapped[str] = mapped_column(String(16), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), default="", index=True)
    # Full Case DTO (so we can rebuild the response verbatim).
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
