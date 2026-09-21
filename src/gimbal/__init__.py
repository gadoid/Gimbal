"""Gimbal testing framework - top-level API exposure."""

from .version import __version__

# Schema 模块 - 所有数据模型
from .schema import (
    # 枚举类
    StepState,
    Scope,
    AssertOperator,
    StrategyPhase,
    FailurePolicy,
    # 资源模型
    Resource,
    Mock,
    File,
    ResourceUnion,
    # API 模型
    Api,
    ApiUnion,
    # 请求模型
    Request,
    RequestUnion,
    # 步骤模型
    Step,
    StepUnion,
    # 策略模型
    StrategyBase,
    Extract,
    Assign,
    Assertion,
    StrategyUnion,
    # 时间策略模型
    TimePolicy,
    TimeoutPolicy,
    RecordPolicy,
    TimePolicyUnion,
    # 重试策略
    RetryPolicy,
    # 场景模型
    Meta,
    Config,
    Scenario,
    # 前置/后置动作
    Setup,
    SetupUnion,
    Teardown,
    TeardownUnion,
)

__all__ = [
    # 版本
    "__version__",
    # 枚举类
    "StepState",
    "Scope",
    "AssertOperator",
    "StrategyPhase",
    "FailurePolicy",
    # 资源模型
    "Resource",
    "Mock",
    "File",
    "ResourceUnion",
    # API 模型
    "Api",
    "ApiUnion",
    # 请求模型
    "Request",
    "RequestUnion",
    # 步骤模型
    "Step",
    "StepUnion",
    # 策略模型
    "StrategyBase",
    "Extract",
    "Assign",
    "Assertion",
    "StrategyUnion",
    # 时间策略模型
    "TimePolicy",
    "TimeoutPolicy",
    "RecordPolicy",
    "TimePolicyUnion",
    # 重试策略
    "RetryPolicy",
    # 场景模型
    "Meta",
    "Config",
    "Scenario",
    # 前置/后置动作
    "Setup",
    "SetupUnion",
    "Teardown",
    "TeardownUnion",
]
