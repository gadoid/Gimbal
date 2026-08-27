"""Schemas for executions (V3 — 每-run 明细已随 exec_runs 表退役)。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    # 执行时场景快照是否存在(存量行 False → 前端"导出场景"置灰)。
    has_scenario_snapshot: bool = False


class ExecutionListOut(BaseModel):
    items: list[ExecutionOut]
    total: int


class ExecutionRowOut(BaseModel):
    """行级状态(spec §9.1)— registry(asdict 的 snake_case)与 JSONL
    回放(camelCase 键)两种输入都收(populate_by_name),响应按别名
    序列化为 camelCase。"""

    model_config = ConfigDict(populate_by_name=True)

    seq: int
    dataset_id: str | None = Field(default=None, alias="datasetId")
    row_index: int = Field(default=0, alias="rowIndex")
    rep: int = 0
    status: str
    case_dir: str = Field(default="", alias="caseDir")
    started_at: str | None = Field(default=None, alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")


class ExecutionRowsOut(BaseModel):
    items: list[ExecutionRowOut]
