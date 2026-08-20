"""Schemas for executions + runs (Spec-2 §4.5 E)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── outputs ────────────────────────────────────────────────────
class ExecRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    idx: int
    status: str
    exit_code: int | None
    report_path: str | None
    log_path: str | None
    command_line: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None


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


class ExecutionDetailOut(ExecutionOut):
    runs: list[ExecRunOut]


class ExecutionListOut(BaseModel):
    items: list[ExecutionOut]
    total: int