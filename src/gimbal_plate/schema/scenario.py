"""M2 Scenario / Meta / Config（M2 方案 v2.4 §3 M2/M4/M5/M6/M11；§9.2）。

- M6：Meta 只有 ``name`` 必填，其余给默认值——需要调用方补默认值才能
  过校验的字段不是执行必需；``system`` 并入（plate 副本已有）、
  ``plate`` 新增（M11：系统 → 已验证修订，值随《Plate 版本模型》4.1）。
- M5：平台视图字段（``endpoints`` / ``navigation`` / ``config_summary``）
  不进定义。
- M2：``config.users`` 由 AuthSession 改为 UserCredential（只存凭证）。
- M9：``timePolicy`` 缺省 None = 不限时（以执行器为准）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .credential import UserCredential
from .resource import ResourceUnion
from .retry_policy import RetryPolicy
from .setup import SetupUnion
from .step import StepUnion
from .teardown import TeardownUnion
from .time_policy import TimePolicyUnion


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str                                    # 唯一必填（M6）
    description: str = ""
    module: str = ""
    priority: int = 0
    author: str = ""
    owner: str = ""
    tags: list[str] = []
    version: str = ""
    createTime: datetime | None = None           # M7：普通 datetime
    expire: bool = False
    requirementRef: list[str] = []
    system: list[str] = []                       # 并入（plate 副本已有）
    plate: dict[str, str] = {}                   # M11：系统 → "<line>#<n>" | "working"


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setup: list[SetupUnion] = Field(default_factory=list)
    teardown: list[TeardownUnion] = Field(default_factory=list)
    services: dict[str, str] = Field(default_factory=dict)
    users: dict[str, UserCredential] = Field(default_factory=dict)   # M2
    timePolicy: Optional[TimePolicyUnion] = None  # M9：None = 不限时
    retry: Optional[RetryPolicy] = None
    vars: dict[str, Any] = Field(
        default_factory=dict,
        description="变量声明；字面量或生成式 spec dict；CLI --var 优先级更高")


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["scenario"] = "scenario"
    scenarioId: str = Field(..., description="场景 ID，前缀 sc")
    meta: Meta
    config: Config
    resource: dict[str, ResourceUnion]
    steps: list[StepUnion]
