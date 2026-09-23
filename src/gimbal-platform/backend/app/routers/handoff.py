"""资源分发(2026-09-23 批次 F1)—— 分发 = Fork(副本),不是授权。

POST /api/handoff:资源 owner(或 admin 代理,§1.8.2)把场景深拷贝一份
给目标用户。语义定稿:接收后归接收方、发送方零控制权、不支持撤回、
凭据引用不迁移(接收方按本人池解析,§1.8.1)。

落账三件:notifications(resource_handoff,悬浮标签数据源)+
activity_events(scenario.handoff_received,actor=接收方);**不写
audit_logs**(评审拍板:维持特权写口径,双写已够,见方案 §1.5)。
重名走 resolve_name_conflict(静默计数后缀,name 上限 64 先截断)。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models import User
from ..models.composer_scenario import ComposerScenario
from ..services import notifications as notify_svc, scenario_store
from ..services.activity import KIND_HANDOFF
from ._error_mapping import key_error_404, value_error_http

router = APIRouter(prefix="/handoff", tags=["handoff"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class HandoffIn(BaseModel):
    resource_type: str = "scenario"
    resource_id: str = Field(min_length=3, max_length=128)
    target_user_id: int


class HandoffOut(BaseModel):
    status: str = "ok"
    new_resource_id: str
    new_name: str
    renamed: bool


@router.post("", response_model=HandoffOut)
async def handoff_resource(
    user: CurrentUser, db: DbSession, body: HandoffIn
) -> HandoffOut:
    if body.resource_type != "scenario":
        raise HTTPException(
            422, "resource_type_unsupported: only 'scenario' in P1")

    row = (await db.execute(
        select(ComposerScenario).where(
            ComposerScenario.scenario_id == body.resource_id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "resource_not_found")
    # 鉴权:owner 或 admin 代理(§1.8.2)
    if user.role != "admin" and row.owner_id != user.id:
        raise HTTPException(403, "not_resource_owner")

    target = (await db.execute(
        select(User).where(User.id == body.target_user_id)
    )).scalar_one_or_none()
    if target is None or not target.is_active:
        raise HTTPException(422, "target_user_invalid")
    if target.id == user.id:
        raise HTTPException(422, "target_self")

    current_name = row.name or row.scenario_id
    resolved, renamed = await scenario_store.resolve_name_conflict(
        db, target.id, current_name)
    sender_disp = user.display_name or user.username

    try:
        out = await scenario_store.copy_scenario(
            db,
            body.resource_id,
            new_owner=target.display_name or target.username,
            new_owner_id=target.id,
            new_name=resolved,
            activity_kind=KIND_HANDOFF,
            activity_detail={
                "senderId": user.id, "senderName": sender_disp},
        )
    except KeyError as e:
        raise key_error_404(e)
    except ValueError as e:
        raise value_error_http(e, {"scenario_id_exists": 409})

    # 通知(悬浮标签数据源):失败不阻断分发结果(通知是增强,不是
    # 前置条件;关闭「收到分享」类型的用户 = 同时放弃悬浮标签),但
    # 必须 rollback + 记日志 —— 静默吞掉会让副本已建、通知没到的
    # 排障无从下手(与 activity.record 同款口径)。
    try:
        await notify_svc.create_notification(
            db,
            user_id=target.id,
            type_="resource_handoff",
            title=f"收到分享:{out.meta.name}",
            body=f"{sender_disp} 分享了场景「{current_name}」给你",
            link=f"/scenarios/{out.meta.scenario_id}/detail",
            resource_type="scenario",
            resource_id=out.meta.scenario_id,
            payload={
                "sender_id": user.id,
                "sender_name": sender_disp,
                "original_name": current_name,
            },
        )
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.warning(
            "handoff: notification for user {} scenario {} failed: {}",
            target.id, out.meta.scenario_id, e)

    return HandoffOut(
        new_resource_id=out.meta.scenario_id,
        new_name=out.meta.name,
        renamed=renamed,
    )
