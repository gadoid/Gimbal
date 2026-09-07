"""schema.step —— 单步骤数据模型与引用。

迁移自 ``gimbal.schema.step``,保持 ``kind/api/request/strategy`` 字段名与
discriminator 不变,确保现有 Scenario JSON 兼容。
"""
from __future__ import annotations

from typing import Literal, Annotated, Union, Optional
from pydantic import BaseModel, Field, field_validator

from gimbal_plate.schema.api import ApiUnion
from gimbal_plate.schema.ref import RefBase
from gimbal_plate.schema.request import RequestUnion
from gimbal_plate.schema.strategy import StrategyUnion


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
    field_states: Optional[dict[str, str]] = Field(
        default=None,
        description="场景侧字段状态稀疏增量(path → form/collapse/carry;"
                    "平台配置意图,09-05 §3.1)。plate 唯一消费点 = 导出定面"
                    "(export/platform.py 解析链);None/空 = 读穿共识默认",
    )

    @field_validator("field_states", mode="before")
    @classmethod
    def _normalize_field_states(cls, v: object) -> object:
        """形状防御(09-07 §3.2):不在此层拒 —— 词表校验归解析链
        (platform validate_field_states / plate resolve_state 三处镜像)。
        非 dict / 空集 → None(读穿共识默认,与收编前 extra=ignore 剥除
        行为等价,fail-open);dict 内仅保留 str 值(非 str 增量丢弃)。"""
        if not isinstance(v, dict):
            return None
        kept = {k: sv for k, sv in v.items() if isinstance(sv, str)}
        return kept or None


class StepRef(RefBase):
    kind: Literal["step_ref"] = "step_ref"


StepUnion = Annotated[
    Union[Step, StepRef],
    Field(discriminator="kind"),
]