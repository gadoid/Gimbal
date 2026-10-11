"""M2 RetryPolicy（步骤 1 定义形态）。

与执行器 ``gimbal/schema/retrypolicy.py`` 同构。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["retry_policy"] = "retry_policy"
    maxAttempts: int = Field(1, description="最大尝试次数")
    backoffSeconds: float = Field(20, description="退避基础时长")
    retryOn: list[str] = Field(
        default_factory=list, description="触发重试的条件标签")
