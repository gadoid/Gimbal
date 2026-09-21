"""schema.api —— 接口描述(transport)。"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class Api(BaseModel):
    """单步骤的接口请求信息(transport 部分)。

    view_hints 是平台视图扩展(可选,只有 platform 落库 dict 会含此字段);
    gimbal 导出时由 GimbalScenarioExporter 自动排除。
    """

    kind: Literal["api"] = "api"
    service: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
    path: str
    headers: dict[str, str] = Field(default_factory=dict, description="头信息字典")
    timeout: float = 30
    view_hints: dict[str, Any] | None = None


ApiUnion = Api