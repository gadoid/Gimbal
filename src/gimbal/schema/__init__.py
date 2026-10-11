"""静态描述层 —— M2 生成物重新导出（Q19：导出名不变）+ D 类保留。

A/B 类自 ``_m2.py``（生成文件，``scripts/gen_m2.py gen`` 产出，禁改）；
``M2_HASH`` / ``M2_GENERATION`` 是这份构建的身份（代际门，M2 §5.1）。
D 类（plan / debug / param_registry / states）留在执行器手写。
UserCredential 取代旧 AuthSession 的定义部分；运行态在
``gimbal.auth.session.AuthSession``。
"""
from ._m2 import (  # noqa: F401
    M2_GENERATION, M2_HASH,
    AssertOperator, Assertion, Assign, Call, CheckDecl, CheckSelector,
    Config, Control, DebugSpec, Extract, FailurePolicy, File, GateDecl,
    LogSelector,
    Meta, Mock, NamedParams, PlanPolicy, RecordPolicy, ReportDefinition,
    ReportPresentation, ReportProjection, ReportSelection, Request,
    RequestUnion, Resource, ResourceUnion, RetryPolicy, RunOptions,
    RunUnion, Scope, Setup, SetupUnion, Step, StepUnion, StrategyBase,
    Scenario, StrategyPhase, StrategyUnion, SubscribeRule, SubscribeSpec,
    SuiteGraph,
    Teardown, TeardownUnion, TimePolicy, TimePolicyUnion, TimeoutPolicy,
    UnitDecl, UserCredential,
)
from .states import StepState  # noqa: F401

# where 键的合法事件字段（除执行上下文标签外）——与 plate _next 同源
EVENT_WHERE_FIELDS: tuple[str, ...] = (
    "event_type", "status", "scenario_id", "step_id", "suite_id",
    "plugin_name", "level",
)

__all__ = [
    "EVENT_WHERE_FIELDS",
    "M2_GENERATION", "M2_HASH",
    "AssertOperator", "Assertion", "Assign", "Call", "CheckDecl",
    "CheckSelector", "Config", "Control", "DebugSpec", "Extract",
    "GateDecl",
    "FailurePolicy", "File", "LogSelector", "Meta", "Mock", "NamedParams",
    "PlanPolicy", "RecordPolicy", "ReportDefinition", "ReportPresentation",
    "ReportProjection", "ReportSelection", "Request", "RequestUnion",
    "Resource", "ResourceUnion", "RetryPolicy", "RunOptions", "RunUnion",
    "Scenario",
    "Scope", "Setup", "SetupUnion", "Step", "StepState", "StepUnion",
    "StrategyBase", "StrategyPhase", "StrategyUnion", "SubscribeRule",
    "SubscribeSpec", "SuiteGraph", "Teardown", "TeardownUnion",
    "TimePolicy", "TimePolicyUnion", "TimeoutPolicy", "UnitDecl",
    "UserCredential",
]
