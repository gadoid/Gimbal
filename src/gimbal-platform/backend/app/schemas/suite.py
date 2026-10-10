"""Suite 域请求/响应形态(权限域二期 P1,《Suite成员层、引用分享与
浏览镜头-设计方案》§9)。

P1 口径:无发布(P2)、无引用(P2)—— publish/share 相关形态留后续
迭代再入本模块。分页信封与字段投影按 M4 既有口径(list 用 Page 形态)。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SuiteCreateIn(BaseModel):
    """name 可省略:服务端生成不重名的草稿名(「未命名 Suite N」,
    重构方案:画布首次拖入创建草稿);带 name 的创建不是草稿。"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)


class SuitePatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    # 完成编排时清除草稿标记(重构方案:正式名称在此填、草稿在此清)
    clearDraft: bool = False


class CompositionMemberIn(BaseModel):
    """composition 的成员行:顺序即列表顺序(聚合发起序/串联链路序/
    扇出源在首位);role 见 suite_members.role。"""

    scenarioId: str = Field(min_length=1, max_length=128)
    role: Literal["main", "before", "after"] = "main"


class SuiteCompositionIn(BaseModel):
    """整体保存(重构方案 PUT /suites/{id}/composition):模式、成员
    及顺序、编排配置一次落库;rev 乐观锁,冲突 409 附最新内容。"""

    rev: int
    mode: Literal["aggregate", "chain", "fanout", "compose"] = "aggregate"
    members: list[CompositionMemberIn] = Field(max_length=100)
    modeConfig: dict = Field(default_factory=dict)
    # 公共 Suite 加私有成员的发布确认标志(与 add_members 同一套 409)
    publishUnpublished: bool = False


class SuiteMembersAddIn(BaseModel):
    scenarioIds: list[str] = Field(..., min_length=1)
    # P2 §7.9:公共 suite 加未发布成员的发布确认标志(确认后成员
    # 发布 + 入组同事务;缺省 False → 409 suite_member_publish_required)
    publishUnpublished: bool = False


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
    rev: int = 0
    isDraft: bool = False          # mode_config.draft 投影(列表「草稿」标记)
    createdAt: str | None = None
    updatedAt: str | None = None
    # 最近运行摘要(重构方案 02 列):**只算本人发起**(不变量 2),
    # kind = suite_graph(编排)/ batch(聚合批次);无本人发起 = None。
    latestRun: dict | None = None
    # 发布者名(display_name 优先;仅列表端点填充)—— 公共用例集页
    # 「发布者」列(2026-10-10 IA 调整),其余端点为 None 不受影响。
    ownerName: str | None = None
    # P2 publish 回执:本次级联发布的成员(数据集一并公开,§7.9)
    publishedMembers: list[str] | None = None


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
    role: Literal["main", "before", "after"] = "main"
    sort: int
    addedAt: str | None = None


class SuiteDetailOut(BaseModel):
    suiteId: int
    name: str
    description: str
    visibility: str
    mode: str
    memberCount: int
    rev: int = 0
    isDraft: bool = False
    # P2/重构:前端不自己推导角色 —— access(owner/admin/ref/public)
    # 与能力位(§7.6 判定;public 不可运行=不变量 7,ref 不可改)
    access: str | None = None
    canEdit: bool | None = None
    canRun: bool | None = None
    canShare: bool | None = None
    modeConfig: dict | None = None
    createdAt: str | None = None
    updatedAt: str | None = None
    members: list[SuiteMemberOut]


class SuiteLookupItem(BaseModel):
    """场景反查所属 suite(GET /api/scenarios/{id}/suites)。"""

    suiteId: int
    name: str
    memberCount: int
    ownerName: str = ""
