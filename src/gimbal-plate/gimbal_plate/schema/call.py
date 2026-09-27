"""schema.call —— 协议中立调用描述（plate 镜像，v2.1 批次 F P2）。

与 gimbal.schema.call 同构：开放模型，protocol 之外的字段由协议定义解释。
Step 的 api/call 恰好其一（api 为平台形态输入兼容，call 为 gimbal 形态）。
"""
from __future__ import annotations

from typing import Optional, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Call(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: Literal["call"] = "call"
    protocol: str = Field(default="http", description="协议判别；默认 http")
    # 平台视图扩展(与 Api.view_hints 同构;composer 写入,导出 gimbal 时剥离)
    view_hints: Optional[dict] = Field(default=None, description="平台视图扩展:endpoint_id 等")

    @classmethod
    def from_api(cls, api: Any) -> "Call":
        payload = api.model_dump(exclude={"kind"}) if hasattr(api, "model_dump") else dict(api)
        payload.pop("kind", None)
        return cls(protocol="http", **payload)
