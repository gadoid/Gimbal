"""分享(副本)请求/响应模型 —— 仅 copy 模式(引用模式退场,ADR-0003 #20)。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShareCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resourceType: Literal["scenario", "suite"]
    resourceId: str = Field(min_length=1, max_length=128)
    granteeUserId: int
    # ref 模式已退役(ADR-0003 #20);显式传 "ref" → 422(枚举收窄)
    mode: Literal["copy"] = "copy"


class ShareCopyOut(BaseModel):
    """副本模式结果:新资源 id(场景)或 suiteId + 成员映射摘要。"""

    mode: Literal["copy"]
    scenarioId: str | None = None
    suiteId: int | None = None
    suiteName: str | None = None
    memberCount: int = 0
