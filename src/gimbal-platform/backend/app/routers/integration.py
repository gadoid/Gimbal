"""外部系统集成 P1 路由:功能(模板)CRUD + 手动执行 + 批量卡片 +
平台凭证(admin)。

《GIMBAL-外部系统集成架构设计》§9 + 评审定稿:P1 只开放平台模式
(personal 随 P2);模板软删(评审 E7);平台凭证 = 平台系统用户的
auth_sessions(决策 9,复用加密与连通测试,只限 admin 管理)。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..core.security import fernet_decrypt, fernet_encrypt
from ..models.auth_session import AuthSession
from ..models.composer_scenario import ComposerScenario
from ..models.integration_task import IntegrationTask
from ..models.user import User
from ..services import integration_runner
from ..services.cron_expr import CronError, describe_cron, parse_cron
from ..services.run_semantics import working_preview

DbSession = Annotated[AsyncSession, Depends(get_db)]
router = APIRouter(prefix="/integration", tags=["integration"])


def _bad(code: str, message: str, status: int = 422) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _iso(dt: datetime | None) -> str | None:
    """UTC naive 归一后再拼 Z(asyncpg 读 timestamptz 回 aware,直接
    isoformat 会产出 "+00:00Z" 双后缀,前端解析失败显示空)。"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"


def _safe_decrypt(encrypted: str) -> str:
    """FERNET_KEY 轮换后旧行不可解 → 掩码(行仍可见可重录),不炸列表。"""
    try:
        return fernet_decrypt(encrypted)
    except ValueError:
        return "(不可解密,请重录)"


def _can_manage(user, tpl: IntegrationTask) -> bool:
    """模板改动权:owner;平台模式另含 admin(方案 §3 操作表)。"""
    return user.id == tpl.owner_id or (
        tpl.identity_mode == "platform" and user.role == "admin")


def _visible(user, tpl: IntegrationTask) -> bool:
    return tpl.removed_at is None and (
        tpl.owner_id == user.id or tpl.visibility == "public"
        or user.role == "admin")


async def _my_instance(db: AsyncSession, tpl: IntegrationTask, user):
    """当前用户的实例(**只读**,W0a① 播种收口):personal 按 holder
    查不建;platform 维持平台唯一实例口径(不建,创建时已有)。"""
    if tpl.identity_mode == "personal":
        return (await db.execute(select(IntegrationTask).where(
            IntegrationTask.template_id == tpl.id,
            IntegrationTask.holder_id == user.id))).scalar()
    return await _tpl_instance(db, tpl.id)


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


