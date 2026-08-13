"""SQLAlchemy model for the V3 Scenario Composer DataSet row.

A DataSet is a tabular payload of ``rows[]`` attached to a Case.  Used
to fan out the same Scenario into N parameterised runs.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ComposerDataSet(Base):
    """A DataSet row (V3 composer).  ``rows`` holds the parameter matrix."""

    __tablename__ = "composer_data_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True
    )  # matches DataSet.datasetId
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("composer_cases.case_id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    rows: Mapped[list] = mapped_column(JSON, default=list)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_status: Mapped[str] = mapped_column(String(16), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
