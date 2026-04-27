from typing import Literal, Any
from pydantic import BaseModel, Field, model_validator

class BaseAction(BaseModel):
    """所有动作的公共基类"""
    type: str                                              # discriminator
    name: str | None = None                                # 可选显式名字（用于报告/日志）
    when: str | None = None                                # 条件执行表达式（P1）
    on_failure: Literal["abort", "continue", "ignore"] | None = None
    timeout_ms: int | None = None                          # 单动作超时