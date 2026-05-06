"""Step / Scenario 模型定义"""
from typing import Any, Optional
from pydantic import BaseModel, Field
from schema.states import StepState


class Step(BaseModel):
    """测试步骤模型"""

    name: str
    action: Action
    state: StepState = StepState.PENDING
    error: Optional[str] = None
    retry: int = 0
    timeout: Optional[int] = None


class Scenario(BaseModel):
    """测试场景模型"""

    name: str
    description: Optional[str] = None
    steps: list[Step] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
