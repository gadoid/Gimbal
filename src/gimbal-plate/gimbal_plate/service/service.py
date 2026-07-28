"""gimbal_plate.service.service —— 被测服务定义。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ServiceDefinition(BaseModel):
    """被测服务元信息。

    - ``name``:服务名(目录名),全仓唯一,如 ``fin`` / ``user`` / ``payment``
    - ``title``:业务名称,用于 Web 端展示
    - ``version``:服务定义版本
    - ``description``:业务描述
    - ``endpoints_module``:端点定义所在 Python 模块路径
    - ``models_module``:Pydantic 模型所在 Python 模块路径
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="服务名(目录名),全仓唯一")
    title: str = Field(..., description="服务业务名称")
    version: str = Field(default="1.0.0", description="服务定义版本")
    description: str = Field(default="", description="服务业务描述")

    endpoints_module: str = Field(
        default="", description="端点定义所在 Python 模块路径"
    )
    models_module: str = Field(
        default="", description="Pydantic 模型所在 Python 模块路径"
    )
