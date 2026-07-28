"""gimbal_plate.interface.api —— 接口描述(transport)与引用。"""
from __future__ import annotations

from typing import Literal, Union, Annotated
from pydantic import BaseModel, Field

from gimbal_plate.schema.base.ref import RefBase


class Api(BaseModel):
    """单步骤的接口请求信息(transport 部分)。"""

    kind: Literal["api"] = "api"
    service: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
    path: str
    headers: dict[str, str] = Field(default_factory=dict, description="头信息字典")
    timeout: float = 30


class ApiRef(RefBase):
    kind: Literal["api_ref"] = "api_ref"


ApiUnion = Annotated[
    Union[Api, ApiRef],
    Field(discriminator="kind"),
]
