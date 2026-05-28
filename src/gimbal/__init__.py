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
    # 引用基类
    RefBase,
    # 资源模型
    Resource,
    Mock,
    File,
    MockRef,
    FileRef,
    ResourceUnion,
    # API 模型
    Api,
    ApiRef,
    ApiUnion,
    # 请求模型
    Request,
    RequestRef,
    RequestUnion,
    # 步骤模型
    Step,
    StepRef,
    StepUnion,
    # 策略模型
    StrategyBase,
    Extract,
    Assign,
    Assertion,
    StrategyRef,
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
    SetupRef,
    SetupUnion,
    Teardown,
    TeardownRef,
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
    # 引用基类
    "RefBase",
    # 资源模型
    "Resource",
    "Mock",
    "File",
    "MockRef",
    "FileRef",
    "ResourceUnion",
    # API 模型
    "Api",
    "ApiRef",
    "ApiUnion",
    # 请求模型
    "Request",
    "RequestRef",
    "RequestUnion",
    # 步骤模型
    "Step",
    "StepRef",
    "StepUnion",
    # 策略模型
    "StrategyBase",
    "Extract",
    "Assign",
    "Assertion",
    "StrategyRef",
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
    "SetupRef",
    "SetupUnion",
    "Teardown",
    "TeardownRef",
    "TeardownUnion",
]
