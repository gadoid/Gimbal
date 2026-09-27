"""schema.step —— 单步骤数据模型。

迁移自 ``gimbal.schema.step``,保持 ``kind/api/request/strategy`` 字段名与
discriminator 不变,确保现有 Scenario JSON 兼容。
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

from pydantic import model_validator

from gimbal_plate.schema.api import ApiUnion
from gimbal_plate.schema.call import Call
from gimbal_plate.schema.request import RequestUnion
from gimbal_plate.schema.strategy import StrategyUnion


class Step(BaseModel):
    """单步骤数据模型（v2.1 批次 F P2：api/call 恰好其一）。

    api = 平台形态输入（composer/UI 产出，兼容存量）；
    call = gimbal 形态（convert 产物与迁移后语料的输入面）。
    """

    kind: Literal["step"] = "step"
    description: Optional[str] = Field(
        default=None,
        description="步骤说明,描述此步骤的能力/意图,供人和 Agent CLI 参考;非必填",
    )
    api: Optional[ApiUnion] = Field(
        default=None, description="当前步骤的接口请求信息（平台形态）",
    )
    call: Optional[Call] = Field(
        default=None, description="协议中立调用（gimbal 形态）",
    )
    request: RequestUnion = Field(..., description="当前步骤的请求体信息")

    @model_validator(mode="after")
    def _exactly_one_call_form(self) -> "Step":
        if (self.api is None) == (self.call is None):
            raise ValueError("step 必须声明 api（平台形态）或 call（gimbal 形态）其一")
        return self

    @property
    def view_api(self):
        """平台视图渲染用的 api 访问器：api 形态直取；call 形态合成 Api。

        平台视图（view_hints/端点匹配/字段面）是 http 语法糖的形状；
        call 形态输入（迁移后语料）经此访问器无需转换即可渲染。
        """
        if self.api is not None:
            return self.api
        from gimbal_plate.schema.api import Api
        c = self.call
        return Api(
            kind="api",
            service=str(c.model_extra.get("service", "")) if c.model_extra else "",
            method=c.model_extra.get("method", "GET") if c.model_extra else "GET",
            path=c.model_extra.get("path", "/") if c.model_extra else "/",
            headers=dict(c.model_extra.get("headers", {})) if c.model_extra else {},
            timeout=float(c.model_extra.get("timeout", 30)) if c.model_extra else 30,
        )
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