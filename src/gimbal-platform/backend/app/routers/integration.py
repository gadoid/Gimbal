"""外部系统集成 P1 路由:功能(模板)CRUD + 手动执行 + 批量卡片 +
令牌注册面。

《GIMBAL-外部系统集成架构设计》§9 + webhook v4 §5.2:模板软删(评审
E7);令牌注册的任务按 ``token_id`` 隔离(令牌只能管理本令牌注册的);
JWT 管理者可解绑令牌(D26)。平台模板(属主 ``__platform__``)由 Admin+
维护(``_can_manage``);平台凭证面随 authz C1 退役。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, principal_or_user
from ..models.auth_session import AuthSession
from ..models.composer_scenario import ComposerScenario
from ..models.integration_task import IntegrationTask
from ..models.user import User
from ..services import access_token as at_svc
from ..services import audit as audit_svc
from ..services import integration_runner
from ..services.access_token import Principal
from ..services.cron_expr import CronError, describe_cron, parse_cron
from ..services.run_semantics import working_preview
from ._ownership import has_capability

DbSession = Annotated[AsyncSession, Depends(get_db)]
PrincipalIn = Annotated[Principal, Depends(principal_or_user)]
router = APIRouter(prefix="/integration", tags=["integration"])


def _bad(code: str, message: str, status: int = 422,
         **extra) -> HTTPException:
    return HTTPException(status_code=status,
                         detail={"code": code, "message": message, **extra})


def _iso(dt: datetime | None) -> str | None:
    """UTC naive 归一后再拼 Z(asyncpg 读 timestamptz 回 aware,直接
    isoformat 会产出 "+00:00Z" 双后缀,前端解析失败显示空)。"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"


async def _platform_uid(db: AsyncSession) -> int | None:
    """``__platform__`` 系统用户 id(平台模板的持有者;无则 None)。"""
    return (await db.execute(
        select(User.id).where(User.is_system == True)  # noqa: E712
        .order_by(User.id).limit(1))).scalar()


def _can_manage(user, tpl: IntegrationTask,
                platform_uid: int | None) -> bool:
    """模板改动权(§5.2 改写):属主 ∨ 平台模板 × ops.write。

    平台模板 = 属主为 ``__platform__`` 的公共模板(方案:「由
    __platform__ 持有、Admin+ 维护」,不因创建人离开失去维护者;
    0038 把原平台模板归到 __platform__ 名下)。"""
    if user.id == tpl.owner_id:
        return True
    return (platform_uid is not None and tpl.owner_id == platform_uid
            and has_capability(user, "ops.write"))


def _visible(user, tpl: IntegrationTask) -> bool:
    """模板可见判定(列表/详情/立即执行/关注卡/订阅前置共用):
    属主 ∨ public(authz C1:平台的 admin+ 恒可见分支随平台模式退役)。"""
    return tpl.removed_at is None and (
        tpl.owner_id == user.id or tpl.visibility == "public")


def _token_owns(principal: Principal, tpl: IntegrationTask) -> bool:
    """令牌面的可见/管理判定(§2.2):只认**本令牌**注册的模板,已软删
    的不出;不满足一律 404(不泄露存在性)。``_visible``/``_can_manage``
    对系统用户恒为真,不能用于令牌面。"""
    return (tpl.removed_at is None
            and tpl.token_id is not None
            and tpl.token_id == principal.token_id)


async def _my_instance(db: AsyncSession, tpl: IntegrationTask, user):
    """当前用户的实例(**只读**,W0a① 播种收口):按 holder 查不建。"""
    return (await db.execute(select(IntegrationTask).where(
        IntegrationTask.template_id == tpl.id,
        IntegrationTask.holder_id == user.id))).scalar()


async def _tpl_instance(db: AsyncSession, tpl_id: int,
                       user=None, tpl=None):
    """模板实例:P1 口径 = 平台唯一实例;Y3 起个人模式按当前用户
    定位/创建(订阅即创建,方案 §4)。user/tpl 缺省时维持旧行为。"""
    if user is not None and tpl is not None \
            and tpl.identity_mode == "personal":
        seeded = await integration_runner.ensure_instance(
            tpl, holder_id=user.id)
        return seeded
    return (await db.execute(select(IntegrationTask).where(
            IntegrationTask.template_id == tpl_id,
            IntegrationTask.holder_id.is_not(None),
    ).order_by(IntegrationTask.id))).scalars().first()


async def _managed_instance(
    db: AsyncSession, tpl: IntegrationTask,
) -> IntegrationTask | None:
    """管理动作(解绑 D26 等)的目标实例 —— 注册方(属主)自己的实例
    (评审 2026-11-05 P2:此前取「该模板 id 最小的实例」,只是靠创建
    顺序碰巧正确 —— 订阅者实例先建时暂停会落到别人头上)。authz C1:
    平台唯一实例分支随平台模式退役。"""
    holder = tpl.owner_id
    if holder is None:
        return None
    return (await db.execute(select(IntegrationTask).where(
        IntegrationTask.template_id == tpl.id,
        IntegrationTask.holder_id == holder))).scalar()


