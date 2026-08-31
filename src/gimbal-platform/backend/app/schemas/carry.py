"""carry API 请求/响应模型(spec §3.2)。dict 的 null 值 = 显式 null 行;
键缺席 = 未配置(spec §3.1)。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CarryMapIn(BaseModel):
    bindings: dict[str, str | None] = Field(default_factory=dict)


class DefaultsIn(BaseModel):
    defaults: dict[str, str | None] = Field(default_factory=dict)


class DefaultsOut(BaseModel):
    defaults: dict[str, str | None] = Field(default_factory=dict)


class BindingsOut(BaseModel):
    bindings: dict[str, dict[str, str | None]] = Field(default_factory=dict)


class ServiceBindingsOut(BaseModel):
    bindings: dict[str, str | None] = Field(default_factory=dict)


class CarryFieldFace(BaseModel):
    path: str
    type: str = "string"
    description: str = ""


class ServiceFieldsOut(BaseModel):
    fields: list[CarryFieldFace] = Field(default_factory=list)


class ServiceDrift(BaseModel):
    service: str
    orphaned: list[str] = Field(default_factory=list)
    uncovered: list[str] = Field(default_factory=list)
    renamedSuggestions: list[dict[str, str]] = Field(default_factory=list)


class DriftReport(BaseModel):
    services: list[ServiceDrift] = Field(default_factory=list)
    plateReachable: bool = True
