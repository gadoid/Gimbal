from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from .base import SealedBaseModel, ContextLayer
from .scenario import ScenarioContext
from gimbal.exceptions import SealedContextError


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class StepScratch:
    """Step 级统一临时存储。

    生命周期随 StepContext，finalize 后 clear。
    所有 Step 内临时数据统一存储，通过 JSONPath 导航读取。

    约定 key：
        request_method / request_url / request_headers / request_body
        response_status / response_headers / response_body
        duration_ms
        其余 key 为业务临时变量
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._sealed: bool = False

    def set(self, key: str, value: Any) -> None:
        if self._sealed:
            raise SealedContextError(
                f"StepScratch is sealed; cannot set '{key}'"
            )
        if key.startswith("$."):
            self._set_jsonpath(key, value)
        else:
            self._data[key] = value

    def _set_jsonpath(self, path: str, value: Any) -> None:
        """支持 JSONPath 写入嵌套结构。

        path=$.request_body.order_id ->
            _data["request_body"]["order_id"] = value
        """
        from gimbal.utils.jsonpath import set_value as jsonpath_set
        jsonpath_set(self._data, path, value)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def has(self, key: str) -> bool:
        return key in self._data

    def as_dict(self) -> dict[str, Any]:
        """暴露给 JSONPath 引擎的根对象。"""
        return self._data

    def seal(self) -> None:
        self._sealed = True

    def clear(self) -> None:
        self._data.clear()

    @property
    def is_sealed(self) -> bool:
        return self._sealed


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
    scratch: StepScratch = Field(default_factory=StepScratch, exclude=True)
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

    model_config = {
        **SealedBaseModel.model_config,
        "arbitrary_types_allowed": True,
    }