def _tpl_out(db_tpl: IntegrationTask, inst: IntegrationTask | None,
             current: User, *, token: Any = None,
             auth_aliases: list[str] | None = None,
             subscribed: bool | None = None) -> dict:
    out = {
        "id": db_tpl.id,
        "name": db_tpl.name,
        "ownerId": db_tpl.owner_id,
        "mine": db_tpl.owner_id == current.id,
        "canManage": db_tpl.owner_id == current.id,
        "visibility": db_tpl.visibility,
        "identityMode": db_tpl.identity_mode,
        "targetType": db_tpl.target_type,
        "scenarioId": db_tpl.scenario_id,
        "suiteId": db_tpl.suite_id,
        "schemeId": db_tpl.scheme_id,
        "targetSystem": db_tpl.target_system,
        "triggerCron": db_tpl.trigger_cron,
        "cronText": describe_cron(db_tpl.trigger_cron),
        "resultPolicy": db_tpl.result_policy,
        "cardTemplate": db_tpl.card_template,
        "removed": db_tpl.removed_at is not None,
        "instance": _inst_out(inst) if inst else None,
    }
    if auth_aliases is not None:
        # W0b④:消费面字段(创建/列表/订阅回显供 W1/W2 前端)
        out["authAliases"] = auth_aliases
    if subscribed is not None:
        out["subscribed"] = subscribed
    # D12:公共模板对非属主隐藏 token/client_ref —— 注册方的集成关系
    # 不外泄;属主/ops.write(平台身份对象面,表 A 驱动)可见。
    if has_capability(current, "ops.write") or db_tpl.owner_id == current.id:
        out["tokenId"] = db_tpl.token_id
        if token is not None:
            out["tokenName"] = token.name
            out["tokenKind"] = token.kind
        out["clientRef"] = db_tpl.client_ref
    return out


async def _missing_credentials(
    db: AsyncSession, aliases: list[str], holder_id: int | None,
) -> list[str]:
    """持有人凭证池中缺失的别名全集(W0b④;S0② 后与执行期暂停判定
    同口径:任一缺失即列)。"""
    if not aliases or holder_id is None:
        return []
    have = set((await db.execute(select(AuthSession.alias).where(
        AuthSession.owner_id == holder_id,
        AuthSession.alias.in_(aliases)))).scalars().all())
    return [a for a in aliases if a not in have]


async def _tpl_out_full(
    db: AsyncSession, tpl: IntegrationTask,
    inst: IntegrationTask | None, user: User,
) -> dict:
    """W0b④ 消费面组装:authAliases / missingCredentials / subscribed。
    missing 的持有人 = 当前查看者(「我缺什么」)。令牌面:tokenId/
    tokenName 一并回显。authz C1:平台持有人口径退役。"""
    from ..models.access_token import AccessToken
    aliases = await integration_runner.auth_aliases_view(db, tpl)
    holder = user.id
    missing = await _missing_credentials(db, aliases, holder)
    subscribed = (inst is not None and inst.holder_id == user.id)
    token = await db.get(AccessToken, tpl.token_id) if tpl.token_id else None
    out = _tpl_out(tpl, inst, user, token=token,
                   auth_aliases=aliases, subscribed=subscribed)
    out["canManage"] = _can_manage(user, tpl, await _platform_uid(db))
    if inst is not None:
        out["instance"] = _inst_out(inst, missing=missing)
    return out


def _inst_out(inst: IntegrationTask | None,
              *, missing: list[str] | None = None) -> dict:
    if inst is None:
        return {"state": "none", "enabled": False,
                "lastRunAt": None, "lastError": "", "pausedReason": "",
                "nextRunAt": None, "failStreak": 0,
                "runStatus": "", "checkStatus": "", "checkMessage": "",
                "checkChangedAt": None, "missingCredentials": []}
    return {
        "state": inst.state,
        "enabled": inst.enabled,
        "runStatus": inst.run_status or "",
        "checkStatus": inst.check_status or "",
        "checkMessage": inst.check_message or "",
        "checkChangedAt": _iso(inst.check_changed_at),
        "lastRunAt": _iso(inst.last_run_at),
        "lastError": inst.last_error,
        "pausedReason": inst.paused_reason,
        "nextRunAt": _iso(inst.next_run_at),
        "failStreak": inst.fail_streak,
        # W0b④:缺失别名全集(与暂停判定同口径 = 任一缺失即列)
        "missingCredentials": missing or [],
    }


# ── 模板 CRUD ───────────────────────────────────────────────────

class TaskIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scenarioId: str = Field(min_length=1, max_length=128)
    schemeId: str | None = None
    # authz W5:默认反转 personal(M1.x 后收窄为仅 personal);
    # Literal 校验防任意串
    # authz C1:平台模式退役 —— 只接受 personal(传 platform → 422)
    identityMode: Literal["personal"] = "personal"
    triggerCron: str = "*/5 * * * *"
    resultPolicy: str = "latest"
    cardTemplate: str = "status"
    visibility: str = "private"
    targetSystem: str = ""
    # 令牌注册面(§2.2);JWT 调用可带但无回调语义
    clientRef: str | None = Field(default=None, max_length=128)
    callbackPath: str | None = Field(default=None, max_length=256)


class TaskPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    schemeId: str | None = None
    triggerCron: str | None = None
    resultPolicy: str | None = None
    visibility: str | None = None
    targetSystem: str | None = None
    # JWT 管理者解绑令牌(D26):显式 null = 解绑;令牌路径不能解绑。
    # ``tokenId`` 其他取值一律 422(绑定关系只在创建时定)。
    tokenId: int | None = None
    clientRef: str | None = Field(default=None, max_length=128)
    callbackPath: str | None = Field(default=None, max_length=256)


