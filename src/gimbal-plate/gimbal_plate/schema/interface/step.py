"""gimbal_plate.interface.step —— 单步骤数据模型与引用。

迁移自 ``gimbal.schema.step``,保持 ``kind/api/request/strategy`` 字段名与
discriminator 不变,确保现有 Scenario JSON 兼容。
"""
from __future__ import annotations

from typing import Literal, Annotated, Union, Optional
from pydantic import BaseModel, Field

from gimbal_plate.schema.base.ref import RefBase
from gimbal_plate.schema.interface.strategy import StrategyUnion
from gimbal_plate.schema.interface.api import ApiUnion
from gimbal_plate.schema.interface.request import RequestUnion


class Step(BaseModel):
    """单步骤数据模型。"""

    kind: Literal["step"] = "step"
    description: Optional[str] = Field(
        default=None,
        description="步骤说明,描述此步骤的能力/意图,供人和 Agent CLI 参考;非必填",
    )
    api: ApiUnion = Field(..., description="当前步骤的接口请求信息")
    request: RequestUnion = Field(..., description="当前步骤的请求体信息")
    strategy: list[StrategyUnion] = Field(
        default_factory=list,
        description="当前步骤需要执行的策略集",
    )


class StepRef(RefBase):
    kind: Literal["step_ref"] = "step_ref"


StepUnion = Annotated[
    Union[Step, StepRef],
    Field(discriminator="kind"),
]
