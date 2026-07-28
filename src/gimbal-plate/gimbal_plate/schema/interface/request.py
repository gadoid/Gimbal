"""gimbal_plate.interface.request —— 请求体容器与引用。

与 ``gimbal.schema.request`` 行为一致;``body`` 支持 ``str | dict | list`` 三种形态,
由调用方通过 ``api.headers.Content-Type`` 显式声明。
"""
from __future__ import annotations

from typing import Any, Literal, Union, Annotated, Dict, List
from pydantic import BaseModel, Field

from gimbal_plate.schema.base.ref import RefBase


class Request(BaseModel):
    """单步骤的请求体信息。"""

    kind: Literal["request"] = "request"
    body: Union[str, Dict[str, Any], List[Any]] = Field(default_factory=dict)


class RequestRef(RefBase):
    kind: Literal["request_ref"] = "request_ref"


RequestUnion = Annotated[
    Union[Request, RequestRef],
    Field(discriminator="kind"),
]
