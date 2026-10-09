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
    scenarioName: str | None = None  # 场景引用的展示名(反查补,评审补记)
    memberCount: int | None = None   # suite 引用的成员数(共享行「N 个场景」)
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


class ReferrerViaSuite(BaseModel):
    """间接引用的经由 Suite(§7.6 判定式的 suite 分支)。"""

    model_config = ConfigDict(extra="forbid")

    suiteId: int
    suiteName: str


class ScenarioReferrerOut(BaseModel):
    """场景的一名引用人:直接引用与经由 Suite 的间接引用合并成一行。"""

    model_config = ConfigDict(extra="forbid")

    granteeUserId: int
    granteeName: str
    direct: bool                      # 直接引用该场景
    viaSuites: list[ReferrerViaSuite] = Field(default_factory=list)


class ScenarioReferrersOut(BaseModel):
    """§7.11 防误伤名单:保存提示与「已引用分享」徽标的数据源。"""

    model_config = ConfigDict(extra="forbid")

    items: list[ScenarioReferrerOut]
