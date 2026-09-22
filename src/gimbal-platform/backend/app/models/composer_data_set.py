"""SQLAlchemy model for the V3 Scenario Composer DataSet row.

A DataSet is a tabular payload of ``rows[]`` attached to a Scenario.  Used
to fan out the same Scenario into N parameterised runs.  (Formerly hung
off a 1:1 Case row; the Case layer was dissolved — datasets parameterise
the scenario's ``config.vars`` directly.)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Computed, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._json_path import json_array_len
from ._types import JsonVar


class ComposerDataSet(Base):
    """A DataSet row (V3 composer).  ``rows`` holds the parameter matrix."""

    __tablename__ = "composer_data_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True
    )  # matches DataSet.datasetId
    # NO ACTION DEFERRABLE(§2.1):scenario_store.delete 在 Python 管整组
    # 子表,FK 只做校验器。
    scenario_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("composer_scenarios.scenario_id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    rows: Mapped[list] = mapped_column(JsonVar, default=list)
    # 行数生成列(G3/方案 §4):rows 数组长度,源存果算 —— 写侧三处
    # (data_set_store create/update、scenario_store.copy)已停写,
    # dispatch 本就不消费该列(run_dispatcher 按实际行数算 total_runs)。
    row_count: Mapped[int] = mapped_column(
        Integer, Computed(json_array_len(rows), persisted=True)
    )
    var_unlocks: Mapped[list] = mapped_column(JsonVar, default=list)
    # 变量锁本地放开清单(spec 2026-09-15 §3.2):数据集级元数据,
    # 与场景级 config.var_locks 互不影响;引擎不读。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
