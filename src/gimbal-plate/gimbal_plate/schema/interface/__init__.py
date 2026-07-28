"""gimbal_plate.interface —— Step 及其下挂的接口、请求、响应、策略类型。"""
from gimbal_plate.schema.interface.resource import (
    Resource,
    Mock,
    File,
    MockRef,
    FileRef,
    ResourceUnion,
)
from gimbal_plate.schema.interface.api import Api, ApiRef, ApiUnion
from gimbal_plate.schema.interface.request import Request, RequestRef, RequestUnion
from gimbal_plate.schema.interface.strategy import (
    StrategyBase,
    Extract,
    Assign,
    Assertion,
    StrategyRef,
    StrategyUnion,
    Scope,
    AssertOperator,
    StrategyPhase,
    FailurePolicy,
)
from gimbal_plate.schema.interface.setup import Setup, SetupRef, SetupUnion
from gimbal_plate.schema.interface.teardown import Teardown, TeardownRef, TeardownUnion
from gimbal_plate.schema.interface.step import Step, StepRef, StepUnion
from gimbal_plate.schema.interface.scenario import (
    Meta,
    Config,
    Scenario,
    ScenarioRef,
    Suite,
    SuiteRef,
    RunUnion,
)

__all__ = [
    "Resource",
    "Mock",
    "File",
    "MockRef",
    "FileRef",
    "ResourceUnion",
    "Api",
    "ApiRef",
    "ApiUnion",
    "Request",
    "RequestRef",
    "RequestUnion",
    "StrategyBase",
    "Extract",
    "Assign",
    "Assertion",
    "StrategyRef",
    "StrategyUnion",
    "Scope",
    "AssertOperator",
    "StrategyPhase",
    "FailurePolicy",
    "Setup",
    "SetupRef",
    "SetupUnion",
    "Teardown",
    "TeardownRef",
    "TeardownUnion",
    "Step",
    "StepRef",
    "StepUnion",
    "Meta",
    "Config",
    "Scenario",
    "ScenarioRef",
    "Suite",
    "SuiteRef",
    "RunUnion",
]
