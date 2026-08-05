"""schema.retry_policy —— 用例级重试策略。"""
from __future__ import annotations

from typing import Literal, List
from pydantic import BaseModel, Field


class RetryPolicy(BaseModel):
    """重试策略配置模型。"""

    kind: Literal["retry_policy"] = "retry_policy"
    maxAttempts: int = Field(1, description="最大尝试次数")
    backoffSeconds: float = Field(20, description="退避基础时长")
    retryOn: List[str] = Field(default_factory=list, description="触发重试的条件标签")