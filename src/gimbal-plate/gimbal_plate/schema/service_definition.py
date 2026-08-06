"""gimbal_plate.schema.service_definition —— 被测服务定义(M2 不可变域)。

本文件原位于 ``gimbal_plate.service.service``,于 V3.1 架构重构中迁入
``schema/``。归位理由:
    - ``ServiceDefinition`` 是 Pydantic ``BaseModel``,与其他 schema/* 同类
      (``EndpointSpec`` / ``ApiSpec`` / ``IOFieldBinding`` …);
    - ``service/`` 包当前承担"服务层纯函数"职责,与数据模型语义不符;
    - V3 设计文档 PLATE_V3_DESIGN.md §V4 已质疑 ``service/service.py``
      的位置与字段用途,本迁入为后续 V4 评估做准备。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ServiceDefinition(BaseModel):
    """被测服务元信息。

    - ``name``:服务名(目录名),全仓唯一,如 ``fin`` / ``user`` / ``payment``
    - ``title``:业务名称,用于 Web 端展示
    - ``version``:被测系统部署版本(人维护,字面与被测系统版本保持一致,无格式校验)
    - ``description``:业务描述
    - ``endpoints_module``:端点定义所在 Python 模块路径
    - ``models_module``:Pydantic 模型所在 Python 模块路径
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="服务名(目录名),全仓唯一")
    title: str = Field(..., description="服务业务名称")
    version: str = Field(
        default="1.0.0",
        description="被测系统部署版本(人维护,字面与被测系统版本保持一致,无格式校验)",
    )
    description: str = Field(default="", description="服务业务描述")

    endpoints_module: str = Field(
        default="", description="端点定义所在 Python 模块路径"
    )
    models_module: str = Field(
        default="", description="Pydantic 模型所在 Python 模块路径"
    )

    @model_validator(mode="after")
    def _validate_version_nonempty(self) -> "ServiceDefinition":
        # version — 被测系统部署版本,人维护;只校验非空,不校验格式
        # (被测系统用什么版本号方案是它自己的事,plate 不强加 semver)
        if not self.version:
            raise ValueError("ServiceDefinition.version 不可为空")
        return self