@router.get("/tasks")
async def list_tasks(principal: PrincipalIn, db: DbSession) -> dict:
    """可见模板:我的 + 公共(admin 全见);软删的不出。令牌
    (§2.2):只回本令牌注册的模板。

    P3.2(已知欠账,暂记不修):每行算 authAliases / missingCredentials
    要单独装载场景 + 方案并查凭证池(N+1);当前数据量小可接受,
    行数上去后按「场景/方案批量取 + 凭证池一次查」批量化。"""
    user = principal.user
    q = select(IntegrationTask).where(
        IntegrationTask.template_id.is_(None),
        IntegrationTask.removed_at.is_(None),
    )
    if principal.is_token:
        q = q.where(IntegrationTask.token_id == principal.token_id)
    rows = (await db.execute(q.order_by(IntegrationTask.id.desc()))).scalars().all()
    out = []
    for t in rows:
        if not principal.is_token and not _visible(user, t):
            continue
        inst = await _my_instance(db, t, user)   # W0a①:列表只读不播种
        out.append(await _tpl_out_full(db, t, inst, user))
    return {"items": out}


@router.post("/tasks", status_code=201)
async def create_task(body: TaskIn, principal: PrincipalIn,
                      db: DbSession) -> dict:
    user = principal.user
    # §2.2:令牌调用的 identityMode 由认证结果决定(personal → 属主);
    # 请求体传入不同值 → 422。authz C1:platform 取值随 TaskIn 的
    # Literal 收敛直接 422(W5 的 410 platform_mode_closed 退役)。
    if principal.is_token:
        if body.identityMode != principal.identity_mode:
            raise _bad(
                "identity_mode_conflict",
                f"identityMode 由认证结果决定为 {principal.identity_mode}"
                f"(请求体传了 {body.identityMode})")
    if body.callbackPath is not None \
            and not at_svc.valid_callback_path(body.callbackPath):
        raise _bad(
            "callback_path_invalid",
            "callbackPath 必须是以 / 开头的路径段(不含协议与主机)")
    try:
        parse_cron(body.triggerCron)
    except CronError as e:
        raise _bad("cron_invalid", str(e)) from None
    if body.resultPolicy not in ("latest", "on_change"):
        raise _bad("result_policy_invalid", "resultPolicy ∈ latest | on_change")
    if body.visibility not in ("private", "public"):
        raise _bad("visibility_invalid", "visibility ∈ private | public")
    scen = (await db.execute(select(ComposerScenario).where(
        ComposerScenario.scenario_id == body.scenarioId))).scalar()
    if scen is None:
        raise _bad("scenario_not_found", f"场景不存在: {body.scenarioId}", 404)
    if scen.owner_id != user.id:
        # §4.3:个人模式(含 JWT/个人令牌属主)要求场景属主。
        raise _bad("scenario_not_owned", "只能引用自己创建的场景")
    # S0①(个人侧方案 G-A):方案必须属于该场景(run_precheck 同款
    # 场景限定)。
    if body.schemeId:
        from ..services import scheme_store
        try:
            await scheme_store.get_row(db, scen.scenario_id, body.schemeId)
        except KeyError:
            raise _bad(
                "scheme_not_owned",
                f"执行方案不存在或不属于该场景: {body.schemeId}") from None
    if principal.is_token:
        # 令牌注册范围闸(§5.4:注册 422;按将生效的方案核对,未指定
        # → 运行期同源回落默认/首个)
        await _require_token_scope(db, principal, scen, body.schemeId)
    tpl = IntegrationTask(
        name=body.name, owner_id=user.id, visibility=body.visibility,
        identity_mode=body.identityMode, target_type="scenario",
        scenario_id=body.scenarioId, scheme_id=body.schemeId,
        target_system=body.targetSystem or "", trigger_cron=body.triggerCron,
        result_policy=body.resultPolicy, card_template=body.cardTemplate,
        updated_by=user.id,
        # 令牌注册台账(§3.3;只落模板行):JWT 注册恒 None → 不回调;
        # 公共化不剥离 —— 仅注册方自己的实例写回调投递行
        token_id=principal.token_id if principal.is_token else None,
        client_ref=body.clientRef,
        callback_path_override=body.callbackPath)
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    inst = await integration_runner.ensure_instance(
        tpl, holder_id=user.id)
    if inst is not None:
        # W0a③:owner 实例留底内容指纹(执行闸只对非 owner 生效);
        # 别名查询失败不阻断创建(owner 无闸,best-effort)
        try:
            inst2 = await db.get(IntegrationTask, inst.id)
            await integration_runner.refresh_consent(db, tpl, scen, inst2)
            await db.commit()
        except Exception:  # noqa: BLE001
            await db.rollback()
    await audit_svc.record_inbound(db, principal, "inbound.task.write", detail={
        "fn": "create", "task": tpl.id, "name": tpl.name,
        "scenario_id": tpl.scenario_id, "client_ref": tpl.client_ref,
        "identity_mode": body.identityMode})
    return await _tpl_out_full(db, tpl, inst, user)


async def _scheme_payload_for(
    db: AsyncSession, scen: ComposerScenario, scheme_id: str | None,
) -> dict | None:
    """注册/保存面**将生效**的方案体:指定 → 必须属该场景(否则 422
    ``scheme_not_owned``,与创建闸同码);未指定/清除 → 运行期同源
    回落(``resolve_for_run`` 默认/首个)—— 保存闸按生效配方核对,
    不能只看调用方传了什么。"""
    from ..services import scheme_store
    if scheme_id:
        try:
            row = await scheme_store.get_row(db, scen.scenario_id, scheme_id)
        except KeyError:
            raise _bad(
                "scheme_not_owned",
                f"执行方案不存在或不属于该场景: {scheme_id}") from None
        return row.payload or {}
    row = await scheme_store.resolve_for_run(db, scen.scenario_id, None)
    return (row.payload or {}) if row is not None else None


