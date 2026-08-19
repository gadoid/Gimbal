"""Executions API — 共享读侧 + 行/单删除。

P4 起 V1 子进程创建链路(POST /executions 与 rerun,经 executor.py 的
gimbal CLI 子进程)已退役;V3 场景执行的创建入口是 ``POST /api/runs``
(run_dispatcher → gimbal HTTP service)。本路由只剩两个引擎共用的
executions/exec_runs 表的读侧与删除。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Request, status
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, get_owned_execution
from ..models import ExecRun, Execution
from ..schemas.execution import (
    ExecRunOut,
    ExecutionDetailOut,
    ExecutionListOut,
    ExecutionOut,
)
from ..services.log_hub import EndEvent, KeepAlive, RunLogLine, hub

router = APIRouter(prefix="/executions", tags=["executions"])


DbSession = Annotated[AsyncSession, Depends(get_db)]
OwnedExecution = Annotated[Execution, Depends(get_owned_execution)]


def _exec_out(e: Execution) -> ExecutionOut:
    return ExecutionOut(
        id=e.id,
        case_id=e.case_id,
        status=e.status,
        total_runs=e.total_runs,
        passed=e.passed,
        failed=e.failed,
        started_at=e.started_at,
        finished_at=e.finished_at,
        config=e.config_json or {},
    )


def _run_out(r: ExecRun) -> ExecRunOut:
    return ExecRunOut.model_validate(r)


# ── list ────────────────────────────────────────────────────────
@router.get("", response_model=ExecutionListOut)
async def list_executions(
    user: CurrentUser, session: DbSession
) -> ExecutionListOut:
    rows = (
        (
            await session.execute(
                select(Execution)
                .where(Execution.owner_id == user.id)
                .order_by(Execution.id.desc())
            )
        )
        .scalars()
        .all()
    )
    items = [_exec_out(e) for e in rows]
    return ExecutionListOut(items=items, total=len(items))


# ── detail (with runs) ─────────────────────────────────────────
@router.get("/{execution_id}", response_model=ExecutionDetailOut)
async def get_execution(
    ex: OwnedExecution,
    session: DbSession,
) -> ExecutionDetailOut:
    runs = (
        (
            await session.execute(
                select(ExecRun)
                .where(ExecRun.execution_id == ex.id)
                .order_by(ExecRun.idx.asc())
            )
        )
        .scalars()
        .all()
    )
    return ExecutionDetailOut(
        id=ex.id,
        case_id=ex.case_id,
        status=ex.status,
        total_runs=ex.total_runs,
        passed=ex.passed,
        failed=ex.failed,
        started_at=ex.started_at,
        finished_at=ex.finished_at,
        config=ex.config_json or {},
        runs=[_run_out(r) for r in runs],
    )


# ── list runs (for polling) ────────────────────────────────────
@router.get("/{execution_id}/runs", response_model=list[ExecRunOut])
async def list_runs(
    ex: OwnedExecution,
    session: DbSession,
) -> list[ExecRunOut]:
    rows = (
        (
            await session.execute(
                select(ExecRun)
                .where(ExecRun.execution_id == ex.id)
                .order_by(ExecRun.idx.asc())
            )
        )
        .scalars()
        .all()
    )
    return [_run_out(r) for r in rows]


# ── report (stream HTML) ──────────────────────────────────────
@router.get("/{execution_id}/report/{idx}")
async def get_report(
    execution_id: Annotated[int, PathParam(ge=1)],
    idx: Annotated[int, PathParam(ge=1)],
    ex: OwnedExecution,
    session: DbSession,
):
    # Locate run by (execution_id, idx)
    run = (
        await session.execute(
            select(ExecRun).where(
                ExecRun.execution_id == ex.id, ExecRun.idx == idx
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    if not run.report_path:
        raise HTTPException(
            status_code=404, detail="report not yet available or not generated"
        )

    p = Path(run.report_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="report file missing")
    return FileResponse(p, media_type="text/html")


# ── run log (CLI + stdout + stderr) ────────────────────────────
@router.get("/{execution_id}/runs/{run_id}/log")
async def get_run_log(
    execution_id: Annotated[int, PathParam(ge=1)],
    run_id: Annotated[int, PathParam(ge=1)],
    ex: OwnedExecution,
    session: DbSession,
):
    """Stream the run's CLI + stdout + stderr log file as text/plain.

    Empty body (200) if the run is still pending/running and the log
    hasn't been written yet — the frontend renders a hint in that case.
    """
    run = await session.get(ExecRun, run_id)
    if run is None or run.execution_id != ex.id:
        raise HTTPException(status_code=404, detail="run not found")

    if not run.log_path:
        return PlainTextResponse(
            "(log not yet available — run is still pending or running)\n",
            media_type="text/plain; charset=utf-8",
        )
    p = Path(run.log_path)
    if not p.exists():
        # Reconstruct from the row when the disk file is gone (e.g. tmp cleared).
        if run.command_line:
            body = (
                f"# log file {p} missing on disk — "
                "showing reconstructed summary\n"
                f"command:\n{run.command_line}\n"
                f"exit_code: {run.exit_code}\n"
            )
            return PlainTextResponse(body, media_type="text/plain; charset=utf-8")
        raise HTTPException(status_code=404, detail="log file missing")
    return PlainTextResponse(
        p.read_text(encoding="utf-8", errors="replace"),
        media_type="text/plain; charset=utf-8",
    )


# ── SSE log stream ───────────────────────────────────────────
@router.get("/{execution_id}/runs/{run_id}/log/stream")
async def stream_run_log(
    execution_id: Annotated[int, PathParam(ge=1)],
    run_id: Annotated[int, PathParam(ge=1)],
    request: Request,
    ex: OwnedExecution,
    session: DbSession,
):
    """Stream this run's stdout/stderr line-by-line as Server-Sent Events.

    Frames:

    * ``event: stdout`` / ``event: stderr`` — ``data: {"seq": <int>, "text": "<line>\\n"}``
    * ``event: end`` — ``data: {"exit_code": <int>}`` (terminal)
    * Heartbeat comment (``: keep-alive\\n\\n``) every 15s with no output,
      so reverse proxies don't drop the connection.

    Authentication: the JWT is read from the ``Authorization`` header
    (same as every other endpoint).  The frontend uses ``fetch`` +
    ``ReadableStream`` rather than the native ``EventSource`` API so we
    keep header-based auth.  See ``frontend/src/api/executions.ts``.
    """
    run = await session.get(ExecRun, run_id)
    if run is None or run.execution_id != ex.id:
        raise HTTPException(status_code=404, detail="run not found")

    # Parse Last-Event-ID for resume support.  Browsers send this
    # automatically on EventSource reconnect; we accept it on the
    # fetch-based path too (the client passes it explicitly).
    last_event_id_raw = request.headers.get("Last-Event-ID", "0")
    try:
        last_event_id = max(0, int(last_event_id_raw))
    except ValueError:
        last_event_id = 0

    channel = hub.get_or_create(execution_id, run_id)
    loop = asyncio.get_running_loop()
    sub_q, replay, is_done = channel.subscribe(loop)

    async def event_gen():
        try:
            # Replay any history the channel already has, but skip lines
            # whose seq is <= Last-Event-ID so a reconnected client
            # doesn't see duplicates.
            for line in replay:
                if last_event_id and line.seq <= last_event_id:
                    continue
                yield line.to_sse()
            if is_done:
                # Process finished before we subscribed — synthesize
                # an EndEvent so the client knows to stop reconnecting.
                ch_stats = channel.stats()
                yield EndEvent(
                    exit_code=ch_stats.get("exit_code") or 0,
                    seq=channel.next_seq(),
                ).to_sse()
                return

            while True:
                if await request.is_disconnected():
                    return
                try:
                    item = await asyncio.wait_for(sub_q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield KeepAlive().to_sse()
                    continue
                if isinstance(item, EndEvent):
                    yield item.to_sse()
                    return
                if isinstance(item, RunLogLine):
                    if last_event_id and item.seq <= last_event_id:
                        continue  # already delivered before disconnect
                    yield item.to_sse()
        finally:
            channel.unsubscribe(sub_q)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # nginx: do not buffer
            "Connection": "keep-alive",
        },
    )


# ── single-run delete (Spec-2-7) ───────────────────────────────
@router.delete(
    "/{execution_id}/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_run(
    execution_id: Annotated[int, PathParam(ge=1)],
    run_id: Annotated[int, PathParam(ge=1)],
    ex: OwnedExecution,
    session: DbSession,
) -> None:
    run = await session.get(ExecRun, run_id)
    if run is None or run.execution_id != ex.id:
        raise HTTPException(status_code=404, detail="run not found")
    # Counter delta: only completed runs (passed/failed) had a counter
    # increment at _run_one completion; pending/running rows never did.
    # Use atomic ``MAX(0, col - 1)`` UPDATEs so a concurrent rerun
    # doing ``passed += 1`` doesn't clobber the decrement.
    if run.status == "passed":
        await session.execute(
            text(
                "UPDATE executions SET passed = MAX(0, passed - 1) "
                "WHERE id = :eid"
            ),
            {"eid": ex.id},
        )
    elif run.status == "failed":
        await session.execute(
            text(
                "UPDATE executions SET failed = MAX(0, failed - 1) "
                "WHERE id = :eid"
            ),
            {"eid": ex.id},
        )
    # total_runs counts row presence; deleting always decrements.
    await session.execute(
        text(
            "UPDATE executions SET total_runs = MAX(0, total_runs - 1) "
            "WHERE id = :eid"
        ),
        {"eid": ex.id},
    )
    await session.delete(run)
    await session.commit()


# ── delete ─────────────────────────────────────────────────────
@router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution(
    ex: OwnedExecution,
    session: DbSession,
) -> None:
    # SQLite runs with FK enforcement OFF (aiosqlite default, no PRAGMA),
    # so the schema's ON DELETE CASCADE never fires — delete the child
    # run rows explicitly or they're orphaned forever.
    await session.execute(delete(ExecRun).where(ExecRun.execution_id == ex.id))
    await session.delete(ex)
    await session.commit()