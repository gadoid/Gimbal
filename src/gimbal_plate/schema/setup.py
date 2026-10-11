"""M2 Setup（M2 方案 v2.4 §3 M8；步骤 1 定义形态）。

以执行器 LifecycleEntry 为准（M8——plate 副本仍是 ``kind:
Literal["setup"]`` 旧形态，已漂移）：``kind`` = 策略名，``params``
开放字典（按 kind 查注册表校验）。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Setup(BaseModel):
    """前置动作条目（预处理后、step 循环前顺序执行）。"""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="要执行的策略 kind（dispatcher 分派键）")
    key: str = Field(default="", description="条目身份（日志/与 teardown 配对）")
    scope: Literal["scenario"] = "scenario"
    params: dict[str, Any] = Field(default_factory=dict)


SetupUnion = Setup