async def _require_token_scope(
    db: AsyncSession, principal: Principal, scen: ComposerScenario,
    scheme_id: str | None,
) -> None:
    """令牌注册/保存的范围闸(§5.4 状态码约定:注册与保存 422)。

    §3.2 单一实现(``used_sets_for_definition``),与 runs ⑤ /
    ``run_precheck`` / 定时复核 #6 同口径;运行期 #6 仍兜底(范围
    行之后被收紧的窗口)。"""
    from ..services.scenario_store import definition_from_payload
    scheme_payload = await _scheme_payload_for(db, scen, scheme_id)
    bindings = dict((scheme_payload or {}).get("serviceBindings") or {})
    used = await at_svc.used_sets_for_definition(
        db, definition_from_payload(scen.payload), bindings)
    missing = await at_svc.check_scope(
        db, principal.token, principal.user.id, used)
    if missing:
        raise _bad(
            at_svc.ERR_RESOURCE_NOT_ALLOWED,
            "超出令牌授权范围:" + at_svc._missing_summary(missing)
            + ";" + at_svc.missing_hint(missing),
            missing=[{"kind": m.kind, "name": m.name, "deleted": m.deleted}
                     for m in missing])


@router.get("/tasks/{task_id}")
async def get_task(task_id: int, principal: PrincipalIn, db: DbSession) -> dict:
    user = principal.user
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None or tpl.template_id is not None or not (
            _token_owns(principal, tpl) if principal.is_token
            else _visible(user, tpl)):
        raise _bad("not_found", "功能不存在", 404)
    inst = await _my_instance(db, tpl, user)   # W0a①:详情只读不播种
    return await _tpl_out_full(db, tpl, inst, user)


@router.patch("/tasks/{task_id}")
async def patch_task(
    task_id: int, body: TaskPatch, principal: PrincipalIn, db: DbSession,
) -> dict:
    user = principal.user
    if body.callbackPath is not None \
            and not at_svc.valid_callback_path(body.callbackPath):
        raise _bad(
            "callback_path_invalid",
            "callbackPath 必须是以 / 开头的路径段(不含协议与主机)")
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None or tpl.template_id is not None or tpl.removed_at is not None:
        raise _bad("not_found", "功能不存在", 404)
    if principal.is_token:
        # 令牌面(§2.2):只能改本令牌注册的任务;不满足 → 404。
        # 令牌不能解绑自己(D26:解绑 = 转 JWT 管理)。
        if not _token_owns(principal, tpl):
            raise _bad("not_found", "功能不存在", 404)
        if "tokenId" in body.model_fields_set:
            raise _bad(
                "token_unbind_not_allowed",
                "令牌路径不能解绑任务;解绑请由 JWT 管理者在集成详情操作",
                403)
    else:
        plat_uid = await _platform_uid(db)
        if not _can_manage(user, tpl, plat_uid):
            raise _bad("forbidden", "只有模板属主(平台模板:Admin+)"
                         "能修改", 403)
        if (body.visibility == "private" and plat_uid is not None
                and tpl.owner_id == plat_uid):
            raise _bad("platform_template_public",
                       "平台模板恒为公共,不能转私有(不再需要可删除)",
                       409)
        if "tokenId" in body.model_fields_set:
            # D26 解绑:token_id 置空、停回调、按 §3.6 实例暂停规则处置
            # (钩子不再拉起,之后手动启动;平台任务仍受 #5 与只读闸)。
            # token_*/resource_not_allowed 暂停同样改 manual —— 否则
            # 恢复接口 409 提示「先解绑」,解绑后仍 409,死循环
            # (评审 2026-11-05 P0)。
            if body.tokenId is not None:
                raise _bad(
                    "token_rebind_not_allowed",
                    "tokenId 只能解绑(传 null);绑定关系在创建时确定")
            if tpl.token_id is None:
                raise _bad("token_not_bound", "该任务未绑定令牌", 409)
            unbind_token_id = tpl.token_id
            tpl.token_id = None
            tpl.callback_path_override = None
            # 目标实例显式定位(评审 2026-11-05 P2):按身份模式取
            # 属主/平台实例,不再取「id 最小的实例」(靠创建顺序)。
            inst = await _managed_instance(db, tpl)
            if inst is not None:
                at_svc.remap_detach_pause(
                    inst, "令牌已解绑,任务转由账号管理;启动后恢复调度")
            await db.commit()
            from ..models.access_token import AccessToken
            old_tok = await db.get(AccessToken, unbind_token_id)
            await audit_svc.record(
                db, actor_id=user.id,
                actor_name=user.display_name or user.username,
                action="token.task.unbind", resource_type="integration",
                resource_id=str(tpl.id), resource_name=tpl.name,
                detail={"task": tpl.id, "token": unbind_token_id,
                        "token_name": old_tok.name if old_tok else None})
            return await _tpl_out_full(db, tpl, inst, user)
    if body.triggerCron is not None:
        try:
            parse_cron(body.triggerCron)
        except CronError as e:
            raise _bad("cron_invalid", str(e)) from None
        tpl.trigger_cron = body.triggerCron
    if body.name is not None:
        tpl.name = body.name
    if "clientRef" in body.model_fields_set:
        tpl.client_ref = body.clientRef
    if "callbackPath" in body.model_fields_set:
        tpl.callback_path_override = body.callbackPath
    if "schemeId" in body.model_fields_set and principal.is_token:
        # 令牌保存面范围闸(§5.4:PATCH 422):换方案/清除都按**将生效**
        # 配方核对 —— 清除后回落默认方案,默认也可能引入超范围引用。
        if tpl.scenario_id:
            scen_row = (await db.execute(select(ComposerScenario).where(
                ComposerScenario.scenario_id == tpl.scenario_id))).scalar()
            if scen_row is not None:
                await _require_token_scope(
                    db, principal, scen_row, body.schemeId or None)
    if body.schemeId:
        # S0①(G-A):PATCH 同创建闸,方案必须属于模板场景
        if not tpl.scenario_id:
            raise _bad("scheme_not_owned", "任务未绑定场景,不能设置执行方案")
        from ..services import scheme_store
        try:
            await scheme_store.get_row(db, tpl.scenario_id, body.schemeId)
        except KeyError:
            raise _bad(
                "scheme_not_owned",
                f"执行方案不存在或不属于该场景: {body.schemeId}") from None
        tpl.scheme_id = body.schemeId
    elif body.schemeId is not None:
        tpl.scheme_id = body.schemeId   # 显式空串 = 清除(维持原语义)
    if body.resultPolicy in ("latest", "on_change"):
        tpl.result_policy = body.resultPolicy
    if body.visibility in ("private", "public"):
        tpl.visibility = body.visibility
    if body.targetSystem is not None:
        tpl.target_system = body.targetSystem
    tpl.updated_by = user.id
    await db.commit()
    # W0a⑤(G-C):public→private 联动 —— 非 owner 订阅实例暂停+通知;
    # 转回 public 不自动恢复,需订阅者重新确认(再订阅)
    if body.visibility == "private" and tpl.identity_mode == "personal":
        await integration_runner.pause_subscriber_instances(
            tpl, paused_reason="made_private",
            message="模板已转为私有,执行已暂停;模板重新公开后请重新"
                    "确认订阅")
    await audit_svc.record_inbound(db, principal, "inbound.task.write", detail={
        "fn": "patch", "task": tpl.id, "name": tpl.name,
        "changed": sorted(body.model_fields_set)})
    inst = await _tpl_instance(db, tpl.id)
    return await _tpl_out_full(db, tpl, inst, user)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, principal: PrincipalIn, db: DbSession) -> dict:
    """软删(评审 E7):卡片走「已移除」态,订阅者可见可自行删卡。
    令牌(§2.2):只能删本令牌注册的,否则 404。"""
    user = principal.user
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None or tpl.template_id is not None:
        raise _bad("not_found", "功能不存在", 404)
    if principal.is_token:
        if not _token_owns(principal, tpl):
            raise _bad("not_found", "功能不存在", 404)
    elif not _can_manage(user, tpl, await _platform_uid(db)):
        raise _bad("forbidden", "只有模板管理者能删除", 403)
    tpl.removed_at = datetime.now(timezone.utc)
    await db.commit()
    # W2(G-E):模板删除通知持有人(卡片转「已移除」态,但按 cron 等
    # 结果的用户只见「过期」—— 发一条人话通知)
    if tpl.identity_mode == "personal":
        await integration_runner.notify_subscribers(
            tpl,
            title=f"集成任务「{tpl.name}」已删除",
            message="模板已被创建者删除,你的订阅随之失效;"
                    "卡片会显示「已移除」,可自行删卡")
    await audit_svc.record_inbound(db, principal, "inbound.task.write", detail={
        "fn": "delete", "task": tpl.id, "name": tpl.name})
    return {"removed": True}


