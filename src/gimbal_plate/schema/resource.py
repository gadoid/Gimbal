"""schema.resource —— 用例级资源(Mock/File)。"""
from __future__ import annotations

from typing import Any, Literal, Annotated, Union
from pydantic import BaseModel, Field


class Resource(BaseModel):
    """资源模型。"""

    name: str = Field(..., description="资源名称")


class Mock(Resource):
    kind: Literal["mock"] = "mock"
    image: str = Field(description="容器镜像")
    config: dict[str, Any] = Field(description="服务配置")
    portMapping: dict[int, int] = Field(description="端口映射")


class File(Resource):
    kind: Literal["file"] = "file"
    path: str = Field(description="路径")


ResourceUnion = Annotated[
    Union[Mock, File],
    Field(discriminator="kind"),
]