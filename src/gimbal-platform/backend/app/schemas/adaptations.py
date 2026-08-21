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
