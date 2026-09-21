"""工作台活动时间线服务端合流(M5,PG迁移方案 §7 M5-3)。

前端 useActivityTimeline 原来三条请求自己拼(执行 + 场景窗 + 适配批次)
—— 收编为一次 GET /api/activity:服务端合流三类事件,前端只做日历分组
与文案。三源独立降级语义保留:sources 报告各源是否取到,任一源失败
不拖垮整条轴。
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
from ..models.composer_scenario import ComposerScenario
from ..models.execution import Execution
from ..services import adaptation_service

router = APIRouter(prefix="/activity", tags=["activity"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

EXEC_LIMIT = 20
SCEN_LIMIT = 10
BATCH_LIMIT = 10


class ActivityEvent(BaseModel):
    kind: Literal["execution", "scenario", "adaptation"]
    at: str
    # execution 面
    executionId: int | None = None
    status: str | None = None
    scenarioId: str | None = None
    # scenario 面
    name: str | None = None
    module: str | None = None
    # adaptation 面
    batchId: str | None = None
    fromVersion: str | None = None
    toVersion: str | None = None
    endpointId: str | None = None
    opCount: int | None = None


class ActivityOut(BaseModel):
    events: list[ActivityEvent] = Field(default_factory=list)
    """各源是否取到(任一源失败 → 前端轴上降级提示,不拖垮整轴)。"""
    sources: dict[str, bool] = Field(default_factory=dict)


@router.get("", response_model=ActivityOut)
async def get_activity(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 40,
) -> ActivityOut:
    """本人活动轴:我的执行 + 我的私有场景改动 + 触碰我场景的适配批次,
    按 at 倒序合并,截 ``limit``。"""
    events: list[ActivityEvent] = []
    sources: dict[str, bool] = {}

    # ── 执行(owner 隔离;排队且无时间戳的行无处安放,跳过)─────────
    try:
        rows = (await db.execute(
            select(Execution)
            .where(Execution.owner_id == user.id)
            .order_by(Execution.id.desc())
            .limit(EXEC_LIMIT * 2)
        )).scalars().all()
        for e in rows:
            at = e.finished_at or e.started_at
            if at is None:
                continue
            events.append(ActivityEvent(
                kind="execution", at=iso_naive_utc(at) or "",
                executionId=e.id, status=e.status, scenarioId=e.scenario_id))
        sources["executions"] = True
    except Exception:
        sources["executions"] = False

    # ── 场景改动(私有桶 = 我的;公共原件的改动不是我的活动)─────────
    try:
        scen = (await db.execute(
            select(ComposerScenario)
            .where(ComposerScenario.owner_id == user.id,
                   ComposerScenario.visibility == "private")
            .order_by(ComposerScenario.updated_at.desc())
            .limit(SCEN_LIMIT)
        )).scalars().all()
        for srow in scen:
            if srow.updated_at is None:
                continue
            events.append(ActivityEvent(
                kind="scenario", at=iso_naive_utc(srow.updated_at) or "",
                scenarioId=srow.scenario_id, name=srow.name or srow.scenario_id,
                module=srow.module or None))
        sources["scenarios"] = True
    except Exception:
        sources["scenarios"] = False

    # ── 适配批次(触碰我场景的批次;member 无全量权,owner 视图人人可读)──
    try:
        batches, _total = await adaptation_service.list_batches_for_owner(
            db, user.id, page=1, page_size=BATCH_LIMIT)
        from datetime import datetime as _dt

        for b in batches[:BATCH_LIMIT]:
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

    events.sort(key=lambda e: e.at, reverse=True)
    return ActivityOut(events=events[:limit], sources=sources)
