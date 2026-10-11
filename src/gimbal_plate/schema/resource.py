"""M2 Resource（步骤 1 定义形态）。

与执行器 ``gimbal/schema/resource.py`` 同构；D 类句柄描述的执行语义
在执行器（执行能力 D3），此处只有被编写的定义。
"""
from __future__ import annotations

from typing import Annotated, Any, Dict, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class Resource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="资源名称")


class Mock(Resource):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["mock"] = "mock"
    image: str = Field(description="容器镜像")
    config: dict[str, Any] = Field(description="服务配置")
    portMapping: dict[int, int] = Field(description="端口映射")


class File(Resource):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["file"] = "file"
    path: str = Field(description="路径")


ResourceUnion = Annotated[Union[Mock, File], Field(discriminator="kind")]
