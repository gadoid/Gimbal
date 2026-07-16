"""Executions API (Spec-2 §4.5 E)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Request, status
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import db as db_module
from ..core.config import settings
from ..core.db import get_db
from ..core.deps import CurrentUser, get_owned_execution
from ..models import ExecRun, Execution
from ..schemas.execution import (
    ExecRunOut,
    ExecutionCreateIn,
    ExecutionDetailOut,
    ExecutionListOut,
    ExecutionOut,
)
from ..services.executor import run_execution
from ..services.case_loader import loader
from ..services.log_hub import EndEvent, KeepAlive, RunLogLine, hub

router = APIRouter(prefix="/executions", tags=["executions"])


# Anything queued/running in the DB at startup with no fresh activity in
# the last ``ORPHAN_GRACE_MIN`` is presumed to belong to a worker that
# died (uvicorn --reload restarts, OOM, SIGTERM).  Mark its child runs
# + execution as ``failed`` so /executions doesn't display permanently
# pending rows.
ORPHAN_GRACE_MIN = 5


DbSession = Annotated[AsyncSession, Depends(get_db)]
OwnedExecution = Annotated[Execution, Depends(get_owned_execution)]


async def reconcile_orphan_runs() -> None:
    """Failure-recovery: clear out half-finished runs left by a
    previous worker instance.  Called from app lifespan."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ORPHAN_GRACE_MIN)
    async with db_module.SessionLocal() as session:
        # 1. Stuck child runs (have started_at but no finished_at)
        stuck_runs = (
            await session.execute(
                select(ExecRun)
                .where(
                    ExecRun.status.in_(["pending", "running"]),
                    ExecRun.started_at != None,  # noqa: E711
                    ExecRun.started_at < cutoff,
                )
            )
        ).scalars().all()

        # 2. Orphan executions themselves (no fresh row update from a live worker)
        stuck_execs = (
            await session.execute(
                select(Execution)
                .where(
                    Execution.status.in_(["queued", "running"]),
                    Execution.started_at != None,  # noqa: E711
                    Execution.started_at < cutoff,
                )
            )
        ).scalars().all()

        # DB columns are naive-UTC; use naive ``datetime.utcnow()`` so
        # subtraction with the stored ``started_at`` is consistent.  Both
        # are naive-UTC — no TypeError about offset-aware/naive mix.
        now = datetime.utcnow()
        affected: list[str] = []
        for run in stuck_runs:
            run.status = "failed"
            run.exit_code = run.exit_code if run.exit_code is not None else -1
            run.finished_at = now
            if run.duration_ms is None and run.started_at is not None:
                started = run.started_at
                if started.tzinfo is not None:
                    # Defensive: a tz-aware stored value would also need
                    # ``.replace(tzinfo=None)`` before subtracting.
                    started = started.replace(tzinfo=None)
                run.duration_ms = max(
                    0, int((now - started).total_seconds() * 1000)
                )
            # Synthesize a log_path + command_line so the UI log dialog
            # doesn't 404 on these recovered rows.
            if not run.log_path:
                run.log_path = "recovered-at-startup"
            run.command_line = run.command_line or "(recovered by reconciler)"
            affected.append(f"run#{run.id} (exec={run.execution_id})")

        # Roll up counters on the parent executions whose stuck runs
        # have been reaped.  This re-reads ``passed/failed`` after the
        # updates above and re-derives ``status``/``finished_at``.
        for ex in stuck_execs:
            ex.status = "failed"
            ex.finished_at = now
            affected.append(f"exec#{ex.id}")

        # Also reconcile parent execution counters for runs whose status
        # was patched above but whose Execution row might still show
        # passed/failed short of ``total_runs``.  Without this the UI
        # would render a permanently-stuck "0 / 0 / 5" status badge.
        if stuck_runs:
            exec_ids = {r.execution_id for r in stuck_runs}
            for ex_id in exec_ids:
                ex = await session.get(Execution, ex_id)
                if ex is None or ex.status not in ("queued", "running", "done", "failed"):
                    continue
                # Count actual rows (post-patch) instead of relying on
                # the live counter that was never updated.
                rows = (
                    await session.execute(
                        select(ExecRun).where(ExecRun.execution_id == ex_id)
                    )
                ).scalars().all()
                passed = sum(1 for r in rows if r.status == "passed")
                failed = sum(1 for r in rows if r.status == "failed")
                ex.passed = passed
                ex.failed = failed
                if passed + failed >= ex.total_runs:
                    ex.status = "done" if failed == 0 else "failed"
                    ex.finished_at = ex.finished_at or now

        if affected:
            await session.commit()
            logger.warning(
                "reconcile_orphan_runs: reaped {} row(s): {}",
                len(affected),
                ", ".join(affected[:10]) + (" ..." if len(affected) > 10 else ""),
            )


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