def _tpl_out(db_tpl: IntegrationTask, inst: IntegrationTask | None,
             current: User, *, auth_aliases: list[str] | None = None,
             subscribed: bool | None = None) -> dict:
    out = {
        "id": db_tpl.id,
        "name": db_tpl.name,
        "ownerId": db_tpl.owner_id,
        "mine": db_tpl.owner_id == current.id,
        "canManage": current.role == "admin" or db_tpl.owner_id == current.id,
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
    missing 的持有人:personal = 当前查看者(「我缺什么」),platform =
    平台实例持有人。"""
    aliases = await integration_runner.auth_aliases_view(db, tpl)
    holder = user.id if tpl.identity_mode == "personal" else (
        inst.holder_id if inst is not None else None)
    missing = await _missing_credentials(db, aliases, holder)
    subscribed = (tpl.identity_mode == "personal"
                  and inst is not None and inst.holder_id == user.id)
    out = _tpl_out(tpl, inst, user,
                   auth_aliases=aliases, subscribed=subscribed)
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
    identityMode: str = "platform"
    triggerCron: str = "*/5 * * * *"
    resultPolicy: str = "latest"
    cardTemplate: str = "status"
    visibility: str = "private"
    targetSystem: str = ""


class TaskPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    schemeId: str | None = None
    triggerCron: str | None = None
    resultPolicy: str | None = None
    visibility: str | None = None
    targetSystem: str | None = None


@router.get("/tasks")
async def list_tasks(user: CurrentUser, db: DbSession) -> dict:
    """可见模板:我的 + 公共(admin 全见);软删的不出。"""
    rows = (await db.execute(
        select(IntegrationTask).where(
            IntegrationTask.template_id.is_(None),
            IntegrationTask.removed_at.is_(None),
        ).order_by(IntegrationTask.id.desc()))).scalars().all()
    out = []
    for t in rows:
        if not _visible(user, t):
            continue
        inst = await _my_instance(db, t, user)   # W0a①:列表只读不播种
        out.append(await _tpl_out_full(db, t, inst, user))
    return {"items": out}


@router.post("/tasks", status_code=201)
async def create_task(body: TaskIn, user: CurrentUser, db: DbSession) -> dict:
    if body.identityMode not in ("platform", "personal"):
        raise _bad("identity_mode_invalid",
                   "identityMode ∈ platform | personal")
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
        raise _bad("scenario_not_owned", "只能引用自己创建的场景")
    # S0①(个人侧方案 G-A):方案必须属于该场景(run_precheck 同款
    # 场景限定)。此前 schemeId 直接入库 + runner 全局取方案,枚举
    # rs-NNN 可跨场景引用他人方案/数据集。
    if body.schemeId:
        from ..services import scheme_store
        try:
            await scheme_store.get_row(db, scen.scenario_id, body.schemeId)
        except KeyError:
            raise _bad(
                "scheme_not_owned",
                f"执行方案不存在或不属于该场景: {body.schemeId}") from None
    # 平台模式只读闸(方案 §3:保存前检查并列出不满足的步骤);
    # Y3:个人模式放行写操作(写操作必须个人身份,方案 §3)
    if body.identityMode == "platform":
        ok, offenders = await _read_only_with_plate(db, scen)
        if not ok:
            raise _bad("not_read_only",
                       f"平台模式要求全部步骤为只读"
                       f"(GET/HEAD/OPTIONS 或已标 query_safe): "
                       f"{'、'.join(offenders)}")
    tpl = IntegrationTask(
        name=body.name, owner_id=user.id, visibility=body.visibility,
        identity_mode=body.identityMode, target_type="scenario",
        scenario_id=body.scenarioId, scheme_id=body.schemeId,
        target_system=body.targetSystem or "", trigger_cron=body.triggerCron,
        result_policy=body.resultPolicy, card_template=body.cardTemplate,
        updated_by=user.id)
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    inst = await integration_runner.ensure_instance(
        tpl, holder_id=user.id if body.identityMode == "personal" else None)
    if inst is not None:
        # W0a③:owner 实例留底内容指纹(执行闸只对非 owner 生效);
        # 别名查询失败不阻断创建(owner 无闸,best-effort)
        try:
            inst2 = await db.get(IntegrationTask, inst.id)
            await integration_runner.refresh_consent(db, tpl, scen, inst2)
            await db.commit()
        except Exception:  # noqa: BLE001
            await db.rollback()
    return await _tpl_out_full(db, tpl, inst, user)


async def _read_only_with_plate(
    db: AsyncSession, scen: ComposerScenario,
) -> tuple[bool, list[str]]:
    """P1 口径 = 全部步骤安全方法(POST+query_safe 随 P2 接 plate 元数据)。"""
    return await integration_runner.is_scenario_read_only(scen.payload)


@router.get("/tasks/{task_id}")
async def get_task(task_id: int, user: CurrentUser, db: DbSession) -> dict:
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None or tpl.template_id is not None or not _visible(user, tpl):
        raise _bad("not_found", "功能不存在", 404)
    inst = await _my_instance(db, tpl, user)   # W0a①:详情只读不播种
    return await _tpl_out_full(db, tpl, inst, user)


@router.patch("/tasks/{task_id}")
async def patch_task(
    task_id: int, body: TaskPatch, user: CurrentUser, db: DbSession,
) -> dict:
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None or tpl.template_id is not None or tpl.removed_at is not None:
        raise _bad("not_found", "功能不存在", 404)
    if not _can_manage(user, tpl):
        raise _bad("forbidden", "只有模板 owner(平台模式含 admin)能修改", 403)
    if body.triggerCron is not None:
        try:
            parse_cron(body.triggerCron)
        except CronError as e:
            raise _bad("cron_invalid", str(e)) from None
        tpl.trigger_cron = body.triggerCron
    if body.name is not None:
        tpl.name = body.name
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
    inst = await _tpl_instance(db, tpl.id)
    return await _tpl_out_full(db, tpl, inst, user)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, user: CurrentUser, db: DbSession) -> dict:
    """软删(评审 E7):卡片走「已移除」态,订阅者可见可自行删卡。"""
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None or tpl.template_id is not None:
        raise _bad("not_found", "功能不存在", 404)
    if not _can_manage(user, tpl):
        raise _bad("forbidden", "只有模板 owner(平台模式含 admin)能删除", 403)
    tpl.removed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"removed": True}


@router.post("/tasks/{task_id}/run")
async def run_task(task_id: int, user: CurrentUser, db: DbSession) -> dict:
    """立即执行:平台模式任意可见者(冷却 60s);个人模式订阅者各自
    的实例(无冷却,方案 §3 操作表)。W0a① 起「点执行即订阅」收口:
    未订阅用户 409 引导走订阅确认。"""
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None or tpl.template_id is not None or not _visible(user, tpl):
        raise _bad("not_found", "功能不存在", 404)
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
    # (SQLite 读回 naive 一直没暴露)。now 侧直接取 aware UTC(utcnow
    # 3.12 起废弃);DB 读回仍按 ensure_aware 归一(两方言形状不同)。
    from ..core.timeutil import ensure_aware
    now = datetime.now(timezone.utc)
    _last_manual = (ensure_aware(inst.last_manual_run_at)
                    if inst.last_manual_run_at is not None else None)
    # Y3/方案 §3 操作表:冷却只对平台模式(任意订阅者触发需限频);
    # 个人模式 = 实例持有人自己,无限冷却
    if tpl.identity_mode == "platform" \
            and inst.last_manual_run_at is not None and (
            now - _last_manual).total_seconds() \
            < integration_runner.MANUAL_COOLDOWN_SECONDS:
        wait = int(integration_runner.MANUAL_COOLDOWN_SECONDS - (
            now - _last_manual).total_seconds())
        raise _bad("cooldown", f"手动执行冷却中,约 {wait}s 后可再试", 409)
    # C-4(2026-10-13):占用判定改条件更新(CAS) —— 此前"读 state → 写
    # running"两步,与调度器并发或个人模式(无冷却)连点会把同一实例执行
    # 两次;且手动路径不计入 _inflight 上限。CAS 失败 = 已被占用,409。
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
        result = await integration_runner.run_instance(inst.id)
    except Exception as e:  # noqa: BLE001 — run_instance 内部已收口;兜一层
        raise _bad("run_failed", str(e)[:300], 500) from None
    finally:
        integration_runner._inflight_add(tpl, inst.holder_id, -1)
    fresh = await db.get(IntegrationTask, inst.id)
    if fresh is not None:
        await db.refresh(fresh)   # run_instance 在独立会话回写,穿透本会话缓存
    return {"result": result, "instance": _inst_out(fresh)}


# ── W0a(个人侧方案 §2):订阅知情同意 ────────────────────────────

def _subscribable(tpl: IntegrationTask, user) -> None:
    """订阅面前置:模板行/可见/未删 + 仅个人模式(平台模式无订阅概念)。"""
    if tpl.template_id is not None or not _visible(user, tpl):
        raise _bad("not_found", "功能不存在", 404)
    if tpl.identity_mode != "personal":
        raise _bad("not_subscribable", "仅个人模式任务支持订阅", 422)


@router.get("/tasks/{task_id}/subscription-summary")
async def subscription_summary(
    task_id: int, user: CurrentUser, db: DbSession,
) -> dict:
    """订阅确认摘要(W0a③):步骤系统·方法·只读标记、所需凭证别名、
    服务地址、数据集名、cron —— 结构信息 only,不含场景全文与数据值
    (私有场景可见性边界,§2.1)。"""
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None:
        raise _bad("not_found", "功能不存在", 404)
    _subscribable(tpl, user)
    try:
        return await integration_runner.subscription_view(db, tpl)
    except integration_runner.IntegrationRunError as e:
        raise _bad(e.code, e.message, 404) from None
    except Exception as e:  # noqa: BLE001 — 别名查询失败 → 503(订阅面口径)
        raise _bad("alias_unavailable",
                   f"服务地址解析失败,暂不能订阅: {e}", 503) from None


@router.post("/tasks/{task_id}/subscribe")
async def subscribe_task(
    task_id: int, user: CurrentUser, db: DbSession,
) -> dict:
    """显式订阅(W0a①/P-1=b):建立/刷新持有人实例 + 记录内容指纹与
    确认时刻;对 template_changed/made_private 暂停的实例 = 重新确认
    (刷新指纹并恢复调度)。幂等。"""
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None:
        raise _bad("not_found", "功能不存在", 404)
    _subscribable(tpl, user)
    scen = (await db.execute(select(ComposerScenario).where(
        ComposerScenario.scenario_id == tpl.scenario_id))).scalar() \
        if tpl.scenario_id else None
    if scen is None:
        raise _bad("scenario_not_found", "场景不存在", 404)
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
    if inst.state == "paused" and inst.paused_reason in (
            "template_changed", "made_private"):
        inst.state = "idle"
        inst.paused_reason = ""
        inst.last_error = ""
        inst.next_run_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(inst)
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


async def _my_subscription(db: AsyncSession, tpl: IntegrationTask, user: User):
    row = (await db.execute(select(IntegrationTask).where(
        IntegrationTask.template_id == tpl.id,
        IntegrationTask.holder_id == user.id))).scalar()
    if row is None:
        raise _bad("subscription_not_found", "尚未订阅该任务", 404)
    return row


@router.post("/tasks/{task_id}/subscription/pause")
async def pause_my_subscription(
    task_id: int, user: CurrentUser, db: DbSession,
) -> dict:
    """W0b⑥(G-D):订阅者自暂停 —— paused/manual(凭证复活钩子不覆盖
    manual,只有本人 resume 可恢复)。幂等;调度面只认 idle,暂停即
    不再被认领。"""
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None:
        raise _bad("not_found", "功能不存在", 404)
    _subscribable(tpl, user)
    inst = await _my_subscription(db, tpl, user)
    if inst.state != "paused" or inst.paused_reason != "manual":
        inst.state = "paused"
        inst.paused_reason = "manual"
        await db.commit()
    return await _tpl_out_full(db, tpl, inst, user)


@router.post("/tasks/{task_id}/subscription/resume")
async def resume_my_subscription(
    task_id: int, user: CurrentUser, db: DbSession,
) -> dict:
    """W0b⑥:订阅者恢复(仅 manual 暂停可恢复)。其余暂停原因各有
    专属路径,恢复操作不代偿:template_changed/made_private → 重新
    订阅确认;missing_credential → 补配凭证(复活钩子自动恢复)。"""
    tpl = await db.get(IntegrationTask, task_id)
    if tpl is None:
        raise _bad("not_found", "功能不存在", 404)
    _subscribable(tpl, user)
    inst = await _my_subscription(db, tpl, user)
    if inst.state == "paused" and inst.paused_reason != "manual":
        raise _bad(
            "resume_not_allowed",
            f"该暂停({inst.paused_reason})不能由恢复操作解除:"
            "template_changed/made_private 请重新订阅确认,"
            "missing_credential 请补配凭证", 409)
    if inst.state == "paused":
        inst.state = "idle"
        inst.paused_reason = ""
        inst.next_run_at = datetime.now(timezone.utc)
        await db.commit()
    return await _tpl_out_full(db, tpl, inst, user)


# ── 批量卡片接口(方案 §7 取数契约)─────────────────────────────

class CardsIn(BaseModel):
    ids: list[str] = Field(max_length=50)


@router.post("/cards")
async def cards(body: CardsIn, user: CurrentUser, db: DbSession) -> dict:
    """工作台把布局里的 fn:<id> 一次发出;只回状态/时间/摘要,不回整行。"""
    out: list[dict] = []
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
        # Y4/方案 §7:卡片输出投影 —— output_mapping {输出键 → 展示键};
        # 缺省(空 mapping)= 全量 last_outputs(已脱敏)。kv/counter/
        # list 模板据比渲染。
        raw_outputs = (getattr(inst, "last_outputs", None) or {}) \
            if inst is not None else {}
        om = tpl.output_mapping if isinstance(tpl.output_mapping, dict) else {}
        card_outputs = {dst: raw_outputs[src]
                        for src, dst in om.items()
                        if isinstance(dst, str) and dst and src in raw_outputs} \
            if om else dict(raw_outputs)
        stale = False
        if io["lastRunAt"]:
            # I2 双触发过期(D10,取代固定 1h):错过两次应有的触发才过期;
            # cron 坏/无 cron 由 is_stale 内部回退 1h(fail-open 到旧行为)
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
            "lastRunAt": io["lastRunAt"], "lastError": io["lastError"],
            "cronText": describe_cron(tpl.trigger_cron),
            "identityMode": tpl.identity_mode, "stale": stale,
            "authAliases": card_aliases,
            "missingCredentials": card_missing,
            "outputs": card_outputs,
            "cardTemplate": tpl.card_template or "status",
        })
    return {"items": out}


# ── 平台凭证(admin;决策 9/10)──────────────────────────────────

class PlatformCredIn(BaseModel):
    alias: str = Field(min_length=1, max_length=64)
    url: str = ""
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)
    tokenType: str = "Bearer"
    expiresIn: int = 7200


def _require_admin(user) -> None:
    if user.role != "admin":
        raise _bad("forbidden", "平台凭证仅 admin 可管理", 403)


@router.get("/platform-credentials")
async def list_platform_credentials(
    user: CurrentUser, db: DbSession,
) -> dict:
    _require_admin(user)
    holder = await integration_runner.get_platform_user_id()
    if holder is None:
        return {"items": []}
    rows = (await db.execute(select(AuthSession).where(
        AuthSession.owner_id == holder))).scalars().all()
    return {"items": [{
        "id": r.id, "alias": r.alias, "url": r.url,
        "username": _safe_decrypt(r.username_enc),
        "tokenType": r.token_type, "expiresIn": r.expires_in,
    } for r in rows]}


@router.post("/platform-credentials", status_code=201)
async def create_platform_credential(
    body: PlatformCredIn, user: CurrentUser, db: DbSession,
) -> dict:
    _require_admin(user)
    holder = await integration_runner.get_platform_user_id()
    if holder is None:
        raise _bad("platform_user_missing", "平台系统用户缺失", 500)
    dup = (await db.execute(select(AuthSession).where(
        AuthSession.owner_id == holder,
        AuthSession.alias == body.alias))).scalar()
    if dup is not None:
        raise _bad("alias_dup", f"别名已存在: {body.alias}", 409)
    row = AuthSession(
        owner_id=holder, alias=body.alias, url=body.url,
        username_enc=fernet_encrypt(body.username),
        password_enc=fernet_encrypt(body.password),
        token_type=body.tokenType, expires_in=body.expiresIn)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    # G7/Y2:平台凭证新建 = 恢复信号 → auth_failed 暂停的平台模式实例
    # 恢复调度(revive 内部平台模式不受 user_id 过滤)。
    try:
        from ..services import integration_runner as _ir
        await _ir.revive_paused_instances(user.id)
    except Exception:  # noqa: BLE001
        pass
    return {"id": row.id, "alias": row.alias}


@router.delete("/platform-credentials/{cred_id}")
async def delete_platform_credential(
    cred_id: int, user: CurrentUser, db: DbSession,
) -> dict:
    _require_admin(user)
    holder = await integration_runner.get_platform_user_id()
    row = await db.get(AuthSession, cred_id)
    if row is None or row.owner_id != holder:
        raise _bad("not_found", "凭证不存在", 404)
    await db.delete(row)
    await db.commit()
    return {"removed": True}
