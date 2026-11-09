"""GET /api/me/summary — 工作台身份卡一次取数(webhook v4 §5.3/P3)。

身份卡(D17)按 ``identity.card`` 偏好渲染:常驻统计(≤ 4)、告警
(按类开关,最多显示 3 条)、快捷入口(纯前端路由,无服务端数据)。
本端点把统计与告警一次取回,前端按偏好挑选 —— 不为每个小数字各开
一个端点。

``items`` = 统计 id 白名单(缺省全部);告警恒随行返回(前端按开关
过滤)。统计 id 是前端注册表口径,后端只产出自己算得出的项。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.access_token import AccessToken
from ..models.auth_session import AuthSession
from ..models.composer_scenario import ComposerScenario
from ..models.execution import Execution
from ..models.integration_task import IntegrationTask
from ..models.permission import Notification
from ..services import access_token as at_svc

router = APIRouter(prefix="/me", tags=["me"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

#: 告警即将到期窗口(§5.1/D17 口径:7 天内到期)
EXPIRING_WINDOW_DAYS = 7


async def _stat_private_scenarios(db, user) -> int:
    return int((await db.execute(select(func.count()).select_from(
        ComposerScenario).where(
            ComposerScenario.owner_id == user.id,
            ComposerScenario.project_id.is_(None)))).scalar_one())


async def _stat_follows(db, user) -> int:
    from ..models.permission import UserStar
    return int((await db.execute(select(func.count()).select_from(
        UserStar).where(UserStar.user_id == user.id))).scalar_one())


async def _stat_tokens(db, user) -> int:
    return int((await db.execute(select(func.count()).select_from(
        AccessToken).where(
            AccessToken.user_id == user.id,
            AccessToken.kind == at_svc.PERSONAL_KIND,
            AccessToken.revoked_at.is_(None)))).scalar_one())


async def _stat_today_failed(db, user, *, since) -> int:
    return int((await db.execute(select(func.count()).select_from(
        Execution).where(
            Execution.owner_id == user.id,
            Execution.status == "failed",
            Execution.created_at >= since))).scalar_one())


async def _stat_subscribed_integrations(db, user) -> int:
    return int((await db.execute(select(func.count()).select_from(
        IntegrationTask).where(
            IntegrationTask.template_id.is_not(None),
            IntegrationTask.holder_id == user.id))).scalar_one())


async def _stat_auths(db, user) -> int:
    return int((await db.execute(select(func.count()).select_from(
        AuthSession).where(AuthSession.owner_id == user.id))).scalar_one())


async def _stat_unread(db, user) -> int:
    return int((await db.execute(select(func.count()).select_from(
        Notification).where(
            Notification.user_id == user.id,
            Notification.read_at.is_(None)))).scalar_one())


@router.get("/summary")
async def me_summary(
    user: CurrentUser, db: DbSession,
    items: Annotated[list[str] | None, Query(max_length=16)] = None,
) -> dict:
    """身份卡统计与告警(§5.3)。``items`` 过滤统计项;告警恒返回。

    告警按类聚合(前端按 ``identity.card.alerts`` 开关过滤、按严重度
    排序取前 3):``token_invalidated`` / ``integration_paused`` /
    ``token_expiring`` / ``execution_failures``。"""
    from ..core.timeutil import ensure_aware
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    today_start = (now - timedelta(
        hours=now.hour, minutes=now.minute, seconds=now.second,
        microseconds=now.microsecond))
    window24 = now - timedelta(hours=24)

    makers = {
        "private_scenarios": lambda: _stat_private_scenarios(db, user),
        "follows": lambda: _stat_follows(db, user),
        "tokens": lambda: _stat_tokens(db, user),
        "today_failed": lambda: _stat_today_failed(
            db, user, since=today_start),
        "subscribed_integrations": lambda: _stat_subscribed_integrations(
            db, user),
        "auths": lambda: _stat_auths(db, user),
        "unread": lambda: _stat_unread(db, user),
    }
    wanted = set(items) if items else set(makers)
    stats: dict[str, int] = {}
    for key in wanted:
        maker = makers.get(key)
        if maker is not None:
            stats[key] = await maker()

    alerts: list[dict] = []

    # ── 访问令牌失效(error)──────────────────────────────────────
    invalidated = (await db.execute(select(AccessToken).where(
        AccessToken.user_id == user.id,
        AccessToken.kind == at_svc.PERSONAL_KIND,
        AccessToken.invalidated_at.is_not(None),
        AccessToken.revoked_at.is_(None)))).scalars().all()
    for tok in invalidated:
        paused_n = 0
        if tok.kind == at_svc.PERSONAL_KIND:
            paused_n = int((await db.execute(select(func.count())
                .select_from(IntegrationTask).where(
                    IntegrationTask.template_id.is_not(None),
                    IntegrationTask.state == "paused",
                    IntegrationTask.paused_reason.in_(
                        (at_svc.PAUSE_TOKEN_INVALIDATED,)),
                    IntegrationTask.template_id.in_(select(
                        IntegrationTask.id).where(
                        IntegrationTask.template_id.is_(None),
                        IntegrationTask.token_id == tok.id)),
                ))).scalar_one())
        reason_label = {"password": "改密失效", "deactivated": "停用失效",
                        "admin": "管理员强制失效"}.get(
                            tok.invalidated_reason or "", "已失效")
        title = f"{tok.name} {reason_label}"
        if paused_n:
            title += f" · {paused_n} 个任务已暂停"
        alerts.append({
            "id": f"token_invalidated:{tok.id}",
            "class": "token_invalidated", "severity": "error",
            "title": title, "action": "重新生成",
            "link": "/profile#tokens"})

    # ── 集成任务暂停(error;token/范围类成因)────────────────────
    # 注意先 await execute 再 .scalars():写成 `await db.execute(...).scalars()`
    # 会把整条链一起 await(对 coroutine 调 .scalars → 500,2026-11-05 修复)
    # 2026-11-05 评审 P2-7:告警直接深链到集成详情页(此前统一跳列表页),
    # 并补上凭证认证失败(auth_failed)。详情页路由参数是模板 id(GET
    # /integration/tasks/{id} 对实例 id 404),链接取 inst.template_id
    # 而非 inst.id(2026-11-05 修复轮评审 N2)。authz C1:平台模板暂停对
    # admin+ 全员可见的并集分支随平台模式退役 —— 恒按本人持有过滤。
    _paused_rows = await db.execute(select(IntegrationTask).where(
        IntegrationTask.state == "paused",
        IntegrationTask.holder_id == user.id))
    paused_insts = _paused_rows.scalars().all()
    task_alert_reasons = (
        at_svc.PAUSE_TOKEN_REVOKED, at_svc.PAUSE_TOKEN_INVALIDATED,
        at_svc.PAUSE_TOKEN_EXPIRED,
        at_svc.PAUSE_RESOURCE_NOT_ALLOWED, at_svc.PAUSE_SCOPE_DENIED,
        "missing_credential", "fail_streak", "auth_failed")
    reason_labels = {
        at_svc.PAUSE_TOKEN_REVOKED: "令牌已吊销",
        at_svc.PAUSE_TOKEN_INVALIDATED: "令牌已失效",
        at_svc.PAUSE_TOKEN_EXPIRED: "令牌已到期",
        at_svc.PAUSE_RESOURCE_NOT_ALLOWED: "超出令牌范围",
        at_svc.PAUSE_SCOPE_DENIED: "场景非公共",
        "missing_credential": "缺少凭证",
        "fail_streak": "连续失败",
        "auth_failed": "凭证认证失败",
    }
    for inst in paused_insts:
        if inst.paused_reason not in task_alert_reasons:
            continue
        tpl = await db.get(IntegrationTask, inst.template_id)
        name = tpl.name if tpl is not None else f"#{inst.template_id}"
        alerts.append({
            "id": f"integration_paused:{inst.id}",
            "class": "integration_paused", "severity": "error",
            "title": f"{name} {reason_labels.get(inst.paused_reason,
                                                  '已暂停')}",
            "action": "查看", "link": f"/integrations/{inst.template_id}"})

    # ── 访问令牌即将到期(warn;7 天内)──────────────────────────
    expiring = (await db.execute(select(AccessToken).where(
        AccessToken.user_id == user.id,
        AccessToken.kind == at_svc.PERSONAL_KIND,
        AccessToken.revoked_at.is_(None),
        AccessToken.invalidated_at.is_(None),
        AccessToken.expires_at <= now + timedelta(
            days=EXPIRING_WINDOW_DAYS)))).scalars().all()
    for tok in expiring:
        days = max(0, (ensure_aware(tok.expires_at) - now).days)
        alerts.append({
            "id": f"token_expiring:{tok.id}",
            "class": "token_expiring", "severity": "warn",
            "title": f"{tok.name} {days} 天后到期",
            "action": "续期", "link": "/profile#tokens"})

    # ── 近 24 小时执行失败(warn)────────────────────────────────
    failed24 = int((await db.execute(select(func.count()).select_from(
        Execution).where(
            Execution.owner_id == user.id,
            Execution.status == "failed",
            Execution.created_at >= window24))).scalar_one())
    if failed24:
        alerts.append({
            "id": "execution_failures", "class": "execution_failures",
            "severity": "warn",
            "title": f"近 24 小时 {failed24} 次执行失败",
            "action": "查看", "link": "/executions?status=failed"})

    severity_rank = {"error": 0, "warn": 1, "info": 2}
    alerts.sort(key=lambda a: severity_rank.get(a["severity"], 9))
    return {"stats": stats, "alerts": alerts}
