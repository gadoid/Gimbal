"""LifecycleEntry 形态的 setup（D-06 / 上轮评审 #9）。

kind = 要执行的**策略 kind**（dispatcher 分派键,如 sleep/sql）；params 为
该策略的参数面。执行时机：ScenarioRunner 在预处理后、step 循环前顺序执行；
任一失败 → 场景 error 且不进入 steps（与 suite before 括号同语义）。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Setup(BaseModel):
    kind: str = Field(description="要执行的策略 kind（dispatcher 分派键）")
    key: str = Field(default="", description="条目身份（日志/与 teardown 配对）")
    scope: Literal["scenario"] = "scenario"
    params: dict[str, Any] = Field(default_factory=dict)


SetupUnion = Setup
