"""工作台活动时间线服务端合流(M5,PG迁移方案 §7 M5-3)。

前端 useActivityTimeline 原来三条请求自己拼(执行 + 场景窗 + 适配批次)
—— 收编为一次 GET /api/activity:服务端合流事件,前端只做日历分组与
文案。各源独立降级语义保留:sources 报告各源是否取到,任一源失败不
拖垮整条轴。

容量语义(2026-11-03 改造):``limit`` 是**每类上限**(缺省 30),不再
全局截断 —— 此前合流后统一截 ``limit``,单一类型刷屏会把其余类型挤出
轴、且按类型筛选时远不足额。现在每类各留 30 条返回(≤ 6×limit 行),
「全部」视图取混排最近 30 由前端负责(useActivityTimeline 的
TIMELINE_POOL)。入站调用(inbound.run,经个人令牌触发的执行/临时调用)
自本改造起入轴 —— 此前第三方调用只有执行行(owner 隔离)看不出调用
来源维度。
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..core.timeutil import iso_naive_utc
from ..models import ActivityEvent as ActivityEventRow
from ..models.execution import Execution
from ..services import adaptation_service

router = APIRouter(prefix="/activity", tags=["activity"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# 2026-11-03 起:每类一份等额窗口(此前 20/10/10 + 全局截断)
PER_KIND_LIMIT = 30


def _int_or_none(v) -> "int | None":
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class ActivityEvent(BaseModel):
    kind: Literal["execution", "scenario", "adaptation", "suite",
                  "integration", "inbound"]
    at: str
    # execution 面
    executionId: int | None = None
    status: str | None = None
    scenarioId: str | None = None
    # 用例展示名(快照列;空(历史行)由前端回退 scenarioId)
    scenarioName: str | None = None
    # scenario 面(F3 起走 activity_events:action 是子动作
    # edit/rename/save_as/handoff_received;detail 携带
    # name/oldName/newName/sourceScenarioId/senderName)
    name: str | None = None
    module: str | None = None
    action: str | None = None
    detail: dict | None = None
    # adaptation 面
    batchId: str | None = None
    fromVersion: str | None = None
    toVersion: str | None = None
    endpointId: str | None = None
    opCount: int | None = None
    # suite 面(suites 事件此前只写不读 —— 2026-10-20 起并入时间线)
    suiteId: int | None = None
    # integration 面(边沿事件:订阅/暂停/恢复/结论翻转)
    taskId: int | None = None
    # inbound 面(webhook v4 §7.3:经令牌触发的执行/临时调用;detail 另带
    # identity_mode/steps(临时调用全量请求)/release/run_id)
    tokenId: int | None = None
    tokenName: str | None = None
    clientRef: str | None = None


class ActivityOut(BaseModel):
    events: list[ActivityEvent] = Field(default_factory=list)
    """各源是否取到(任一源失败 → 前端轴上降级提示,不拖垮整轴)。"""
    sources: dict[str, bool] = Field(default_factory=dict)


@router.get("", response_model=ActivityOut)
async def get_activity(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = PER_KIND_LIMIT,
) -> ActivityOut:
    """本人活动轴:我的执行 + 我的私有场景改动 + 触碰我场景的适配批次
    + 我的 suite/集成事件(2026-10-20 起)+ 入站调用(2026-11-03 起),
    按 at 倒序合并。``limit`` = **每类上限**(不做全局截断,「全部」视图
    取混排最近 30 由前端负责 —— 见模块注释的容量语义改造说明)。
    """
    events: list[ActivityEvent] = []
    sources: dict[str, bool] = {}

    # ── 执行(owner 隔离;排队且无时间戳的行无处安放,跳过)─────────
    # 取 2×limit 再过滤无时间戳行,装满 limit 即停 —— 每类上限对执行源
    # 同样成立(2026-11-03 容量语义),不随 2× 预取超发。
    try:
        rows = (await db.execute(
            select(Execution)
            .where(Execution.owner_id == user.id)
            .order_by(Execution.id.desc())
            .limit(limit * 2)
        )).scalars().all()
        taken = 0
        for e in rows:
            at = e.finished_at or e.started_at
            if at is None:
                continue
            events.append(ActivityEvent(
                kind="execution", at=iso_naive_utc(at) or "",
                executionId=e.id, status=e.status, scenarioId=e.scenario_id,
                scenarioName=(e.scenario_name or None)))
            taken += 1
            if taken >= limit:
                break
        sources["executions"] = True
    except Exception:
        sources["executions"] = False

    # ── 场景事件(F3,2026-09-23:activity_events 真事件取代
    #    updated_at 反推;冷启动空窗已拍板接受 —— 旧口径本是假事件,
    #    不留暖场回退双口径)─────────────────────────────────────────
    try:
        rows = (await db.execute(
            select(ActivityEventRow)
            .where(ActivityEventRow.actor_id == user.id,
                   ActivityEventRow.resource_type == "scenario")
            .order_by(ActivityEventRow.created_at.desc())
            .limit(limit)
        )).scalars().all()
        for r in rows:
            d = r.detail or {}
            events.append(ActivityEvent(
                kind="scenario", at=iso_naive_utc(r.created_at) or "",
                scenarioId=r.resource_id,
                name=d.get("name") or r.resource_id,
                action=r.kind, detail=d or None))
        sources["scenarios"] = True
    except Exception:
        sources["scenarios"] = False

    # ── 适配批次(触碰我场景的批次;member 无全量权,owner 视图人人可读)──
    try:
        batches, _total = await adaptation_service.list_batches_for_owner(
            db, user.id, page=1, page_size=limit)
        from datetime import datetime as _dt

        for b in batches[:limit]:
            ops = sum((b.get("opCounts") or {}).values())
            raw_at = b.get("closedAt") or b.get("createdAt")
            at_str = iso_naive_utc(raw_at) if isinstance(raw_at, _dt) else str(raw_at or "")
            events.append(ActivityEvent(
                kind="adaptation",
                at=at_str,
                batchId=b.get("batchId"),
                fromVersion=b.get("fromVersion"),
                toVersion=b.get("toVersion"),
                status=b.get("status"),
                endpointId=b.get("endpointId"),
                opCount=int(ops),
            ))
        sources["adaptations"] = True
    except Exception:
        sources["adaptations"] = False

    # ── suite 事件(2026-10-20:suite.share_* 此前只写不读,同表同源
    #    查询补上;kind 区分路由渲染)────────────────────────────────
    try:
        rows = (await db.execute(
            select(ActivityEventRow)
            .where(ActivityEventRow.actor_id == user.id,
                   ActivityEventRow.resource_type == "suite")
            .order_by(ActivityEventRow.created_at.desc())
            .limit(limit)
        )).scalars().all()
        for r in rows:
            d = r.detail or {}
            suite_id: int | None = None
            try:
                suite_id = int(r.resource_id)
            except (TypeError, ValueError):
                suite_id = None
            events.append(ActivityEvent(
                kind="suite", at=iso_naive_utc(r.created_at) or "",
                suiteId=suite_id,
                name=d.get("name") or r.resource_id,
                action=r.kind, detail=d or None))
        sources["suites"] = True
    except Exception:
        sources["suites"] = False

    # ── 集成事件(边沿:订阅/退订/暂停/恢复/翻转;个人实例归持有人轴)──
    try:
        rows = (await db.execute(
            select(ActivityEventRow)
            .where(ActivityEventRow.actor_id == user.id,
                   ActivityEventRow.resource_type == "integration")
            .order_by(ActivityEventRow.created_at.desc())
            .limit(limit)
        )).scalars().all()
        for r in rows:
            d = r.detail or {}
            task_id: int | None = None
            try:
                task_id = int(r.resource_id)
            except (TypeError, ValueError):
                task_id = None
            events.append(ActivityEvent(
                kind="integration", at=iso_naive_utc(r.created_at) or "",
                taskId=task_id,
                name=d.get("name") or r.resource_id,
                action=r.kind, detail=d or None))
        sources["integrations"] = True
    except Exception:
        sources["integrations"] = False

    # ── 入站调用(webhook v4 §7.3:经**个人令牌**触发的执行/临时调用;
    #    actor = 令牌属主,写入点 runs.py;平台令牌不上个人轴(D23))──
    try:
        rows = (await db.execute(
            select(ActivityEventRow)
            .where(ActivityEventRow.actor_id == user.id,
                   ActivityEventRow.resource_type == "inbound")
            .order_by(ActivityEventRow.created_at.desc())
            .limit(limit)
        )).scalars().all()
        for r in rows:
            d = r.detail or {}
            exec_id = d.get("execution_id")
            events.append(ActivityEvent(
                kind="inbound", at=iso_naive_utc(r.created_at) or "",
                executionId=int(exec_id) if exec_id is not None else None,
                scenarioId=d.get("scenario_id"),
                scenarioName=d.get("scenario_name"),
                tokenId=d.get("token_id")
                if d.get("token_id") is not None else _int_or_none(r.resource_id),
                tokenName=d.get("token_name"),
                clientRef=d.get("client_ref"),
                action=r.kind, detail=d or None))
        sources["inbound"] = True
    except Exception:
        sources["inbound"] = False

    events.sort(key=lambda e: e.at, reverse=True)
    # 每类上限已各自生效;此处不再全局截断(容量语义见模块注释)
    return ActivityOut(events=events, sources=sources)
