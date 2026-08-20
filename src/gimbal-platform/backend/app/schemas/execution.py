"""Schemas for executions (V3 — 每-run 明细已随 exec_runs 表退役)。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario_id: str
    status: str
    total_runs: int
    passed: int
    failed: int
    started_at: datetime | None
    finished_at: datetime | None
    config: dict


class ExecutionListOut(BaseModel):
    items: list[ExecutionOut]
    total: int
