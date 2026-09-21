"""schema —— 全部数据类定义统一入口。

布局(V3.2 扁平化):
- 根目录下:基础类型 + Step 及其下挂的所有 interface 类型,各占一个文件
- endpoint/:EndpointSpec 及其 4 个内嵌子类型,保留目录形式(契约复杂度高)

依赖关系(单向,无环):
    base 层(states/time_policy/retry_policy/auth)
      ↓
    interface 层(resource/setup/teardown/api/strategy/step/scenario/request)
      ↓
    endpoint 出口(Request 引用 DeclarationEntry,Scenario 整体作为真相源)

外部 import 应统一通过本 __init__,直接 import 子文件应仅限 schema 内部。
"""
from __future__ import annotations

# ── 基础类型 ──
from gimbal_plate.schema.auth import AuthSession
from gimbal_plate.schema.retry_policy import RetryPolicy
from gimbal_plate.schema.states import StepState
from gimbal_plate.schema.time_policy import (
    RecordPolicy,
    TimePolicy,
    TimePolicyUnion,
    TimeoutPolicy,
)

# ── endpoint(目录形式,保持现状) ──
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)

# ── Step 及其下挂类型 ──
from gimbal_plate.schema.api import Api, ApiUnion
from gimbal_plate.schema.request import Request, RequestUnion
from gimbal_plate.schema.resource import (
    File,
    Mock,
    Resource,
    ResourceUnion,
)
from gimbal_plate.schema.strategy import (
    AssertOperator,
    Assertion,
    Assign,
    Extract,
    FailurePolicy,
    Scope,
    StrategyBase,
    StrategyPhase,
    StrategyUnion,
)
from gimbal_plate.schema.setup import Setup, SetupUnion
from gimbal_plate.schema.teardown import Teardown, TeardownUnion
from gimbal_plate.schema.step import Step, StepUnion

# ── Scenario / Suite ──
from gimbal_plate.schema.scenario import (
    Config,
    Meta,
    RunUnion,
    Scenario,
    Suite,
)


__all__ = [
    # base
    "AuthSession",
    "RetryPolicy",
    "StepState",
    "RecordPolicy",
    "TimePolicy",
    "TimePolicyUnion",
    "TimeoutPolicy",
    # endpoint
    "ApiSpec",
    "EndpointMetadata",
    "EndpointSpec",
    "DeclarationEntry",
    "RequestSpec",
    "ResponseSpec",
    # api / request
    "Api",
    "ApiUnion",
    "Request",
    "RequestUnion",
    # resource
    "File",
    "Mock",
    "Resource",
    "ResourceUnion",
    # strategy
    "AssertOperator",
    "Assertion",
    "Assign",
    "Extract",
    "FailurePolicy",
    "Scope",
    "StrategyBase",
    "StrategyPhase",
    "StrategyUnion",
    # setup / teardown / step
    "Setup",
    "SetupUnion",
    "Teardown",
    "TeardownUnion",
    "Step",
    "StepUnion",
    # scenario
    "Config",
    "Meta",
    "RunUnion",
    "Scenario",
    "Suite",
]