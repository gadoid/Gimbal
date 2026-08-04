"""gimbal_plate.interface.request —— 请求体容器与引用。

与 ``gimbal.schema.request`` 行为一致;``body`` 支持 ``str | dict | list`` 三种形态,
由调用方通过 ``api.headers.Content-Type`` 显式声明。
"""
from __future__ import annotations

from typing import Any, Literal, Union, Annotated, Dict, List
from pydantic import BaseModel, Field

from gimbal_plate.schema.base.ref import RefBase
from gimbal_plate.schema.endpoint.io_spec import IOFieldBinding


class Request(BaseModel):
    """单步骤的请求体信息。

    fields_meta 是平台视图扩展(可选,只有 platform 落库 dict 会含此字段);
    gimbal 导出时由 GimbalScenarioExporter 通过 model_dump(exclude=...) 自动排除,
    保证 gimbal 可执行 dict 干净。
    """

    kind: Literal["request"] = "request"
    body: Union[str, Dict[str, Any], List[Any]] = Field(default_factory=dict)
    fields_meta: Dict[str, IOFieldBinding] | None = None


class RequestRef(RefBase):
    kind: Literal["request_ref"] = "request_ref"


RequestUnion = Annotated[
    Union[Request, RequestRef],
    Field(discriminator="kind"),
]
