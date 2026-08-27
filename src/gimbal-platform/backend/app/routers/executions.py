"""Executions API — 读侧 + 删除(V3)。

V1 子进程创建链路(POST /executions 与 rerun,经 executor.py 的
gimbal CLI 子进程)已退役;V3 场景执行的创建入口是 ``POST /api/runs``
(run_dispatcher → gimbal_launcher 子进程(``gimbal run launch``))。

exec_runs 表(V1 每-run 明细/报告/日志/SSE)已随存量数据清理一并
退役:V3 运行的可观测面是 Execution 计数器 + ``data/runs/*.jsonl``
调度日志(无 API 消费,运维直读文件)。
"""
from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, get_owned_execution
from ..core.timeutil import utcnow
from ..models import Execution
from ..models.execution import (
    STATUS_CANCELED,
    STATUS_QUEUED,
    STATUS_RUNNING,
)
from ..schemas.execution import ExecutionListOut, ExecutionOut, ExecutionRowsOut
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
    scenario_id: Annotated[str | None, Query(max_length=64)] = None,
) -> ExecutionListOut:
    """分页列表(P:此前全量返回,无界)。默认 200 与前端现状兼容。

    ``scenario_id`` 叠加在 owner 过滤之上(前端「上次运行」数据源)。
    """
    base = select(Execution).where(Execution.owner_id == user.id)
    if scenario_id:
        base = base.where(Execution.scenario_id == scenario_id)
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


# ── rows(行级可观测,spec §9.1)─────────────────────────────────
@router.get("/{execution_id}/rows", response_model=ExecutionRowsOut)
async def get_execution_rows(ex: OwnedExecution) -> ExecutionRowsOut:
    """行级状态:活跃执行读 dispatcher 内存 registry,历史执行回放
    JSONL(dispatched+final 两行/row,final 覆盖)。Task 13 前端消费。"""
    return ExecutionRowsOut(items=run_dispatcher.execution_rows(ex.id))


# ── case-artifact(白名单工件,spec §9.1)────────────────────────
# 白名单只有两个文件;case.json 刻意不在列(含明文凭证,无前端消费
# 场景)。stem 严格式校验(无路径分隔符 + 显式拒 `.`/`..`),run 目录
# 按 runId 定位 —— 跨执行读不可能(runId 唯一)。
_CASE_STEM_RE = re.compile(r"[A-Za-z0-9._-]+")
_ARTIFACTS = {"engine-log": "engine.log", "result": "result.json"}


@router.get("/{execution_id}/case-artifact", response_class=PlainTextResponse)
async def get_case_artifact(
    ex: OwnedExecution,
    case: Annotated[str, Query(max_length=128)],
    file: Annotated[str, Query(max_length=32)],
) -> PlainTextResponse:
    """白名单工件:engine.log(引擎日志)/ result.json(步骤级明细)。
    case.json 刻意不暴露 — 含明文凭证,无前端消费场景。Task 13 前端消费。"""
    name = _ARTIFACTS.get(file)
    if name is None or case in {".", ".."} or not _CASE_STEM_RE.fullmatch(case):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "bad_artifact_kind",
                "message": f"file ∈ {sorted(_ARTIFACTS)}",
            },
        )
    run_id = (ex.config_json or {}).get("runId")
    if not run_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "artifact_not_found", "message": name},
        )
    path = run_dispatcher.run_dir(str(run_id)) / case / name
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "artifact_not_found", "message": name},
        )
    return PlainTextResponse(path.read_text(encoding="utf-8"))


# ── scenario-snapshot(执行时场景快照,P-review)────────────────
@router.get("/{execution_id}/scenario-snapshot")
async def get_scenario_snapshot(ex: OwnedExecution) -> dict:
    """执行时的场景 draft 容器({definition, orchestration})原样返回。

    dispatch 同拍快照(见 run_dispatcher._create_execution)— 场景此后
    被编辑不影响本端点内容。原样透传、不经 ScenarioDraft 重校验:快照是
    历史事实,schema 漂移不应让旧快照不可读(与 GET /scenarios/{id}/draft
    的校验语义不同,那是对"活草稿"的校验)。存量行无快照 → 404 带明确
    code(前端据此区分"无快照"与"无权限",两者对用户都呈现为不可导出)。"""
    if not ex.scenario_snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "scenario_snapshot_not_found",
                "message": "该执行早于快照功能上线,无场景快照",
            },
        )
    return ex.scenario_snapshot


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

    可取消态 = queued | running(running 由在飞 fanout 行边界消费);
    无在飞 task 的 queued/running 都是重启僵尸,立即终态化。终态单 409。
    """
    if ex.status not in (STATUS_QUEUED, STATUS_RUNNING):
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
