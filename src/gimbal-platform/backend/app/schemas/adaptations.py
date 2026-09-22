"""适配中心请求/响应模型(spec §5)。显式 Field(alias=...) 对齐前端 camelCase。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .page import PageOut

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
    source: str | None = None
    field: str | None = None
    via_var: str | None = Field(default=None, alias="viaVar")
    dataset_id: str | None = Field(default=None, alias="datasetId")
    dataset_column: str | None = Field(default=None, alias="datasetColumn")


class RefsDriftReport(BaseModel):
    """倒排索引 endpoint 面 vs plate 目录 diff(只读;结构同 carry drift)。

    dangling:refs 有、plate 无(悬空引用);zeroRef:plate 有、refs 无
    (全网零引用);plateReachable=False 时两清单不可信,先看信号。
    """

    model_config = _CAMEL

    dangling: list[str] = Field(default_factory=list)
    zero_ref: list[str] = Field(default_factory=list, alias="zeroRef")
    plate_reachable: bool = Field(alias="plateReachable")


class ImpactSummaryService(BaseModel):
    """impact-summary 单服务条(配套方案 §3.2):pending 归组 + 波及面。"""

    model_config = _CAMEL

    name: str
    change_count: int = Field(alias="changeCount", ge=0)
    case_count: int = Field(alias="caseCount", ge=0)
    recent_fail_count: int = Field(alias="recentFailCount", ge=0)


class ImpactSummaryTotals(BaseModel):
    model_config = _CAMEL

    change_count: int = Field(alias="changeCount", ge=0)
    service_count: int = Field(alias="serviceCount", ge=0)
    case_count: int = Field(alias="caseCount", ge=0)
    recent_fail_count: int = Field(alias="recentFailCount", ge=0)


class ImpactSummaryReport(BaseModel):
    """GET /adaptations/impact-summary:客户端传入 pending endpointIds
    (catalog/diff 的产物),本接口纯读聚合 —— recentFail 为全站口径
    (跨 owner),不回执行详情/场景标题。"""

    model_config = _CAMEL

    services: list[ImpactSummaryService] = Field(default_factory=list)
    totals: ImpactSummaryTotals


class OpenBatchIn(BaseModel):
    model_config = _CAMEL

    endpoint_id: str = Field(alias="endpointId", min_length=1)


class CarryBatchIn(BaseModel):
    """POST /adaptations/carry-batches 请求体(spec §7):service 缺省 = 全局默认表。"""

    model_config = _CAMEL

    service: str | None = Field(default=None, min_length=1)


class OpOut(BaseModel):
    model_config = _CAMEL

    id: int
    batch_id: str = Field(alias="batchId")
    scenario_id: str | None = Field(default=None, alias="scenarioId")
    dataset_id: str | None = Field(default=None, alias="datasetId")
    op_type: str = Field(alias="opType")
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str
    applied_at: datetime | None = Field(default=None, alias="appliedAt")
    note: str | None = None
    # G1-E1 读侧投影:活名(可读时)→ 本批快照 → 裸 id
    scenario_display_name: str | None = Field(
        default=None, alias="scenarioDisplayName")
    dataset_name: str | None = Field(default=None, alias="datasetName")


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
    # G1-E2 触发上下文投影:catalog_versions.spec_json = 批次开立时刻的
    # 形状(审计正确,不问 plate 现值);空串 = 戳缺失(理论不可达)。
    endpoint_name: str = Field(default="", alias="endpointName")
    endpoint_method: str = Field(default="", alias="endpointMethod")
    endpoint_path: str = Field(default="", alias="endpointPath")



class BatchListOut(PageOut[BatchOut]):
    """M4 Page 信封(§6.3)。"""

class BatchDetail(BatchOut):
    ops: list[OpOut] = Field(default_factory=list)
    snapshots: list[SnapshotRef] = Field(default_factory=list)


class OpCreateIn(BaseModel):
    model_config = _CAMEL

    op_type: str = Field(alias="opType", min_length=1)
    scenario_id: str | None = Field(default=None, alias="scenarioId")
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
