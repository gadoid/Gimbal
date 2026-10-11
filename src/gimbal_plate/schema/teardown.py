"""M2 Teardown（M2 方案 v2.4 §3 M8；步骤 1 定义形态）。

以执行器 LifecycleEntry 为准（M8）：step 循环结束后必达逆序执行，
失败不改变主判定、记录为 teardown 留痕。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Teardown(BaseModel):
    """后置动作条目。"""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="要执行的策略 kind（dispatcher 分派键）")
    key: str = Field(default="", description="条目身份（日志/与 setup 配对）")
    scope: Literal["scenario"] = "scenario"
    params: dict[str, Any] = Field(default_factory=dict)


TeardownUnion = Teardown
