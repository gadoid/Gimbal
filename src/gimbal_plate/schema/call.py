"""M2 Call（M2 方案 v2.4 §3 M1；步骤 1 定义形态）。

与执行器 ``gimbal/schema/call.py`` 同构：**唯一保持开放（extra=allow）
的模型**（M1 的唯一例外）——协议自有字段由协议 ``params_model`` 校验
（http 已是 forbid）。Release 4.5：场景存储只存场景自有字段，binding
派生字段由 plate 投影（/convert 合并）；``protocol`` 必填。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Call(BaseModel):
    """协议中立调用外壳。"""

    model_config = ConfigDict(extra="allow")

    kind: Literal["call"] = "call"
    protocol: str = Field(
        ..., description="协议名（必填）；协议注册表的分派键")
