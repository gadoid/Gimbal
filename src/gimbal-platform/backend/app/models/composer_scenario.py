"""SQLAlchemy model for the V3 Scenario Composer Scenario row.

A Scenario is the "structural definition layer" — 1:1 with a Case, which
in turn owns 1:N DataSets.  ``payload`` carries the full draft container
``{definition, orchestration, caseMeta}``; ``definition`` is the plate
Scenario structure (steps included) and lives in a JSON column because
the per-step shape is heterogeneous and we never query into individual
step fields from SQL.

The legacy ``Case`` model in ``app/models/case.py`` (Spec-1 file-backed
cases) is unrelated; the V3 scenario composer lives in its own table
namespace to keep concerns isolated.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ComposerScenario(Base):
    """A Scenario row (V3 composer).  ``payload`` carries the full draft."""

    __tablename__ = "composer_scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True
    )  # matches meta.scenarioId
    name: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    module: Mapped[str] = mapped_column(String(128), default="", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=1, index=True)
    author: Mapped[str] = mapped_column(String(128), default="")
    owner: Mapped[str] = mapped_column(String(128), default="", index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    system: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[str] = mapped_column(String(32), default="v0.1.0")
    expire: Mapped[bool] = mapped_column(default=False)
    # Full draft container: {definition, orchestration, caseMeta} — kept
    # so we can rebuild the response without losing anything the user typed.
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    # Step count is denormalized for fast list-side rendering.
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
