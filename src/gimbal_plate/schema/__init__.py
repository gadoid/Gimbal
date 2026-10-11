"""gimbal_plate.schema —— M1（知识侧）+ M2（用例/框架侧）统一包。

M2（用例/框架侧）自步骤 4 切换窗口起直接在本包（原 ``_next/`` 并行
建设期已结束，目录已删除）。定义与执行器 ``gimbal.schema._m2`` 同源
（同一份 JSON Schema 生成），只是 plate 侧保留 pydantic 定义形态作为
唯一可编辑真源。

M1（知识侧）：``endpoint/``（EndpointSpec 家族）、``service_definition``。
框架：``generator``、``states``。
"""
from gimbal_plate.schema.call import Call
from gimbal_plate.schema.credential import UserCredential
from gimbal_plate.schema.report_definition import (
    ReportDefinition,
    ReportPresentation,
    ReportProjection,
    ReportSelection,
)
from gimbal_plate.schema.request import Request, RequestUnion
from gimbal_plate.schema.resource import File, Mock, Resource, ResourceUnion
from gimbal_plate.schema.retry_policy import RetryPolicy
from gimbal_plate.schema.run_options import DebugSpec, RunOptions
from gimbal_plate.schema.scenario import Config, Meta, Scenario
from gimbal_plate.schema.setup import Setup, SetupUnion
from gimbal_plate.schema.step import Step, StepUnion
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
from gimbal_plate.schema.subscribe import (
    EVENT_WHERE_FIELDS,
    LogSelector,
    SubscribeRule,
)
from gimbal_plate.schema.suite import (
    CheckDecl,
    CheckSelector,
    Control,
    GateDecl,
    NamedParams,
    PlanPolicy,
    SuiteGraph,
    UnitDecl,
)
from gimbal_plate.schema.suite import SuiteGraph
from gimbal_plate.schema.teardown import Teardown, TeardownUnion
from typing import Annotated, Union
from pydantic import Field

RunUnion = Annotated[Union[Scenario, SuiteGraph], Field(discriminator="kind")]
from gimbal_plate.schema.time_policy import (
    RecordPolicy,
    TimePolicy,
    TimePolicyUnion,
    TimeoutPolicy,
)

# M2 构建代际（不兼容变更时递增；P8 加法演进下新增可选字段是兼容变更）
M2_GENERATION = 1

# M1 / 框架（非 M2，保持原位）
from gimbal_plate.schema.endpoint import DeclarationEntry, EndpointMetadata
from gimbal_plate.schema.service_definition import ServiceDefinition
from gimbal_plate.schema.states import StepState

# A2:端点模型真源在方言层(dialect.models)。急切转发会与
# dialect.models → schema.endpoint.io_spec 的共享模型依赖成环,
# 故门面用 PEP 562 惰性导出。
_LAZY_ENDPOINT_NAMES = {
    "DeclarationEntry", "EndpointMetadata", "EndpointSpec",
    "RequestSpec", "ResponseSpec", "Binding", "HttpBinding",
}


def __getattr__(name: str):
    if name in _LAZY_ENDPOINT_NAMES:
        if name in ("DeclarationEntry", "EndpointMetadata"):
            from gimbal_plate.schema.endpoint import __getattr__ as _ep
            return _ep(name)
        from gimbal_plate.dialect import models as _models
        return getattr(_models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "M2_GENERATION", "RunUnion",
    # M2 A 类
    "Call", "Request", "RequestUnion", "Step", "StepUnion",
    "Resource", "Mock", "File", "ResourceUnion",
    "StrategyBase", "Extract", "Assign", "Assertion", "StrategyUnion",
    "Scope", "AssertOperator", "StrategyPhase", "FailurePolicy",
    "Setup", "SetupUnion", "Teardown", "TeardownUnion",
    "TimePolicy", "TimeoutPolicy", "RecordPolicy", "TimePolicyUnion",
    "RetryPolicy", "Meta", "Config", "Scenario",
    "Control", "UnitDecl", "NamedParams", "CheckSelector", "CheckDecl",
    "GateDecl", "PlanPolicy", "SuiteGraph",
    "UserCredential", "DebugSpec", "RunOptions",
    # M2 B 类
    "LogSelector", "SubscribeRule", "EVENT_WHERE_FIELDS",
    "ReportSelection", "ReportProjection", "ReportPresentation",
    "ReportDefinition",
    # M1 / 框架
    "DeclarationEntry", "EndpointMetadata",
    "ServiceDefinition", "StepState",
]
