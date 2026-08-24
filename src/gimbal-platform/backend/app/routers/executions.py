"""Executions API — 读侧 + 删除(V3)。

V1 子进程创建链路(POST /executions 与 rerun,经 executor.py 的
gimbal CLI 子进程)已退役;V3 场景执行的创建入口是 ``POST /api/runs``
(run_dispatcher → gimbal_launcher 子进程(``gimbal run launch``))。

exec_runs 表(V1 每-run 明细/报告/日志/SSE)已随存量数据清理一并
退役:V3 运行的可观测面是 Execution 计数器 + ``data/runs/*.jsonl``
调度日志(无 API 消费,运维直读文件)。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, get_owned_execution
from ..core.timeutil import utcnow
from ..models import Execution
from ..models.execution import STATUS_CANCELED, STATUS_QUEUED
from ..schemas.execution import ExecutionListOut, ExecutionOut
from ..services import execution_store, run_dispatcher

router = APIRouter(prefix="/executions", tags=["executions"])


DbSession = Annotated[AsyncSession, Depends(get_db)]
OwnedExecution = Annotated[Execution, Depends(get_owned_execution)]


# ── list ────────────────────────────────────────────────────────
@router.get("", response_model=ExecutionListOut)
async def list_executions(
    user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExecutionListOut:
    """分页列表(P:此前全量返回,无界)。默认 200 与前端现状兼容。"""
    base = select(Execution).where(Execution.owner_id == user.id)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                base.order_by(Execution.id.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    items = [execution_store.execution_out(e) for e in rows]
    return ExecutionListOut(items=items, total=total)


# ── detail ─────────────────────────────────────────────────────
@router.get("/{execution_id}", response_model=ExecutionOut)
async def get_execution(ex: OwnedExecution) -> ExecutionOut:
    return execution_store.execution_out(ex)


# ── delete ─────────────────────────────────────────────────────
@router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution(
    ex: OwnedExecution,
    session: DbSession,
) -> None:
    await execution_store.delete_execution(session, ex)


# ── cancel ──────────────────────────────────────────────────────
@router.post("/{execution_id}/cancel", response_model=ExecutionOut)
async def cancel_execution(
    ex: OwnedExecution,
    session: DbSession,
) -> ExecutionOut:
    """P4 协作式取消:登记请求,在飞 fanout 在行边界收敛为 canceled。

    无在飞 task 的 queued 僵尸单立即终态化。终态单 409。
    """
    if ex.status != STATUS_QUEUED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "not_cancelable",
                "message": f"execution already {ex.status}",
            },
        )
    run_dispatcher.request_cancel(ex.id)
    if not run_dispatcher.has_live_fanout(ex.id):
        ex.status = STATUS_CANCELED
        ex.finished_at = utcnow()
        await session.commit()
        await session.refresh(ex)
    return execution_store.execution_out(ex)