@router.post("/tasks/{task_id}/run")
async def run_task(task_id: int, principal: PrincipalIn, db: DbSession) -> dict:
    """立即执行:平台模式任意可见者(冷却 60s);个人模式订阅者各自
    的实例(无冷却,方案 §3 操作表)。W0a① 起「点执行即订阅」收口:
    未订阅用户 409 引导走订阅确认。

    令牌(§2.2):只能触发本令牌注册的任务(否则 404),且身份须与
    注册时一致 —— 个人模式任务的令牌属主 = 任务属主。"""
    user = principal.user
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None or tpl.template_id is not None or not (
            _token_owns(principal, tpl) if principal.is_token
            else _visible(user, tpl)):
        raise _bad("not_found", "功能不存在", 404)
    if principal.is_token:
        if tpl.identity_mode != principal.identity_mode:
            raise _bad(
                "identity_mode_conflict",
                f"该任务为{'个人' if tpl.identity_mode == 'personal' else '平台'}"
                f"模式,与令牌身份({principal.identity_mode})不符")
        if tpl.identity_mode == "personal" and tpl.owner_id != user.id:
            raise _bad(
                "token_owner_mismatch",
                "令牌属主与任务属主不一致,不能触发他人任务", 403)
    # A-4/W6 手动面前置闸(版本模型 §6):working 预览场景 409 拒触发,
    # 在建实例/占冷却之前;调度路径由 integration_runner 内部同款闸兜底。
    if tpl.scenario_id:
        scen_row = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == tpl.scenario_id))).scalar()
        if scen_row is not None and working_preview(scen_row.payload):
            raise _bad(
                "working_preview",
                "场景声明 working(预览执行),集成任务拒绝触发:"
                "请先在编排器钉定修订(外部服务不受影响)", 409)
    # W0a①(P-1=b 播种收口):个人模式不再隐式建实例 —— 未订阅 409
    # 引导订阅确认,不建不跑;平台模式维持 ensure(唯一平台实例兜底)。
    if tpl.identity_mode == "personal":
        inst = (await db.execute(select(IntegrationTask).where(
            IntegrationTask.template_id == tpl.id,
            IntegrationTask.holder_id == user.id))).scalar()
        if inst is None:
            raise _bad(
                "subscription_required",
                "尚未订阅该个人模式任务,请先订阅确认后再执行", 409)
    else:
        seeded = await integration_runner.ensure_instance(tpl)
        if seeded is None:
            raise _bad("instance_missing", "平台系统用户缺失(迁移 0015 未执行?)", 500)
        # ensure_instance 用的是独立会话;冷却与占用判定在本会话的行上做
        inst = await db.get(IntegrationTask, seeded.id)
    # 2-5(2026-10-13):naive utcnow() 与 PG 读回的 aware 时间相减必炸
    # (SQLite 读回 naive 一直没暴露)。now 侧直接取 aware UTC。
    now = datetime.now(timezone.utc)
    # C-4(2026-10-13):占用判定改条件更新(CAS)
    if not integration_runner._inflight_ok(tpl, inst.holder_id):
        raise _bad("inflight_limit", "在飞实例数已达上限,稍后再试", 429)
    from sqlalchemy import update as sa_update
    claimed = (await db.execute(
        sa_update(IntegrationTask)
        .where(IntegrationTask.id == inst.id,
               IntegrationTask.state != "running")
        .values(last_manual_run_at=now, state="running",
                running_since=now)
        .returning(IntegrationTask.id))).scalar()
    if claimed is None:
        raise _bad("running", "该功能正在执行", 409)
    await db.commit()
    integration_runner._inflight_add(tpl, inst.holder_id, 1)
    try:
        # P0-3.1:占用 CAS 写入的 now 即租约令牌
        result = await integration_runner.run_instance(inst.id, lease=now)
    except Exception as e:  # noqa: BLE001 — run_instance 内部已收口;兜一层
        raise _bad("run_failed", str(e)[:300], 500) from None
    finally:
        integration_runner._inflight_add(tpl, inst.holder_id, -1)
    fresh = await db.get(IntegrationTask, inst.id)
    if fresh is not None:
        await db.refresh(fresh)   # run_instance 在独立会话回写,穿透本会话缓存
    await audit_svc.record_inbound(db, principal, "inbound.task.write", detail={
        "fn": "run", "task": tpl.id, "name": tpl.name, "instance": inst.id,
        "run_status": (fresh.run_status or "") if fresh is not None else ""})
    return {"result": result, "instance": _inst_out(fresh)}


