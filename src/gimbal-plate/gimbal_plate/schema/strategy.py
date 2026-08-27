"""schema.strategy —— 策略抽象基类与三种实现。"""
from __future__ import annotations

from typing import Any, Optional, Literal, Union, Annotated, List
from enum import Enum
from pydantic import BaseModel, Field

from gimbal_plate.schema.ref import RefBase


class Scope(str, Enum):
    FRAMEWORK = "framework"
    SESSION = "session"
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
    BEFORE_REQUEST = "before_request"  # SQL 注入数据、Assign 准备入参
    AFTER_REQUEST = "after_request"  # Extract 提取字段
    VERIFYING = "verifying"  # Assertion、DBChecker
    TEARDOWN = "teardown"  # SQL 清理、Chaos 恢复


class FailurePolicy(str, Enum):
    ABORT = "abort"  # 中止整个 step
    CONTINUE = "continue"  # 记录错误但继续
    WARN = "warn"  # 仅警告
    RETRY = "retry"  # 配合 retry 字段


class StrategyBase(BaseModel):
    name: Optional[str] = None
    phase: Optional[StrategyPhase] = None  # 处理的阶段
    order: int = 0  # 执行顺序
    enabled: bool = True  # 是否启动
    onFailure: FailurePolicy = FailurePolicy.ABORT  # 失败处理策略
    timeout: Optional[float] = None  # 策略执行超时
    tags: List[str] = Field(default_factory=list)  # 标签

    # ── 平台视图扩展字段（PLATE_V3_DESIGN.md §7.2） ────────────────
    view_note: Optional[str] = Field(
        default=None,
        description="[V3.1 平台视图] 人类语言策略摘要,如 'response.code eq 0'",
    )


class Extract(StrategyBase):
    kind: Literal["extract"] = "extract"
    expression: str  # JSONPath,在 scratch 上导航
    target: str  # 写入目标的 key
    scope: Scope = Scope.STEP
    default: Optional[Any] = None
    required: bool = True


class Assign(StrategyBase):
    kind: Literal["assign"] = "assign"
    source: Any  # 路径或者值
    target: str  # 模板路径
    scope: Scope = Scope.SCENARIO
    default: Optional[Any] = None  # 提取失败,注入的默认值
    required: bool = True  # 注入失败是否抛出异常


class Assertion(StrategyBase):
    kind: Literal["assertion"] = "assertion"
    target: str  # 断言的目标字段
    operator: AssertOperator  # 断言的比较符
    expected: Any = None  # 断言的比较值
    message: Optional[str] = None  # 断言失败信息
    soft: bool = False  # 软断言


class StrategyRef(RefBase):
    kind: Literal["strategy_ref"] = "strategy_ref"


StrategyUnion = Annotated[
    Union[Extract, Assign, Assertion, StrategyRef],
    Field(discriminator="kind"),
]