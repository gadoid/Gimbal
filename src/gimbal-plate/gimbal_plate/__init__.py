"""gimbal_plate —— 被测系统结构知识库。

第一期职责边界:
    - 本包定义被测系统的接口数据结构、字段元信息、业务元信息;
    - 不直接参与 Gimbal 执行期调用,只作为 Platform 的查询数据源;
    - 与现有 ``gimbal.schema`` 保持兼容,共享 ``kind`` discriminator 命名,
      现有 Scenario JSON 可继续被 Gimbal 加载。

目录约定:
    - ``gimbal_plate.schema.base``       非 Step 相关的公共基础类型
    - ``gimbal_plate.schema.interface``  Step 及其下挂的接口、请求、响应、策略类型
    - ``gimbal_plate.schema.endpoint``   被测接口的定义态/实例态/Schema 投影
    - ``gimbal_plate.service``           被测服务注册与业务信息
    - ``gimbal_plate.registry``          服务、接口、模型的查询注册表
"""
from __future__ import annotations

# 基座与接口层
from gimbal_plate.schema.base import (
    auth as _auth,
    ref as _ref,
    retrypolicy as _retrypolicy,
    states as _states,
    timepolicy as _timepolicy,
)
from gimbal_plate.schema.interface import (
    api as _api,
    request as _request,
    resource as _resource,
    scenario as _scenario,
    setup as _setup,
    step as _step,
    strategy as _strategy,
    teardown as _teardown,
)

# 业务能力
from gimbal_plate.schema.endpoint.endpoint import (
    ApiSpec,
    EndpointInfo,
    EndpointSpec,
)
from gimbal_plate.service.service import ServiceDefinition

# 公共 API 入口(平台调用方使用)
from gimbal_plate import registry as _registry

__all__ = [
    # base
    "AuthSession",
    "RefBase",
    "Ref",
    "RetryPolicy",
    "StepState",
    "TimePolicy",
    "TimeoutPolicy",
    "RecordPolicy",
    "TimePolicyUnion",
    # interface
    "Api",
    "ApiRef",
    "ApiUnion",
    "Request",
    "RequestRef",
    "RequestUnion",
    "Resource",
    "Mock",
    "File",
    "MockRef",
    "FileRef",
    "ResourceUnion",
    "Setup",
    "SetupRef",
    "SetupUnion",
    "Teardown",
    "TeardownRef",
    "TeardownUnion",
    "Scenario",
    "ScenarioRef",
    "Suite",
    "SuiteRef",
    "RunUnion",
    "Meta",
    "Config",
    "Step",
    "StepRef",
    "StepUnion",
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
    # endpoint / service
    "ApiSpec",
    "EndpointInfo",
    "EndpointSpec",
    "ServiceDefinition",
    # public API
    "registry",
]

# 公共类型重导出
AuthSession = _auth.AuthSession
RefBase = _ref.RefBase
Ref = _ref.Ref
RetryPolicy = _retrypolicy.RetryPolicy
StepState = _states.StepState
TimePolicy = _timepolicy.TimePolicy
TimeoutPolicy = _timepolicy.TimeoutPolicy
RecordPolicy = _timepolicy.RecordPolicy
TimePolicyUnion = _timepolicy.TimePolicyUnion

Api = _api.Api
ApiRef = _api.ApiRef
ApiUnion = _api.ApiUnion
Request = _request.Request
RequestRef = _request.RequestRef
RequestUnion = _request.RequestUnion
Resource = _resource.Resource
Mock = _resource.Mock
File = _resource.File
MockRef = _resource.MockRef
FileRef = _resource.FileRef
ResourceUnion = _resource.ResourceUnion
Setup = _setup.Setup
SetupRef = _setup.SetupRef
SetupUnion = _setup.SetupUnion
Teardown = _teardown.Teardown
TeardownRef = _teardown.TeardownRef
TeardownUnion = _teardown.TeardownUnion
Scenario = _scenario.Scenario
ScenarioRef = _scenario.ScenarioRef
Suite = _scenario.Suite
SuiteRef = _scenario.SuiteRef
RunUnion = _scenario.RunUnion
Meta = _scenario.Meta
Config = _scenario.Config
Step = _step.Step
StepRef = _step.StepRef
StepUnion = _step.StepUnion
StrategyBase = _strategy.StrategyBase
Extract = _strategy.Extract
Assign = _strategy.Assign
Assertion = _strategy.Assertion
StrategyRef = _strategy.StrategyRef
StrategyUnion = _strategy.StrategyUnion
Scope = _strategy.Scope
AssertOperator = _strategy.AssertOperator
StrategyPhase = _strategy.StrategyPhase
FailurePolicy = _strategy.FailurePolicy

# 公共 API facade(简写)
registry = _registry
