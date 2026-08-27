"""schema.ref —— 所有引用模型的基类 + 通用内联引用。

与 ``gimbal.schema.ref`` 行为一致;仅做物理迁移,不修改 ``kind`` 命名。
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class RefBase(BaseModel):
    """所有引用模型的基类。

    子类必须:
      1. 用 ``kind`` 字段声明自己的 discriminator(便于 Pydantic 多态反序列化)
      2. 通过 ``ref`` 字段(继承自本类)声明要拉取的 asset ref 字符串
    """

    ref: str = Field(
        ...,
        description="asset ref 字符串,格式 namespace/name:tag 或 namespace/name@digest",
    )


class Ref(RefBase):
    """通用内联引用:可出现在 dict / list 任意位置的待实例化占位符。

    识别规则:
        ``isinstance(x, RefBase)`` 为 true 即视为待实例化节点;
        解释器 (gimbal.core.asset_materializer.AssetMaterializer) 不区分具体类型,
        统一按 "pull + 替换" 处理。
    """

    kind: Literal["ref"] = "ref"