"""schema.call —— 协议中立调用描述（plate 镜像，v2.1 批次 F P2）。

与 gimbal.schema.call 同构：开放模型，protocol 之外的字段由协议定义解释。
Step.call 是唯一调用形态（api 平台形态输入面已随 api→call 清理退役）。
"""
from __future__ import annotations

from typing import Optional, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Call(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: Literal["call"] = "call"
    protocol: str = Field(default="http", description="协议判别；默认 http")
    # 平台视图扩展(composer 写入,导出 gimbal 时剥离)
    view_hints: Optional[dict] = Field(default=None, description="平台视图扩展:endpoint_id 等")

