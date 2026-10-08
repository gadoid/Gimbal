"""Suite 域请求/响应形态(权限域二期 P1,《Suite成员层、引用分享与
浏览镜头-设计方案》§9)。

P1 口径:无发布(P2)、无引用(P2)—— publish/share 相关形态留后续
迭代再入本模块。分页信封与字段投影按 M4 既有口径(list 用 Page 形态)。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SuiteCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)


class SuitePatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)


class SuiteMembersAddIn(BaseModel):
    scenarioIds: list[str] = Field(..., min_length=1)


class SuiteMembersOrderIn(BaseModel):
    """整表排序:按列表顺序重编 sort(0..n-1)。"""

    scenarioIds: list[str] = Field(..., min_length=1)


class SuiteSummaryOut(BaseModel):
    suiteId: int
    name: str
    description: str
    visibility: str
    mode: str
    memberCount: int
    createdAt: str | None = None
    updatedAt: str | None = None


class SuitePageOut(BaseModel):
    items: list[SuiteSummaryOut]
    total: int
    page: int
    pageSize: int


class SuiteMemberOut(BaseModel):
    scenarioId: str
    name: str
    module: str
    visibility: str
    sort: int
    addedAt: str | None = None


class SuiteDetailOut(BaseModel):
    suiteId: int
    name: str
    description: str
    visibility: str
    mode: str
    memberCount: int
    createdAt: str | None = None
    updatedAt: str | None = None
    members: list[SuiteMemberOut]


class SuiteLookupItem(BaseModel):
    """场景反查所属 suite(GET /api/scenarios/{id}/suites)。"""

    suiteId: int
    name: str
    memberCount: int
    ownerName: str = ""
