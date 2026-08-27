"""schema.scenario —— Scenario/Suite 与 Meta/Config。

迁移自 ``gimbal.schema.scenario``,字段命名与可选性保持兼容;
``Meta`` 中除 ``requirementRef`` 外的字段保留 ``...`` 必填,匹配现有 Scenario
校验行为。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Literal, Annotated, Union
from pydantic import BaseModel, Field

from gimbal_plate.schema.auth import AuthSession
from gimbal_plate.schema.ref import RefBase
from gimbal_plate.schema.resource import ResourceUnion
from gimbal_plate.schema.retry_policy import RetryPolicy
from gimbal_plate.schema.setup import SetupUnion
from gimbal_plate.schema.step import StepUnion
from gimbal_plate.schema.teardown import TeardownUnion
from gimbal_plate.schema.time_policy import TimePolicyUnion, RecordPolicy


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
    # V3 新增:归属被测系统标识。V3 PLATE_V3_DESIGN.md §3 要求"该系统的 Meta
    # 默认模板",必须携带 system 信息。
    # V3.2 变更为 list[str]:一条用例可同时归属多个被测系统(如"fin 与 mall
    # 共用的资金链路用例")。默认空 list 保持向后兼容。
    system: list[str] = Field(
        default_factory=list,
        description="[V3] 归属被测系统标识列表(如 ['fin'] 或 ['fin', 'mall'])",
    )


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
    """用例数据模型。

    V3.1 平台视图扩展字段（PLATE_V3_DESIGN.md §7.2）:
    - endpoints: 平台后端消费的 endpoint 渲染视图列表（PlatformEndpointView dict 列表）
    - navigation: 平台前端按 service 分组的导航树
    - config_summary: 配置项分类提示（env_placeholder / scenario_var_placeholder / auth_placeholder / literal）
    默认值均为 None,不携带时 GimbalScenarioExporter.to_dict() 通过 model_dump(exclude=...) 过滤掉。
    """

    kind: Literal["scenario"] = "scenario"
    scenarioId: str = Field(..., description="场景,用例ID,前缀为sc")
    meta: Meta = Field(..., description="用例的元信息,用于管理用例")
    config: Config = Field(..., description="本次执行的配置信息")
    resource: dict[str, ResourceUnion] = Field(
        description="存放用例需要执行的相关资源信息"
    )
    steps: list[StepUnion] = Field(..., description="存放具体的执行过程")

    # ── 平台视图扩展字段（PLATE_V3_DESIGN.md §7.2） ────────────────
    endpoints: list[dict[str, Any]] | None = Field(
        default=None,
        description="[V3.1 平台视图] endpoint 渲染视图列表（PlatformEndpointView dict）",
    )
    navigation: dict[str, Any] | None = Field(
        default=None,
        description="[V3.1 平台视图] 按 service 分组的导航树",
    )
    config_summary: dict[str, Any] | None = Field(
        default=None,
        description="[V3.1 平台视图] 配置项分类提示(env_placeholder/var_placeholder/...)",
    )


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