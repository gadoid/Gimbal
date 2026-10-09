"""分享(引用/副本)P2 请求/响应模型 —— 《…设计方案》§9。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShareCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resourceType: Literal["scenario", "suite"]
    resourceId: str = Field(min_length=1, max_length=128)
    granteeUserId: int
    mode: Literal["ref", "copy"] = "copy"


class ShareRefOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    resourceType: str          # scenario | suite(展开可空双键)
    scenarioId: str | None = None
    suiteId: int | None = None
    suiteName: str | None = None   # suite 引用的展示名(反查补)
    granteeUserId: int
    granteeName: str
    grantedByName: str
    grantedAt: str | None = None


class ShareCopyOut(BaseModel):
    """副本模式结果:新资源 id(场景)或 suiteId + 成员映射摘要。"""

    mode: Literal["copy"]
    scenarioId: str | None = None
    suiteId: int | None = None
    suiteName: str | None = None
    memberCount: int = 0
