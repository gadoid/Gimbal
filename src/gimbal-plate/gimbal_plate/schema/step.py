"""schema.step —— 单步骤数据模型。

迁移自 ``gimbal.schema.step``。v2.1 批次 F 定稿 + api→call 清理(2026-09-28):
call 是唯一调用形态 —— api 平台形态输入面已退役,api 步骤在 model_validate
期即被拒(错误信息指向迁移脚本);平台视图渲染与 gimbal 导出都只消费 call。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from gimbal_plate.schema.call import Call
from gimbal_plate.schema.request import RequestUnion
from gimbal_plate.schema.strategy import StrategyUnion


class Step(BaseModel):
    """单步骤数据模型(call 唯一调用形态)。

    extra 维持 ignore(平台草稿携带 step 级 `id` 等编排键,沿收编前
    语义静默剥除);api 形态是**显式拒绝**的唯一例外 —— 由
    ``_reject_api_form`` 在 validate 前拦截并指向迁移脚本。
    """

    kind: Literal["step"] = "step"
    description: Optional[str] = Field(
        default=None,
        description="步骤说明,描述此步骤的能力/意图,供人和 Agent CLI 参考;非必填",
    )
    call: Call = Field(
        description="协议中立调用(唯一调用形态;http 协议字段 service/method/path/headers/timeout)",
    )
    request: RequestUnion = Field(..., description="当前步骤的请求体信息")

    @model_validator(mode="before")
    @classmethod
    def _reject_api_form(cls, data: object) -> object:
        """api 形态已退役:显式报错并指向迁移路径,不静默丢弃。"""
        if isinstance(data, dict) and "api" in data:
            raise ValueError(
                "step.api 形态已退役(v2.1 批次 F):请改用 "
                'call{protocol:"http", service, method, path, ...};'
                "存量文件迁移见 scripts/migrate_legacy_case.py"
            )
        return data

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


StepUnion = Step
