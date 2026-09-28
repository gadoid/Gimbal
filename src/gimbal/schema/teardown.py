"""LifecycleEntry 形态的 teardown（D-06 / 上轮评审 #9）。

执行时机：step 循环结束后**必达逆序**执行（失败不改变主判定,记录为
teardown 留痕——与 suite after 括号同语义）。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Teardown(BaseModel):
    kind: str = Field(description="要执行的策略 kind（dispatcher 分派键）")
    key: str = Field(default="", description="条目身份（日志/与 setup 配对）")
    scope: Literal["scenario"] = "scenario"
    params: dict[str, Any] = Field(default_factory=dict)


TeardownUnion = Teardown
