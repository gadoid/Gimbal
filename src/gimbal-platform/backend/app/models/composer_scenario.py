"""SQLAlchemy model for the V3 Scenario Composer Scenario row.

A Scenario is the "structural definition layer" and owns 1:N DataSets.
``payload`` carries the full draft container
``{definition, orchestration}``; ``definition`` is the plate
Scenario structure (steps included) and lives in a JSON column because
the per-step shape is heterogeneous and we never query into individual
step fields from SQL.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ComposerScenario(Base):
    """A Scenario row (V3 composer).  ``payload`` carries the full draft."""

    __tablename__ = "composer_scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True
    )  # matches meta.scenarioId
    # Display-name snapshot of the owner (legacy owner_id==0 rows fall
    # back to matching it); ownership itself is owner_id below.
    owner: Mapped[str] = mapped_column(String(128), default="", index=True)
    # 稳定属主(int user.id)。``owner`` 字符串保留为展示快照;归属判断
    # 以 owner_id 为准,owner_id==0 的存量行走 owner 名字回退(P2 迁移
    # 脚本会批量回填)。visibility: private(默认,仅 owner/admin 可读)
    # | public(所有登录用户可读)——取代 V1 的目录即真相模型。
    owner_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    visibility: Mapped[str] = mapped_column(
        String(16), default="private", index=True
    )
    # Full draft container: {definition, orchestration} — the single
    # source of truth for meta/steps/config/resource.  Column mirrors
    # (name/module/tags/…) were retired: 源存果算 — the payload is the
    # source; list-side meta/filters are methods over it.
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