# ── create ──────────────────────────────────────────────────────
@router.post("", response_model=ExecutionOut, status_code=status.HTTP_201_CREATED)
async def create_execution(
    payload: ExecutionCreateIn,
    user: CurrentUser,
    session: DbSession,
) -> ExecutionOut:
    # ``command_line`` override is an authenticated RCE surface — see the
    # security note in ``ExecutionCreateIn``.  Only admins may set it;
    # silently ignored if a non-admin happens to send it (defence in
    # depth — the field validator rejects empty / overlong).
    if payload.command_line is not None and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="command_line override requires admin",
        )

    cfg: dict[str, Any] = {
        "n_runs": payload.n_runs,
        "parallel": payload.parallel,
        "env": payload.env,
        "prefix": payload.prefix,
        "exec_auth_alias": payload.exec_auth_alias,
        "merge_policy": payload.merge_policy,
        # Persisted so rerun can honor the original "no injection" intent;
        # the executor skips credential injection when this is False.
        "inject_credentials": payload.inject_credentials,
    }
    if payload.command_line is not None:
        cfg["command_line"] = payload.command_line
    if payload.step_to is not None:
        # Validate against the case's step count BEFORE writing to DB —
        # this gives the client a precise error (with the actual range)
        # rather than letting the subprocess start and exit early.
        try:
            case_payload = loader.read(payload.case_id)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"case not found: {payload.case_id}",
            )
        steps = case_payload.get("steps") or []
        if not steps:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="case has no steps; step_to cannot be set",
            )
        if payload.step_to >= len(steps):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"step_to={payload.step_to} out of range "
                    f"(case has {len(steps)} steps, indices 0..{len(steps)-1})"
                ),
            )
        cfg["step_to"] = payload.step_to
    ex = Execution(
        case_id=payload.case_id,
        owner_id=user.id,
        status="queued",
        total_runs=payload.n_runs,
        config_json=cfg,
    )
    session.add(ex)
    await session.commit()
    await session.refresh(ex)

    # Pre-create ExecRun rows so polling has IDs immediately
    for idx in range(1, payload.n_runs + 1):
        session.add(ExecRun(execution_id=ex.id, idx=idx, status="pending"))
    await session.commit()

    # Fire the orchestrator in the background. The response returns
    # immediately so the UI can navigate to the live status page.
    asyncio.create_task(_safe_run(ex.id))

    return _exec_out(ex)


async def _safe_run(execution_id: int) -> None:
    try:
        await run_execution(execution_id)
    except Exception as e:
        logger.exception("execution {} crashed: {}", execution_id, e)
        async with db_module.SessionLocal() as session:
            ex = await session.get(Execution, execution_id)
            if ex:
                ex.status = "failed"
                ex.finished_at = datetime.utcnow()
                await session.commit()


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
    # Decrementing when the run was completed keeps the parent's
    # passed/failed aligned with the surviving row set.
    if run.status == "passed":
        ex.passed = max(0, (ex.passed or 0) - 1)
    elif run.status == "failed":
        ex.failed = max(0, (ex.failed or 0) - 1)
    # total_runs counts row presence; deleting always decrements.
    ex.total_runs = max(0, (ex.total_runs or 0) - 1)
    await session.delete(run)
    await session.commit()


# ── single-run rerun (Spec-2-7) ────────────────────────────────
@router.post("/{execution_id}/runs/{run_id}/rerun", response_model=ExecRunOut)
async def rerun_run(
    execution_id: Annotated[int, PathParam(ge=1)],
    run_id: Annotated[int, PathParam(ge=1)],
    ex: OwnedExecution,
    session: DbSession,
) -> ExecRunOut:
    """Re-fire a run by INSERTING a new ExecRun row (B-model semantics).

    Each rerun creates a fresh row with ``idx = max(idx) + 1`` so the
    full history is preserved — failures + retries stay visible.  The
    parent execution's ``total_runs`` grows by 1 per rerun.

    The new row's ``log_path`` / ``report_path`` are derived from the
    fresh ``run_id`` so they don't clobber the previous attempt's
    artifacts.  ``_run_one`` increments ``Execution.passed`` /
    ``Execution.failed`` exactly once per completed attempt — no
    double-counting even when the prior attempt was already passed.
    """
    src_run = await session.get(ExecRun, run_id)
    if src_run is None or src_run.execution_id != ex.id:
        raise HTTPException(status_code=404, detail="run not found")

    from sqlalchemy import func, select

    # Compute next idx from the live set.  Concurrent reruns are rare
    # enough that the worst-case race is a duplicate idx — accepted as
    # a known limitation rather than a hard transactional lock.
    max_idx_row = (
        await session.execute(
            select(func.max(ExecRun.idx)).where(ExecRun.execution_id == ex.id)
        )
    ).scalar()
    next_idx = (max_idx_row or 0) + 1

    new_run = ExecRun(execution_id=ex.id, idx=next_idx, status="pending")
    session.add(new_run)
    ex.total_runs = (ex.total_runs or 0) + 1
    await session.commit()
    await session.refresh(new_run)

    from ..services.executor import _run_one

    report_dir = settings.DATA_DIR / "reports" / f"exec_{execution_id}"
    report_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = report_dir / f"run_{new_run.id}.yaml"
    # Always render fresh — the new run id means the yaml must be
    # regenerated (no chance of clashing with a previous attempt's file).
    from ..services.executor import _write_temp_yaml, render_execution_yaml

    cfg = ex.config_json or {}
    try:
        rendered = await render_execution_yaml(
            case_id=ex.case_id,
            owner_id=ex.owner_id,
            cfg=cfg,
            idx=new_run.idx,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"case file vanished: {ex.case_id}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"render failed: {e}")
    _write_temp_yaml(rendered, yaml_path)

    await _run_one(
        execution_id=execution_id,
        run_id=new_run.id,
        yaml_path=yaml_path,
        env=cfg.get("env", "dev"),
        report_dir=report_dir,
        # Rerun replays the original execution's config — including step_to
        # so the new attempt honors the same halt-at semantics.
        step_to=cfg.get("step_to"),
    )

    # Re-fetch the new row so the response reflects post-subprocess
    # state (status, exit_code, duration, log_path, command_line).
    # _run_one commits via its own session; refresh here hits the DB.
    await session.refresh(new_run)
    return _run_out(new_run)


# ── delete ─────────────────────────────────────────────────────
@router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution(
    ex: OwnedExecution,
    session: DbSession,
) -> None:
    await session.delete(ex)
    await session.commit()