"""gimbal_plate.interface.scenario —— Scenario/Suite 与 Meta/Config。

迁移自 ``gimbal.schema.scenario``,字段命名与可选性保持兼容;
``Meta`` 中除 ``requirementRef`` 外的字段保留 ``...`` 必填,匹配现有 Scenario
校验行为。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Literal, Annotated, Union
from pydantic import BaseModel, Field

from gimbal_plate.schema.base.ref import RefBase
from gimbal_plate.schema.base.retrypolicy import RetryPolicy
from gimbal_plate.schema.base.timepolicy import TimePolicyUnion, RecordPolicy
from gimbal_plate.schema.base.auth import AuthSession
from gimbal_plate.schema.interface.resource import ResourceUnion
from gimbal_plate.schema.interface.step import StepUnion
from gimbal_plate.schema.interface.setup import SetupUnion
from gimbal_plate.schema.interface.teardown import TeardownUnion


class Meta(BaseModel):
    """用例信息配置模型。"""

    name: str = Field(..., description="用例名")
    description: str = Field(..., description="用例信息描述")
    module: str = Field(..., description="用例所属的业务模块")
    priority: int = Field(..., description="用例等级描述")
    author: str = Field(..., description="用例作者")
    owner: str = Field(..., description="维护人/执行人")
    tags: list[str] = Field(..., description="用例标签")
    version: str = Field(description="用例版本号")
    createTime: datetime = Field(description="创建时间")
    expire: bool = Field(description="过期标志位")
    requirementRef: list[RefBase] = Field(description="需求,用例关联链接")


class Config(BaseModel):
    """用例执行配置模型。"""

    setup: list[SetupUnion] = Field(default_factory=list, description="用例前置动作")
    teardown: list[TeardownUnion] = Field(default_factory=list, description="用例后置动作")
    services: dict[str, str] = Field(default_factory=dict, description="服务与URL映射关系")
    users: dict[str, AuthSession] = Field(
        default_factory=dict, description="认证信息字典"
    )
    timePolicy: TimePolicyUnion = Field(
        default_factory=RecordPolicy,
        description="时间处理策略:超时检查或耗时记录",
    )
    retry: Optional[RetryPolicy] = None
    vars: dict[str, Any] = Field(
        default_factory=dict,
        description="变量声明;字面量或生成式 spec dict;CLI --var 优先级更高",
    )


class Scenario(BaseModel):
    """用例数据模型。"""

    kind: Literal["scenario"] = "scenario"
    scenarioId: str = Field(..., description="场景,用例ID,前缀为sc")
    meta: Meta = Field(..., description="用例的元信息,用于管理用例")
    config: Config = Field(..., description="本次执行的配置信息")
    resource: dict[str, ResourceUnion] = Field(
        description="存放用例需要执行的相关资源信息"
    )
    steps: list[StepUnion] = Field(..., description="存放具体的执行过程")


class ScenarioRef(RefBase):
    kind: Literal["scenario_ref"] = "scenario_ref"


class Suite(BaseModel):
    kind: Literal["suite"] = "suite"
    suite: list[Scenario] = Field(..., description="scenario集合,暂时使用列表实现")


class SuiteRef(RefBase):
    kind: Literal["suite_ref"] = "suite_ref"


RunUnion = Annotated[
    Union[Scenario, ScenarioRef, Suite, SuiteRef],
    Field(discriminator="kind"),
]