# ── W0a(个人侧方案 §2):订阅知情同意 ────────────────────────────

def _subscribable(tpl: IntegrationTask, user) -> None:
    """订阅面前置:模板行/可见/未删 + 仅个人模式(平台模式无订阅概念)。"""
    if tpl.template_id is not None or not _visible(user, tpl):
        raise _bad("not_found", "功能不存在", 404)
    if tpl.identity_mode != "personal":
        raise _bad("not_subscribable", "仅个人模式任务支持订阅", 422)


@router.get("/scenario-preview")
async def scenario_preview(
    user: CurrentUser, db: DbSession,
    scenarioId: str, schemeId: str | None = None,
) -> dict:
    """W1 创建前置提示:场景+方案(可选)的执行形态预览 —— 注入凭证
    别名、当前用户缺失清单、working 预览标记。只允许预览自己的场景
    (与创建闸同口径);指定方案须属该场景。"""
    scen = (await db.execute(select(ComposerScenario).where(
        ComposerScenario.scenario_id == scenarioId))).scalar()
    if scen is None:
        raise _bad("scenario_not_found", f"场景不存在: {scenarioId}", 404)
    if scen.owner_id != user.id:
        raise _bad("scenario_not_owned", "只能引用自己创建的场景")
    if schemeId:
        from ..services import scheme_store
        try:
            await scheme_store.get_row(db, scenarioId, schemeId)
        except KeyError:
            raise _bad(
                "scheme_not_owned",
                f"执行方案不存在或不属于该场景: {schemeId}") from None
    aliases = await integration_runner.scenario_aliases(db, scen, schemeId)
    return {
        "authAliases": aliases,
        "missingCredentials": await _missing_credentials(
            db, aliases, user.id),
        "workingPreview": bool(working_preview(scen.payload)),
    }


@router.get("/tasks/{task_id}/subscription-summary")
async def subscription_summary(
    task_id: int, user: CurrentUser, db: DbSession,
) -> dict:
    """订阅确认摘要(W0a③):步骤系统·方法·只读标记、所需凭证别名、
    服务地址、数据集名、cron —— 结构信息 only。"""
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None:
        raise _bad("not_found", "功能不存在", 404)
    _subscribable(tpl, user)
    from ..services.plate_client import PlateUnavailableError
    try:
        return await integration_runner.subscription_view(db, tpl)
    except integration_runner.IntegrationRunError as e:
        raise _bad(e.code, e.message, 404) from None
    except PlateUnavailableError as e:
        raise _bad("plate_unavailable",
                   f"接口定义暂不可得,稍后再试: {e}", 502) from None
    except Exception as e:  # noqa: BLE001 — 别名查询失败 → 503(订阅面口径)
        raise _bad("alias_unavailable",
                   f"服务地址解析失败,暂不能订阅: {e}", 503) from None


class SubscribeIn(BaseModel):
    """P2.2:订阅回传摘要里的 fingerprint —— 确认的必须是订阅者看到
    的那份内容;与当前计算值不一致 409,前端重拉摘要后再确认。
    **必填**。"""
    fingerprint: str = Field(min_length=1)


