"""SQLAlchemy model for the scenario run-scheme row (workbench spec §4).

A RunScheme is the complete preparation for one execution (dataset rows +
injection entries + service bindings + run params).  Formerly embedded in
``composer_scenarios.payload.orchestration.runSchemes``; promoted to its
own table for PG-friendly relational modelling — relational dimensions
(scenario ownership, name uniqueness, default flag) as indexed columns,
the config document itself as one JSON payload.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, String, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime


class ComposerRunScheme(Base):
    __tablename__ = "composer_run_schemes"
    __table_args__ = (
        Index("uq_run_scheme_scenario_name", "scenario_id", "name", unique=True),
        # 每场景恰一个默认方案(SQLite/PG 双方言 partial unique index)
        Index(
            "uq_run_scheme_default",
            "scenario_id",
            unique=True,
            sqlite_where=text("is_default = 1"),
            postgresql_where=text("is_default IS TRUE"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scheme_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # NO ACTION DEFERRABLE(§2.1):scenario_store.delete 在 Python 管整组
    # 子表,FK 只做校验器。
    scenario_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("composer_scenarios.scenario_id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"),
    )
    name: Mapped[str] = mapped_column(String(64))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JsonVar, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now()
    )
