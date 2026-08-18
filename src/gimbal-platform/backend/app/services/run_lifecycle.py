"""Execution-run lifecycle machinery (formerly living in the
``routers/executions`` module).

Owns three concerns that exist *outside* any single HTTP request:

* **Task tracking** — ``spawn_safe_run`` keeps a handle on every
  background orchestrator so the app lifespan can cancel + await
  them on shutdown instead of leaving un-tracked tasks to be killed
  mid-subprocess (orphan ``status='running'`` rows).
* **Shutdown gate** — ``is_shutting_down`` / ``drain_in_flight_runners``
  refuse new spawns and drain in-flight ones during graceful stop.
* **Startup recovery** — ``reconcile_orphan_runs`` marks half-finished
  rows from a previous (dead) worker as failed so /executions doesn't
  display permanently-stuck rows.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import and_, or_, select

from ..core import db as db_module
from ..models import ExecRun, Execution
from .executor import run_execution

# Anything queued/running in the DB at startup with no fresh activity in
# the last ``ORPHAN_GRACE_MIN`` is presumed to belong to a worker that
# died (uvicorn --reload restarts, OOM, SIGTERM).  Mark its child runs
# + execution as ``failed`` so /executions doesn't display permanently
# pending rows.
ORPHAN_GRACE_MIN = 5

# ── in-flight orchestrator tracking ──────────────────────────────
_in_flight_runners: set[asyncio.Task] = set()
_shutting_down: bool = False


def is_shutting_down() -> bool:
    return _shutting_down


def spawn_safe_run(execution_id: int) -> "asyncio.Task | None":
    """Spawn the orchestrator for ``execution_id`` and track the handle.

    Returns ``None`` (without spawning) when the app is shutting down —
    the caller should mark the row as failed and return a structured
    error to the client so the user isn't left waiting on a task
    that will never complete.
    """
    if _shutting_down:
        return None
    task = asyncio.create_task(_safe_run(execution_id))
    _in_flight_runners.add(task)
    task.add_done_callback(_in_flight_runners.discard)
    return task


async def drain_in_flight_runners() -> int:
    """Cancel and await all running orchestrators.  Called from the
    app lifespan teardown.  Returns the number of tasks drained so
    the operator log shows what was in flight at shutdown."""
    global _shutting_down
    _shutting_down = True
    n = len(_in_flight_runners)
    # Kill tracked live subprocesses FIRST: cancelling the awaiting task
    # does not stop the ``asyncio.to_thread`` worker (and its child).
    # Signalling the children unblocks the ``proc.wait()`` inside those
    # threads so the drain below actually completes.
    from .executor import kill_all_live_subprocesses
    killed = kill_all_live_subprocesses()
    if killed:
        logger.info("drain: killed {} live subprocess(es) at shutdown", killed)
    if n == 0:
        return 0
    for t in list(_in_flight_runners):
        t.cancel()
    # Wait for them to finish cancellation; bound so a stuck subprocess
    # can't keep the loop alive forever.  Each ``_safe_run`` already
    # has its own try/except that catches CancelledError; the children
    # were killed above so the threads' ``proc.wait()`` returns promptly.
    await asyncio.gather(*_in_flight_runners, return_exceptions=True)
    return n


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


async def reconcile_orphan_runs() -> None:
    """Failure-recovery: clear out half-finished runs left by a
    previous worker instance.  Called from app lifespan.

    NOTE: single-worker assumption — with multiple uvicorn workers, a
    restarting worker could mark executions still running under another
    live worker as failed. This platform currently runs a single uvicorn
    process; revisit if the deployment model changes.
    """
    # DB columns are naive-UTC — use naive ``utcnow()`` so the SQL
    # comparison is consistent (an aware cutoff serializes with a
    # ``+00:00`` suffix and skews the grace window).
    cutoff = datetime.utcnow() - timedelta(minutes=ORPHAN_GRACE_MIN)
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

        # 2. Orphan executions themselves (no fresh row update from a live worker).
        #    A crash between INSERT (status=queued, started_at=NULL — the
        #    creator doesn't set it) and the executor's first update would
        #    previously leave the row unrecoverable forever: the old filter
        #    required ``started_at IS NOT NULL``. Fall back to ``created_at``
        #    for rows that never started.
        stuck_execs = (
            await session.execute(
                select(Execution)
                .where(
                    Execution.status.in_(["queued", "running"]),
                    or_(
                        and_(
                            Execution.started_at != None,  # noqa: E711
                            Execution.started_at < cutoff,
                        ),
                        and_(
                            Execution.started_at == None,  # noqa: E711
                            Execution.created_at < cutoff,
                        ),
                    ),
                )
            )
        ).scalars().all()

        # 2b. Pending runs that never started (NULL started_at) under a
        #     stuck execution — same gap as above, reaped via the parent.
        if stuck_execs:
            stuck_exec_ids = [ex.id for ex in stuck_execs]
            never_started = (
                await session.execute(
                    select(ExecRun)
                    .where(
                        ExecRun.execution_id.in_(stuck_exec_ids),
                        ExecRun.status == "pending",
                        ExecRun.started_at == None,  # noqa: E711
                    )
                )
            ).scalars().all()
            stuck_runs = list(stuck_runs) + list(never_started)

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
