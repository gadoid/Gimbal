"""分享(副本)— S7.4 引用分享退役后仅剩复制模式。

对象级权限(§9 沿用):
- 发起分享 = **属主**(admin 不可代他人分享,§8.1);
- copy = 场景走 copy_scenario(与 handoff 同一深拷贝,跨属主剥内置
  凭证与敏感列)、suite 走单事务深拷贝(成员逐个复制 + forked_from
  三件套,mode_config 重映射)。

引用模式(share_refs)已随 authz M2a S7.4 退役:存量引用经
scripts/retire_share_refs.py 一次性转为被分享人私有副本,迁移 0049
删表。历史时间线事件(scenario/suite.share_ref* / share_fork)照常
展示(useActivityTimeline 文案保留)。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.composer_scenario import ComposerScenario
from ..models.suite import Suite
from ..models.user import User
from ..schemas.share import ShareCopyOut, ShareCreateIn
from ..services.suite_copy import deep_copy_suite
from ..services import notifications as notify_svc
from ..services import scenario_store

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/shares", tags=["shares"])


async def _load_grantee(db, grantee_id: int, sharer_id: int) -> User:
    """接收人校验(§7.7):活跃、非本人。"""
    target = (await db.execute(
        select(User).where(User.id == grantee_id))).scalar_one_or_none()
    if target is None or not target.is_active:
        raise HTTPException(422, "target_user_invalid")
    if target.id == sharer_id:
        raise HTTPException(422, "target_self")
    return target


async def _record_share_event(db, *, actor_id, kind, resource_type,
                              resource_id, detail) -> None:
    """activity_events:全部分享事件(§10;副本历史只存在这里)。"""
    from ..services import activity as activity_svc
    await activity_svc.record(
        db, actor_id=actor_id, kind=kind,
        resource_type=resource_type, resource_id=resource_id,
        detail=detail, coalesce=False)


@router.post("", response_model=ShareCopyOut, status_code=201)
async def create_share(
    user: CurrentUser, db: DbSession, body: ShareCreateIn,
) -> ShareCopyOut:
    """副本分享(原 copy 分支原样;ref 模式已随 S7.4 退役)。"""
    sharer_disp = user.display_name or user.username

    if body.resourceType == "scenario":
        row = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == body.resourceId))
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "scenario_not_found")
        # §8.1:发起分享 = 属主;admin 无豁免(防 admin 借分享转内容)
        if user.id != row.owner_id:
            raise HTTPException(403, "not_owner")
        target = await _load_grantee(db, body.granteeUserId, user.id)
        resolved, _ = await scenario_store.resolve_name_conflict(
            db, target.id, row.name or row.scenario_id)
        out = await scenario_store.copy_scenario(
            db, row.scenario_id,
            new_owner=target.display_name or target.username,
            new_owner_id=target.id, new_name=resolved,
            activity_kind="scenario.share_copy",
            activity_detail={"senderId": user.id,
                             "senderName": sharer_disp},
            origin_id=row.scenario_id,
            origin_owner_name=row.owner_name or "")
        await _notify(db, target.id, "resource_handoff",
                     f"收到副本:{out.meta.name}",
                     f"{sharer_disp} 拷贝分享了场景「{row.name or row.scenario_id}」给你",
                     link=f"/scenarios/{out.meta.scenario_id}/detail",
                     resource_id=out.meta.scenario_id,
                     payload={"sender_name": sharer_disp})
        await _record_share_event(
            db, actor_id=user.id, kind="scenario.share_copy",
            resource_type="scenario", resource_id=row.scenario_id,
            detail={"granteeId": target.id, "copyId": out.meta.scenario_id})
        return ShareCopyOut(mode="copy", scenarioId=out.meta.scenario_id)

    # suite
    suite = (await db.execute(select(Suite).where(
        Suite.id == int(body.resourceId)))).scalar_one_or_none()
    if suite is None:
        raise HTTPException(404, "suite_not_found")
    if user.id != suite.owner_id:
        raise HTTPException(403, "not_owner")
    if (suite.mode_config or {}).get("draft"):
        raise HTTPException(409, {
            "code": "suite_is_draft",
            "message": "草稿不可分享(完成编排后可分享)"})
    target = await _load_grantee(db, body.granteeUserId, user.id)
    out = await deep_copy_suite(db, suite, target, sharer_disp)
    await _notify(db, target.id, "resource_handoff",
                 f"收到副本:{out['name']}",
                 f"{sharer_disp} 拷贝分享了 Suite「{suite.name}」给你({out['count']} 个成员)",
                 link=f"/suites/{out['suiteId']}",
                 resource_id=str(out["suiteId"]),
                 payload={"sender_name": sharer_disp})
    await _record_share_event(
        db, actor_id=user.id, kind="suite.share_copy",
        resource_type="suite", resource_id=str(suite.id),
        detail={"granteeId": target.id, "copyId": out["suiteId"]})
    return ShareCopyOut(mode="copy", suiteId=out["suiteId"],
                        suiteName=out["name"], memberCount=out["count"])


# ── 内部 ──────────────────────────────────────────────────────────

async def _notify(db, user_id: int, type_: str, title: str, body: str,
                  link: str | None = None, resource_id: str | None = None,
                  resource_type: str = "scenario",
                  payload: dict | None = None) -> None:
    """通知 best-effort(§10;失败 rollback+记日志,不阻断业务)。

    ``payload``:resource_handoff 必带 ``sender_name`` —— handoff-unread
    端点(悬浮标签数据源)读的就是这个键,缺失 = 标签永不显示。"""
    from loguru import logger
    try:
        await notify_svc.create_notification(
            db, user_id=user_id, type_=type_, title=title, body=body,
            link=link, resource_type=resource_type, resource_id=resource_id,
            payload=payload, commit=True)
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.warning("shares: notify {} failed: {}", type_, e)