@router.post("/tasks/{task_id}/subscribe")
async def subscribe_task(
    task_id: int, user: CurrentUser, db: DbSession,
    body: SubscribeIn,
) -> dict:
    """显式订阅(W0a①/P-1=b):建立/刷新持有人实例 + 记录内容指纹与
    确认时刻;对 template_changed/made_private 暂停的实例 = 重新确认
    (刷新指纹并恢复调度)。幂等。**必须回传摘要 fingerprint**。"""
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None:
        raise _bad("not_found", "功能不存在", 404)
    _subscribable(tpl, user)
    scen = (await db.execute(select(ComposerScenario).where(
        ComposerScenario.scenario_id == tpl.scenario_id))).scalar() \
        if tpl.scenario_id else None
    if scen is None:
        raise _bad("scenario_not_found", "场景不存在", 404)
    # P2.2:先按当前内容算指纹并与回传值比对
    try:
        current_fp = await integration_runner.consent_fingerprint_now(
            db, tpl, scen)
    except Exception as e:  # noqa: BLE001 — 订阅面失败口径:503
        raise _bad("alias_unavailable",
                   f"服务地址解析失败,暂不能订阅: {e}", 503) from None
    if body.fingerprint != current_fp:
        raise _bad(
            "consent_stale",
            "模板内容已变更,请重新查看执行内容摘要后确认", 409)
    inst = await integration_runner.ensure_instance(tpl, holder_id=user.id)
    if inst is None:
        raise _bad("instance_missing", "实例创建失败", 500)
    inst = await db.get(IntegrationTask, inst.id)
    try:
        await integration_runner.refresh_consent(db, tpl, scen, inst)
    except Exception as e:  # noqa: BLE001 — 订阅面失败口径:503,不留半确认
        await db.rollback()
        raise _bad("alias_unavailable",
                   f"服务地址解析失败,暂不能订阅: {e}", 503) from None
    was_reconfirm = (inst.state == "paused" and inst.paused_reason in
                     ("template_changed", "made_private"))
    if inst.state == "paused" and inst.paused_reason in (
            "template_changed", "made_private"):
        inst.state = "idle"
        inst.paused_reason = ""
        inst.last_error = ""
        inst.next_run_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(inst)
    # 时间线:订阅(重新确认解除待确认暂停时,补记一条 resumed 配对)
    from ..services import activity as activity_svc
    if tpl.identity_mode == "personal":
        await activity_svc.record(
            db, actor_id=user.id, kind="integration.subscribed",
            resource_type="integration", resource_id=str(tpl.id),
            detail={"name": tpl.name}, coalesce=False)
        if was_reconfirm:
            await activity_svc.record(
                db, actor_id=user.id, kind="integration.resumed",
                resource_type="integration", resource_id=str(tpl.id),
                detail={"name": tpl.name, "via": "reconfirm"},
                coalesce=False)
    return await _tpl_out_full(db, tpl, inst, user)


@router.delete("/tasks/{task_id}/subscription", status_code=204)
async def unsubscribe_task(
    task_id: int, user: CurrentUser, db: DbSession,
) -> None:
    """退订(P-3):删持有人实例行(模板不动;重订 = 重新确认重建)。"""
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None:
        raise _bad("not_found", "功能不存在", 404)
    _subscribable(tpl, user)
    row = (await db.execute(select(IntegrationTask).where(
        IntegrationTask.template_id == tpl.id,
        IntegrationTask.holder_id == user.id))).scalar()
    if row is not None:
        await db.delete(row)
        await db.commit()
        # 时间线:退订(与 subscribed 成对)
        from ..services import activity as activity_svc
        if tpl.identity_mode == "personal":
            await activity_svc.record(
                db, actor_id=user.id, kind="integration.unsubscribed",
                resource_type="integration", resource_id=str(tpl.id),
                detail={"name": tpl.name}, coalesce=False)


async def _my_subscription(db: AsyncSession, tpl: IntegrationTask, user: User):
    row = (await db.execute(select(IntegrationTask).where(
        IntegrationTask.template_id == tpl.id,
        IntegrationTask.holder_id == user.id))).scalar()
    if row is None:
        raise _bad("subscription_not_found", "尚未订阅该任务", 404)
    return row


async def _resume_instance(db: AsyncSession, tpl: IntegrationTask,
                           inst: IntegrationTask, *, actor_id: int,
                           via: str) -> None:
    """「启动」的恢复逻辑(唯一实现):暂停实例回 idle、立即排期;
    fail_streak 恢复即清零(重启失败阶梯);个人模式写时间线
    ``integration.resumed``(``via`` 记恢复路径)。"""
    if inst.paused_reason == "fail_streak":
        inst.fail_streak = 0   # W4:启动即重置连续失败计数
    inst.state = "idle"
    inst.paused_reason = ""
    inst.next_run_at = datetime.now(timezone.utc)
    await db.commit()
    from ..services import activity as activity_svc
    if tpl.identity_mode == "personal":
        await activity_svc.record(
            db, actor_id=actor_id, kind="integration.resumed",
            resource_type="integration", resource_id=str(tpl.id),
            detail={"name": tpl.name, "via": via}, coalesce=False)


#: 「启动」放行的暂停原因(§3.3 恢复入口):manual/fail_streak 可直接
#: 恢复;scope_denied(场景公开后)/ resource_not_allowed(缺项处置后)
#: 条件由管理者满足后启动,下次运行再过复核闸。token_* 三类各有专属
#: 路径,不由「启动」代偿。authz C1:token_owner_ineligible 随 W5/0036
#: 退役(存量已由迁移恢复,不再产生)。
_RESUMABLE = ("manual", "fail_streak", "scope_denied",
              "resource_not_allowed")


@router.post("/tasks/{task_id}/subscription/pause")
async def pause_my_subscription(
    task_id: int, user: CurrentUser, db: DbSession,
) -> dict:
    """W0b⑥(G-D):订阅者自暂停 —— paused/manual(凭证复活钩子不覆盖
    manual,只有本人 resume 可恢复)。幂等;调度面只认 idle,暂停即
    不再被认领。W4:个人模式 owner 自有实例同走此口;平台模式对
    member+ 开放 —— 操作平台唯一实例,其他用户 403。"""
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None:
        raise _bad("not_found", "功能不存在", 404)
    _subscribable(tpl, user)
    inst = await _my_subscription(db, tpl, user)
    if inst.state != "paused" or inst.paused_reason != "manual":
        inst.state = "paused"
        inst.paused_reason = "manual"
        # 清掉上一轮运行的失败说明:manual 横幅/快照的 lastError 面只该
        # 出解绑与处置写入的备注(remap_detach_pause),陈旧运行错误当
        # 暂停说明展示会误导(评审 2026-11-05 收敛检查);与重新确认
        # 解除暂停时的清空同口径。
        inst.last_error = ""
        await db.commit()
        # 时间线:自暂停(状态确变才记,幂等重按不刷屏)
        from ..services import activity as activity_svc
        if tpl.identity_mode == "personal":
            await activity_svc.record(
                db, actor_id=user.id, kind="integration.paused",
                resource_type="integration", resource_id=str(tpl.id),
                detail={"name": tpl.name, "reason": "manual"},
                coalesce=False)
    return await _tpl_out_full(db, tpl, inst, user)


