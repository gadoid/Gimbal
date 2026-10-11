"""M2 Request（步骤 1 定义形态）。

与执行器 ``gimbal/schema/request.py`` 同构；plate 副本的视图字段
``fields_meta`` 不进定义（M5——前端只在类型声明出现过，无写入点）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class Request(BaseModel):
    """请求体载体（body 结构由协议定义解释）。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["request"] = "request"
    # str: 原始文本；dict: JSON 对象；list: JSON 数组（批量请求）
    body: Union[str, Dict[str, Any], List[Any]] = Field(default_factory=dict)


RequestUnion = Request
