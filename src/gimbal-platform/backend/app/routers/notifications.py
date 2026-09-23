"""通知中心接口(权限方案 §3.3,P1b/M2.5)。

三只(§3.3):list / read / unread-count;外加按 type 开关的偏好读写
(开关必须先于吵闹型通知 —— adaptation_applied 一批扫几十场景,没有
关闭手段的铃铛上线第一天就会被整体关掉)。

``unread-count`` 顺带回传**角色版本号**(users.updated_at):前端把
currentUser 快照进 localStorage,降级后本地菜单要等 fetchMe 才收敛 ——
铃铛 30s 轮询顺带比对,变了就 refetch me(§1.3 第六轮,几乎零成本)。
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser, CurrentUser
from ..models import UserPref
from ..services import notifications as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    body: str
    link: str | None = None
    batch_id: str | None = Field(default=None, alias="batchId")
    created_at: str
    read_at: str | None = Field(default=None, alias="readAt")

    model_config = {"populate_by_name": True, "from_attributes": True}


class NotificationListOut(BaseModel):
    model_config = {"populate_by_name": True}

    items: list[NotificationOut]
    unread: int
    # 2026-09-23 分页批次:真分页信封(total = 未读优先同口径下的总条数)
    total: int = 0
    page: int = 1
    page_size: int = Field(default=50, alias="pageSize")


class ReadIn(BaseModel):
    ids: list[int] | None = Field(
        default=None, description="要标读的通知 id;缺省 = 全部已读")


class UnreadCountOut(BaseModel):
    model_config = {"populate_by_name": True}

    count: int
    # 角色版本(users.updated_at ISO):前端发现变了就 refetch me
    role_version: str | None = Field(default=None, alias="roleVersion")


class HandoffUnreadItem(BaseModel):
    """未读分享(悬浮标签数据源,2026-09-23 批次 F1)。

    前端以 Set<resourceId> 维护,列表行渲染 O(1) 查找;销账走
    POST /read(按 id)。
    """

    model_config = {"populate_by_name": True}

    id: int
    resource_id: str = Field(alias="resourceId")
    sender_name: str | None = Field(default=None, alias="senderName")


class HandoffUnreadOut(BaseModel):
    model_config = {"populate_by_name": True}

    items: list[HandoffUnreadItem] = Field(default_factory=list)


class PrefsOut(BaseModel):
    """按 type 通知开关;off 列表之外的类型全部开着。"""

    off: list[str]


class PrefsIn(BaseModel):
    off: list[Literal[
        "execution_finished", "adaptation_applied", "announcement",
        "scenario_unpublished", "role_changed", "resource_transferred",
        "resource_handoff",
    ]] = Field(default_factory=list)


@router.get("", response_model=NotificationListOut)
async def list_notifications(
    user: CurrentUser, db: DbSession,
    unread_only: bool = False,
    # 边界校验与其他分页路由同款(auth_sessions/admin/adaptations):
    # 裸 int 时 page_size=-1 会让 PG 抛 LIMIT must not be negative → 500,
    # 超大值则等于一次拉全表。
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> NotificationListOut:
    rows, unread, total = await svc.list_notifications(
        db, user.id, unread_only=unread_only, page=page, page_size=page_size)
    return NotificationListOut(
        items=[
            NotificationOut(
                id=n.id, type=n.type, title=n.title, body=n.body, link=n.link,
                batch_id=n.batch_id,
                created_at=n.created_at.isoformat() if n.created_at else "",
                read_at=n.read_at.isoformat() if n.read_at else None,
            )
            for n in rows
        ],
        unread=unread,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/read")
async def mark_read(user: CurrentUser, db: DbSession, body: ReadIn) -> dict:
    n = await svc.mark_read(db, user.id, body.ids)
    return {"marked": n}


@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(user: CurrentUser, db: DbSession) -> UnreadCountOut:
    return UnreadCountOut(
        count=await svc.unread_count(db, user.id),
        role_version=(
            user.updated_at.isoformat() if user.updated_at else None),
    )


@router.get("/handoff-unread", response_model=HandoffUnreadOut)
async def handoff_unread(user: CurrentUser, db: DbSession) -> HandoffUnreadOut:
    """未读分享列表(F1 悬浮标签数据源):场景行渲染 O(1) 查 Set 用。

    查询走 0005 已建的 (user_id, id) 索引,量级足够(方案 §1.4)。
    """
    from ..models import Notification

    rows = (await db.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.type == "resource_handoff",
            Notification.read_at.is_(None),
        ).order_by(Notification.id.desc())
    )).scalars().all()
    return HandoffUnreadOut(items=[
        HandoffUnreadItem(
            id=n.id,
            resource_id=n.resource_id or "",
            sender_name=(n.payload or {}).get("sender_name"),
        )
        for n in rows
    ])


# ── 按 type 开关(user_prefs,与铃铛同批上线)────────────────────────
_PREF_KEY = "notification_types"


@router.get("/preferences", response_model=PrefsOut)
async def get_prefs(user: CurrentUser, db: DbSession) -> PrefsOut:
    pref = (await db.execute(
        select(UserPref).where(
            UserPref.user_id == user.id, UserPref.key == _PREF_KEY)
    )).scalar_one_or_none()
    return PrefsOut(off=((pref.value or {}).get("off") or []) if pref else [])


@router.put("/preferences", response_model=PrefsOut)
async def put_prefs(
    user: CurrentUser, db: DbSession, body: PrefsIn
) -> PrefsOut:
    pref = (await db.execute(
        select(UserPref).where(
            UserPref.user_id == user.id, UserPref.key == _PREF_KEY)
    )).scalar_one_or_none()
    if pref is None:
        db.add(UserPref(
            user_id=user.id, key=_PREF_KEY, value={"off": body.off}))
    else:
        pref.value = {"off": body.off}
    await db.commit()
    return PrefsOut(off=body.off)


# ── 公告(admin only;写时对全员 fan-out 行)────────────────────────
class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(default="", max_length=4096)
    hours: int = Field(default=0, ge=0, le=24 * 365,
                       description="有效小时数;0 = 永不过期")


@router.post("/announcements", status_code=201)
async def post_announcement(
    admin: AdminUser, db: DbSession, body: AnnouncementIn
) -> dict:
    n = await svc.fan_out_announcement(
        db, title=body.title, body=body.body, hours=body.hours, actor=admin)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=admin.id,
        actor_name=admin.display_name or admin.username,
        action="announcement.publish", resource_type="announcement",
        resource_id=None, detail={"title": body.title, "delivered": n},
    )
    return {"delivered": n}
