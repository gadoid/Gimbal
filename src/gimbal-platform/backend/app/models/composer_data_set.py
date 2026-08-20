"""SQLAlchemy model for the V3 Scenario Composer DataSet row.

A DataSet is a tabular payload of ``rows[]`` attached to a Scenario.  Used
to fan out the same Scenario into N parameterised runs.  (Formerly hung
off a 1:1 Case row; the Case layer was dissolved — datasets parameterise
the scenario's ``config.vars`` directly.)
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
    scenario_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("composer_scenarios.scenario_id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    rows: Mapped[list] = mapped_column(JSON, default=list)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
