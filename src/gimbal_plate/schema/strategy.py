"""M2 策略（M2 方案 v2.4 §3；步骤 1 定义形态）。

与执行器 ``gimbal/schema/strategy.py`` 同构（枚举成员名/值、字段、
判别联合），差异仅 M1：A 类统一 ``extra="forbid"``。``view_note`` 是
plate 副本的视图字段，不进定义（M5）。
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class Scope(str, Enum):
    FRAMEWORK = "framework"
    SUITE = "suite"        # 历史值 "session" 已退役（与 ContextLayer.SUITE 对齐）
    SCENARIO = "scenario"
    STEP = "step"
    REQUEST = "request"


class AssertOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    EXISTS = "exists"
    EMPTY = "empty"
    LENGTH_EQ = "length_eq"
    SCHEMA = "schema"


class StrategyPhase(str, Enum):
    """策略执行阶段（value 沿用历史值，存量场景零迁移）。"""

    PREPARE = "before_request"
    EXTRACTING = "after_request"
    VERIFYING = "verifying"
    TEARDOWN = "teardown"


class FailurePolicy(str, Enum):
    ABORT = "abort"
    CONTINUE = "continue"
    WARN = "warn"
    RETRY = "retry"


class StrategyBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    phase: Optional[StrategyPhase] = None
    order: int = 0
    enabled: bool = True
    onFailure: FailurePolicy = FailurePolicy.ABORT
    timeout: Optional[float] = None
    tags: List[str] = Field(default_factory=list)


class Extract(StrategyBase):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["extract"] = "extract"
    phase: StrategyPhase = StrategyPhase.EXTRACTING
    expression: str            # JSONPath，在 scratch 上导航
    target: str                # 写入目标的 key
    scope: Scope = Scope.STEP
    default: Optional[Any] = None
    required: bool = True


class Assign(StrategyBase):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["assign"] = "assign"
    phase: StrategyPhase = StrategyPhase.PREPARE
    source: Any                # 路径或值
    target: str                # 模板路径
    scope: Scope = Scope.SCENARIO
    default: Optional[Any] = None
    required: bool = True


class Assertion(StrategyBase):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["assertion"] = "assertion"
    phase: StrategyPhase = StrategyPhase.VERIFYING
    target: str                # 断言目标字段
    operator: AssertOperator
    expected: Any = None
    message: Optional[str] = None
    soft: bool = False


StrategyUnion = Annotated[
    Union[Extract, Assign, Assertion],
    Field(discriminator="kind"),
]
