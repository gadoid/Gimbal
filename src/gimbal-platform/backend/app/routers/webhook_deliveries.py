"""GET /api/webhook-deliveries — 回调投递排查面(webhook v4 §5.2)。

按 ``executionId`` / ``instanceId`` / ``tokenId`` 过滤投递行(status /
attempts / lastError / body),供令牌属主与 member+ 排查「回调发了没、
为什么没收到」。

可见性(§2.3 矩阵;不可见与不存在同样 404,不泄露):

* 令牌路径:只列本令牌的投递;**不能补发**(补发只走 JWT);
* JWT 列表:admin、执行属主、模板属主、个人令牌属主;平台身份
  (投递目标为平台令牌)member+;
* JWT 补发:admin、个人令牌属主;平台身份 member+。

body 含脱敏后的 outputs,可见面已按属主收窄,可随行返回。
"""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import principal_or_user
from ..core.timeutil import iso_utc_z
from ..models.access_token import AccessToken
from ..models.execution import Execution
from ..models.integration_task import IntegrationTask
from ..models.webhook_delivery import WebhookDelivery
from ..services.access_token import Principal

router = APIRouter(prefix="/webhook-deliveries", tags=["webhook-deliveries"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
PrincipalIn = Annotated[Principal, Depends(principal_or_user)]


def _row_out(r: WebhookDelivery) -> dict:
    return {
        "id": r.id, "tokenId": r.token_id, "tokenName": r.token_name,
        "eventType": r.event_type,
        "executionId": r.execution_id, "instanceId": r.instance_id,
        "url": r.url, "status": r.status, "attempts": r.attempts,
        "lastError": r.last_error, "nextRetryAt": iso_utc_z(r.next_retry_at),
        "deliveredAt": iso_utc_z(r.delivered_at),
        "createdAt": iso_utc_z(r.created_at),
        "body": r.body,
    }


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": "deliveries not found"})


async def _target_token_of(
    db: AsyncSession, execution_id: int | None, instance_id: int | None,
    token_id: int | None,
) -> "AccessToken | None":
    """行级权限跟着目标走,不跟着请求参数走:优先取执行/实例行携带的
    token_id;直接按 tokenId 查时校验调用方对该令牌的可见性。"""
    if execution_id is not None:
        ex = await db.get(Execution, execution_id)
        if ex is not None and ex.token_id is not None:
            return await db.get(AccessToken, ex.token_id)
    if instance_id is not None:
        inst = await db.get(IntegrationTask, instance_id)
        if inst is not None and inst.template_id is not None:
            tpl = await db.get(IntegrationTask, inst.template_id)
            if tpl is not None and tpl.token_id is not None:
                return await db.get(AccessToken, tpl.token_id)
    if token_id is not None:
        return await db.get(AccessToken, token_id)
    return None


def _may_view_token(user, tok: "AccessToken | None") -> bool:
    """JWT 面对目标令牌的可见性:个人令牌属主 / 平台令牌 admin+
    (authz W4:越属主旁路删除,判定单点 = services.access_token.can_view)。"""
    from ..services.access_token import can_view
    return tok is not None and can_view(user, tok)


@router.get("")
async def list_deliveries(
    principal: PrincipalIn, db: DbSession,
    execution_id: Annotated[int | None, Query(
        alias="executionId", ge=1)] = None,
    instance_id: Annotated[int | None, Query(
        alias="instanceId", ge=1)] = None,
    token_id: Annotated[int | None, Query(
        alias="tokenId", ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    user = principal.user
    if execution_id is None and instance_id is None and token_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "filter_required",
                    "message": "executionId / instanceId / tokenId "
                               "至少提供一个"})
    if getattr(principal, "is_token", False):
        # 令牌路径(§2.2):只看本令牌的投递行
        target = await _target_token_of(
            db, execution_id, instance_id, principal.token_id)
        if target is None or target.id != principal.token_id:
            raise _not_found()
        target_id = principal.token_id
    else:
        target = await _target_token_of(db, execution_id, instance_id,
                                        token_id)
        if target is None:
            # 目标行不存在 / 目标非令牌发起(JWT 执行无投递)→ 404
            raise _not_found()
        # authz W4:super_admin 越属主旁路删除 —— 只认 _may_view_token
        # (本人令牌 ∨ 平台令牌,平台面 C1 退役前维持)
        if not _may_view_token(user, target):
            raise _not_found()
        target_id = target.id

    q = select(WebhookDelivery).where(WebhookDelivery.token_id == target_id)
    if execution_id is not None:
        q = q.where(WebhookDelivery.execution_id == execution_id)
    if instance_id is not None:
        q = q.where(WebhookDelivery.instance_id == instance_id)
    rows = (await db.execute(
        q.order_by(WebhookDelivery.id.desc()).limit(limit))).scalars().all()
    return {"items": [_row_out(r) for r in rows]}


@router.post("/{delivery_id}/redeliver", status_code=status.HTTP_201_CREATED)
async def redeliver(
    delivery_id: int, principal: PrincipalIn, db: DbSession,
) -> dict:
    """人工补发:按 ``failed`` / ``delivered`` 的投递行**新建一行**
    pending(同 token / event / execution / instance / url;body 同内容但
    ``deliveryId`` 改为新行 id、附 ``redeliveredFrom``),交回投递循环
    重发;原行原样保留为历史。

    为什么不是原地重置:接收端以 ``X-Gimbal-Delivery``(= 行 id)去重,
    同 id 重发会被正确实现的接收端当重复丢弃 —— 补发必须换新 id。body
    里的 ``deliveryId`` 必须跟着换。签名按当前令牌密钥现取。

    谁能点(§5.2,authz W4 后):个人令牌属主;平台令牌面 admin+。
    admin 越属主旁路已删;令牌路径与其他用户一律 404(不泄露)。
    ``pending`` 行(在飞/等待退避)409 ``already_pending``。
    """
    from ..services import webhook_outbox

    user = principal.user
    row = await db.get(WebhookDelivery, delivery_id)
    if row is None or getattr(principal, "is_token", False):
        raise _not_found()
    tok = (await db.get(AccessToken, row.token_id)
           if row.token_id is not None else None)
    if not _may_view_token(user, tok):
        raise _not_found()
    if row.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "already_pending",
                    "message": "该投递仍在队列中,无需补发"})
    fresh = WebhookDelivery(
        token_id=row.token_id, token_name=row.token_name,
        event_type=row.event_type,
        execution_id=row.execution_id, instance_id=row.instance_id,
        url=row.url, body=row.body, status="pending", attempts=0)
    db.add(fresh)
    await db.flush()                      # 先拿新 id,再改写 body
    try:
        payload = json.loads(row.body)
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        payload["deliveryId"] = fresh.id
        payload["redeliveredFrom"] = row.id
        fresh.body = json.dumps(payload, ensure_ascii=False, default=str)
    # 手工干预入审计(resource = access_token,与令牌域同面查看)
    from ..services import audit as audit_svc
    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="webhook.redeliver", resource_type="access_token",
        resource_id=str(row.token_id) if row.token_id is not None else None,
        detail={"delivery": row.id, "new_delivery": fresh.id,
                "event_type": row.event_type,
                "execution": row.execution_id, "instance": row.instance_id,
                "url": row.url})
    await db.commit()
    await db.refresh(fresh)
    webhook_outbox.wake()
    return {**_row_out(fresh), "redeliveredFrom": row.id}
