"""GET /api/webhook-deliveries — 回调投递排查面(webhook 设计 v3 P2-6)。

按 ``executionId`` / ``instanceId`` / ``aliasName`` 过滤投递行(status /
attempts / lastError / body),供调用方与别名属主排查「回调发了没、
为什么没收到」。

可见性(与执行的 D8 口径对齐;不可见与不存在同样 404,不泄露):
admin 全量;入站凭证只看本别名;JWT 用户 = 目标执行/实例的 owner,
或目标 caller 别名的属主(``aliasName`` 直查时要求别名属主/admin)。
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
from ..models.execution import Execution
from ..models.integration_task import IntegrationTask
from ..models.service_alias import ServiceAlias
from ..models.webhook_delivery import WebhookDelivery
from ..services.inbound_identity import Principal

router = APIRouter(prefix="/webhook-deliveries", tags=["webhook-deliveries"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
PrincipalIn = Annotated[Principal, Depends(principal_or_user)]


def _row_out(r: WebhookDelivery) -> dict:
    return {
        "id": r.id, "aliasName": r.alias_name, "eventType": r.event_type,
        "executionId": r.execution_id, "instanceId": r.instance_id,
        "url": r.url, "status": r.status, "attempts": r.attempts,
        "lastError": r.last_error, "nextRetryAt": iso_utc_z(r.next_retry_at),
        "deliveredAt": iso_utc_z(r.delivered_at), "createdAt": iso_utc_z(r.created_at),
        "body": r.body,
    }


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": "deliveries not found"})


@router.get("")
async def list_deliveries(
    principal: PrincipalIn, db: DbSession,
    execution_id: Annotated[int | None, Query(
        alias="executionId", ge=1)] = None,
    instance_id: Annotated[int | None, Query(
        alias="instanceId", ge=1)] = None,
    alias_name: Annotated[str | None, Query(
        alias="aliasName", max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    user = principal.user
    if execution_id is None and instance_id is None and alias_name is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "filter_required",
                    "message": "executionId / instanceId / aliasName "
                               "至少提供一个"})
    # 目标 caller 别名:执行/实例行携带的 caller_alias_name(覆盖
    # aliasName 入参 —— 行级权限跟着目标走,不跟着请求参数走)。
    target_alias = alias_name
    allowed = user.role == "admin"
    if execution_id is not None:
        ex = await db.get(Execution, execution_id)
        if ex is not None:
            target_alias = ex.caller_alias_name
            allowed = allowed or ex.owner_id == user.id
    if instance_id is not None:
        inst = await db.get(IntegrationTask, instance_id)
        if inst is not None and inst.template_id is not None:
            tpl = await db.get(IntegrationTask, inst.template_id)
            if tpl is not None:
                target_alias = tpl.caller_alias_name
                allowed = allowed or tpl.owner_id == user.id
    if getattr(principal, "inbound", False):
        # 入站凭证(§5.6):只能看本别名的投递行
        if target_alias != principal.caller_alias:
            raise _not_found()
    elif not allowed:
        # JWT 非 admin:目标 caller 别名的属主才可见(团队共享别名只归
        # admin)。目标行不存在/无 caller → 同样 404。
        if target_alias:
            alias = await db.get(ServiceAlias, target_alias)
            allowed = (alias is not None
                       and alias.owner_user_id == user.id)
        if not allowed:
            raise _not_found()

    q = select(WebhookDelivery).where(
        WebhookDelivery.alias_name == target_alias)
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
    """人工补发(收尾评审 2026-11-02 G5):按 ``failed`` / ``delivered``
    的投递行**新建一行** pending(同 alias / event / execution / instance /
    url;body 同内容但 ``deliveryId`` 改为新行 id、附 ``redeliveredFrom``),
    交回投递循环重发;原行原样保留为历史。

    为什么不是原地重置:接收端以 ``X-Gimbal-Delivery``(= 行 id)去重
    (§4.3),同 id 重发会被正确实现的接收端当重复丢弃 —— 补发必须换
    新 id。body 里的 ``deliveryId`` 必须跟着换:按 body 去重的接收端
    否则同样把补发当重复丢掉,而补发恰是接收端故障恢复后才用的。
    签名按当前别名密钥现取。

    谁能点:admin,或该行 caller 别名的**属主**(JWT);入站凭证与其他
    用户一律 404(不泄露)。``pending`` 行(在飞 / 等待退避)409
    ``already_pending`` —— 它本来就会发。
    """
    from ..services import webhook_outbox

    user = principal.user
    row = await db.get(WebhookDelivery, delivery_id)
    if row is None or getattr(principal, "inbound", False):
        raise _not_found()
    if user.role != "admin":
        alias = await db.get(ServiceAlias, row.alias_name)
        if alias is None or alias.owner_user_id != user.id:
            raise _not_found()
    if row.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "already_pending",
                    "message": "该投递仍在队列中,无需补发"})
    fresh = WebhookDelivery(
        alias_name=row.alias_name, event_type=row.event_type,
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
    await db.commit()
    await db.refresh(fresh)
    webhook_outbox.wake()
    return {**_row_out(fresh), "redeliveredFrom": row.id}
