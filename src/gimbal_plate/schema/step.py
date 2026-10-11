"""M2 Step（M2 方案 v2.4 §3 M3/M4；步骤 1 定义形态）。

- M3：``endpoint`` 提升为一等可选字段（M1 接口 id）——步骤 ↔ 接口定义
  的溯源锚点，执行器调用边界改读它作执行标签；plate 副本的
  ``field_states`` 视图字段不进定义（M4——编排器状态移到定义之外的
  ``ui.fieldStates``）。
- M1：``extra="forbid"``（拼写错误的字段名在编译期暴露）。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .call import Call
from .request import RequestUnion
from .strategy import StrategyUnion


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["step"] = "step"
    description: Optional[str] = Field(
        default=None, description="步骤说明；非必填")
    endpoint: Optional[str] = Field(
        default=None,
        description="M1 接口 id（M3）：步骤 ↔ plate 接口定义的溯源锚点，"
                    "系统前缀决定取 meta.plate 的哪一项；无锚点 = 手写原始调用")
    call: Call = Field(
        ..., description="协议中立调用：{protocol(必填), ...协议自有字段}")
    request: Optional[RequestUnion] = Field(
        default=None, description="请求体信息；body 结构由协议定义")
    strategy: list[StrategyUnion] = Field(..., description="策略集")


StepUnion = Step
