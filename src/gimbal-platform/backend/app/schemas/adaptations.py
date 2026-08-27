"""适配中心请求/响应模型(spec §5)。显式 Field(alias=...) 对齐前端 camelCase。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_CAMEL = ConfigDict(populate_by_name=True)


class PendingChange(BaseModel):
    model_config = _CAMEL

    endpoint_id: str = Field(alias="endpointId")
    from_version: str = Field(alias="fromVersion")
    to_version: str = Field(alias="toVersion")


class CatalogAnomaly(BaseModel):
    model_config = _CAMEL

    endpoint_id: str = Field(alias="endpointId")
    reason: str
    detail: str


class CatalogDiffReport(BaseModel):
    model_config = _CAMEL

    pending: list[PendingChange] = Field(default_factory=list)
    anomalies: list[CatalogAnomaly] = Field(default_factory=list)
    baselined_now: int = Field(default=0, alias="baselinedNow")


class ImpactItem(BaseModel):
    model_config = _CAMEL

    scenario_id: str = Field(alias="scenarioId")
    step_index: int = Field(alias="stepIndex")
    source: str
    field: str
    via_var: str | None = Field(default=None, alias="viaVar")
    dataset_id: str | None = Field(default=None, alias="datasetId")
    dataset_column: str | None = Field(default=None, alias="datasetColumn")


class OpenBatchIn(BaseModel):
    model_config = _CAMEL

    endpoint_id: str = Field(alias="endpointId", min_length=1)


class OpOut(BaseModel):
    model_config = _CAMEL

    id: int
    batch_id: str = Field(alias="batchId")
    scenario_id: str = Field(alias="scenarioId")
    dataset_id: str | None = Field(default=None, alias="datasetId")
    op_type: str = Field(alias="opType")
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str
    applied_at: datetime | None = Field(default=None, alias="appliedAt")
    note: str | None = None


class SnapshotRef(BaseModel):
    model_config = _CAMEL

    entity_type: str = Field(alias="entityType")
    entity_id: str = Field(alias="entityId")


class BatchOut(BaseModel):
    model_config = _CAMEL

    batch_id: str = Field(alias="batchId")
    endpoint_id: str = Field(alias="endpointId")
    from_version: str = Field(alias="fromVersion")
    to_version: str = Field(alias="toVersion")
    status: str
    operator_id: int = Field(alias="operatorId")
    created_at: datetime = Field(alias="createdAt")
    closed_at: datetime | None = Field(default=None, alias="closedAt")
    op_counts: dict[str, int] = Field(default_factory=dict, alias="opCounts")


class BatchDetail(BatchOut):
    ops: list[OpOut] = Field(default_factory=list)
    snapshots: list[SnapshotRef] = Field(default_factory=list)


class OpCreateIn(BaseModel):
    model_config = _CAMEL

    op_type: str = Field(alias="opType", min_length=1)
    scenario_id: str = Field(alias="scenarioId", min_length=1)
    dataset_id: str | None = Field(default=None, alias="datasetId")
    payload: dict[str, Any] = Field(default_factory=dict)


class RestoredEntity(BaseModel):
    model_config = _CAMEL

    entity_type: str = Field(alias="entityType")
    entity_id: str = Field(alias="entityId")


class RollbackConflictItem(RestoredEntity):
    note: str


class RollbackReport(BaseModel):
    model_config = _CAMEL

    batch_id: str = Field(alias="batchId")
    status: str
    restored: list[RestoredEntity] = Field(default_factory=list)
    conflicts: list[RollbackConflictItem] = Field(default_factory=list)


class UnindexedStepOut(BaseModel):
    """C10 未索引步骤(缺 endpoint_id)—— 适配保护缺口警示条数据。"""

    model_config = _CAMEL

    scenario_id: str = Field(alias="scenarioId")
    step_index: int = Field(alias="stepIndex")
    reason: str


class OpPatchIn(BaseModel):
    """PATCH /ops/{id} 请求体:payload 整包替换(仅 pending 可改)。"""

    model_config = _CAMEL

    payload: dict[str, Any] = Field(default_factory=dict)
