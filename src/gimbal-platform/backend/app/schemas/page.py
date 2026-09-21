"""通用 Page 信封(M4,PG迁移方案 §4.1/§6.3)。

各域列表端点从「全量裸数组」迁到 ``{items, total, page, pageSize}`` 统一
契约 —— 信封泛型化,免每个域手抄一份四字段。驼峰别名 + populate_by_name
与 ScenarioListOut/ExecutionListOut 既有口径一致(构造侧收 page_size,
响应侧出 pageSize)。
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PageOut(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)

    items: list[T]
    total: int = 0
    page: int = 1
    page_size: int = Field(default=20, alias="pageSize")