@router.post("/tasks/{task_id}/subscription/resume")
async def resume_my_subscription(
    task_id: int, user: CurrentUser, db: DbSession,
) -> dict:
    """W0b⑥:恢复(§3.3 恢复入口)。放行 ``_RESUMABLE`` 五类;其余暂停
    原因各有专属路径,恢复操作不代偿:

    * ``token_revoked`` → 409 提示先解绑(吊销是终态);
    * ``token_expired`` / ``token_invalidated`` → 409 提示续期或重新
      生成(完成后自动恢复);
    * template_changed/made_private → 重新订阅确认;
    * missing_credential → 补配凭证(复活钩子自动恢复)。
    """
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None:
        raise _bad("not_found", "功能不存在", 404)
    _subscribable(tpl, user)
    inst = await _my_subscription(db, tpl, user)
    reason = inst.paused_reason or ""
    if inst.state == "paused" and reason not in _RESUMABLE:
        if reason == at_svc.PAUSE_TOKEN_REVOKED:
            hint = ("该暂停(token_revoked)不能由恢复操作解除:令牌已吊销"
                    "(终态),请先在集成详情「解绑令牌」转由账号管理")
        elif reason == at_svc.PAUSE_TOKEN_EXPIRED:
            hint = ("该暂停(token_expired)请在个人设置对令牌续期或"
                    "重新生成,完成后任务自动恢复")
        elif reason == at_svc.PAUSE_TOKEN_INVALIDATED:
            hint = ("该暂停(token_invalidated)请在个人设置重新生成令牌,"
                    "完成后任务自动恢复")
        else:
            hint = ("该暂停(" + reason + ")不能由恢复操作解除:"
                    "template_changed/made_private 请重新订阅确认,"
                    "missing_credential 请补配凭证")
        raise _bad("resume_not_allowed", hint, 409)
    if inst.state == "paused":
        via = (reason if reason in ("fail_streak", "scope_denied",
                                    "resource_not_allowed")
               else "manual")
        await _resume_instance(db, tpl, inst, actor_id=user.id, via=via)
    return await _tpl_out_full(db, tpl, inst, user)


# ── 批量卡片接口(方案 §7 取数契约)─────────────────────────────

class CardsIn(BaseModel):
    ids: list[str] = Field(max_length=50)


@router.post("/cards")
async def cards(body: CardsIn, user: CurrentUser, db: DbSession) -> dict:
    """工作台把布局里的 fn:<id> 一次发出;只回状态/时间/摘要,不回整行。"""
    out: list[dict] = []
    plat_uid = await _platform_uid(db)
    for raw in body.ids:
        if not raw.startswith("fn:"):
            continue
        try:
            tid = int(raw[3:])
        except ValueError:
            continue
        tpl = await db.get(IntegrationTask, tid)
        if tpl is None or tpl.template_id is not None:
            out.append({"id": raw, "state": "removed"})
            continue
        if not _visible(user, tpl):
            out.append({"id": raw, "state": "removed"})
            continue
        inst = await _my_instance(db, tpl, user)   # W0a①:只读不播种
        io = _inst_out(inst)
        # W0b④:消费面字段(W3 凭证引导用:角标定位缺失别名)
        card_aliases = await integration_runner.auth_aliases_view(db, tpl)
        card_missing = await _missing_credentials(
            db, card_aliases,
            user.id if tpl.identity_mode == "personal"
            else (inst.holder_id if inst is not None else None))
        # Y4/方案 §7:卡片输出投影
        raw_outputs = (getattr(inst, "last_outputs", None) or {}) \
            if inst is not None else {}
        om = tpl.output_mapping if isinstance(tpl.output_mapping, dict) else {}
        card_outputs = {dst: raw_outputs[src]
                        for src, dst in om.items()
                        if isinstance(dst, str) and dst and src in raw_outputs} \
            if om else dict(raw_outputs)
        stale = False
        if io["lastRunAt"]:
            # I2 双触发过期(D10)
            stale = integration_runner.is_stale(
                tpl.trigger_cron, inst.last_run_at
                if inst is not None else None)
        out.append({
            "id": raw, "name": tpl.name, "state": io["state"],
            "enabled": io["enabled"],
            "runStatus": io["runStatus"], "checkStatus": io["checkStatus"],
            "checkMessage": io["checkMessage"],
            "checkChangedAt": io["checkChangedAt"],
            "pausedReason": io["pausedReason"],
            "failStreak": io["failStreak"],
            "lastRunAt": io["lastRunAt"], "lastError": io["lastError"],
            "cronText": describe_cron(tpl.trigger_cron),
            "identityMode": tpl.identity_mode, "stale": stale,
            "canManage": _can_manage(user, tpl, plat_uid),
            "authAliases": card_aliases,
            "missingCredentials": card_missing,
            "outputs": card_outputs,
            "cardTemplate": tpl.card_template or "status",
        })
    return {"items": out}
