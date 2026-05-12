from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from .base import SealedBaseModel, ContextLayer
from .scenario import ScenarioContext


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class StepInputs(BaseModel):
    """Step 输入态:开始时定型,执行期间只读。frozen=True 强制不可变。"""
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    
    step_id: str
    step_name: str
    strategy_kind: str
    strategy_spec: dict
    resolved_vars: dict[str, Any]


class AssertionResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    name: str
    passed: bool
    expected: Any
    actual: Any
    message: Optional[str] = None


class ErrorInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    type: str
    message: str
    traceback: Optional[str] = None


class StepOutcome(BaseModel):
    """Step 产物态:执行期间累积,seal 时定型。"""
    model_config = ConfigDict(validate_assignment=True)
    
    status: StepStatus = StepStatus.PENDING
    extracted: dict[str, Any] = Field(default_factory=dict)
    assertions: list[AssertionResult] = Field(default_factory=list)
    response_artifact: Optional[str] = None    # 指向 scenario.channels 中的 artifact name
    error_info: Optional[ErrorInfo] = None
    duration_ms: Optional[float] = None
    retry_count: int = 0
    promotions_made: list[str] = Field(default_factory=list)   # 本 step 提升过的 key 列表


class StepContext(SealedBaseModel):
    inputs: StepInputs
    outcome: StepOutcome = Field(default_factory=StepOutcome)
    started_at: datetime
    ended_at: Optional[datetime] = None
    
    parent: ScenarioContext = Field(exclude=True)
    
    @property
    def layer(self) -> ContextLayer:
        return ContextLayer.STEP
    
    @property
    def step_id(self) -> str:
        return self.inputs.step_id
    
    @property
    def scenario_id(self) -> str:
        return self.parent.scenario_id