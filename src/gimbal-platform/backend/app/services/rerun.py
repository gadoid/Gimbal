"""Single-run rerun orchestration (extracted from routers/executions.py).

Owns the full B-model rerun flow:
1. INSERT a fresh ``ExecRun`` row (``idx = max(idx) + 1``, full history
   preserved) with IntegrityError retry under concurrent reruns.
2. Atomically bump ``Execution.total_runs`` (``+ 1`` SQL UPDATE).
3. Render the execution YAML for the new run id and drive ``_run_one``.

The router stays a thin transport layer; this module is the single place
that knows how a rerun is composed.

NOTE (design debt, see DEFERRED.md): the subprocess runs to completion
inside the caller's request (synchronous semantics — the HTTP response
reflects the post-run row state, which the frontend relies on).  Moving
to a background task + polling would change the API contract and is
deferred.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models import ExecRun, Execution
from .executor import _run_one, _write_temp_yaml, render_execution_yaml


async def rerun_single_run(
    session: AsyncSession, ex: Execution, run_id: int
) -> ExecRun:
    """Insert + execute a fresh attempt for ``run_id`` under ``ex``.

    Raises HTTPException (404 run / 404 case vanished / 422 render
    failed) — the router maps nothing further.
    """
    src_run = await session.get(ExecRun, run_id)
    if src_run is None or src_run.execution_id != ex.id:
        raise HTTPException(status_code=404, detail="run not found")

    # Two concurrent reruns could both compute the same next_idx from
    # ``SELECT MAX(idx)`` and then both INSERT — a logical duplicate.
    # Mitigations:
    #   1. UNIQUE (execution_id, idx) constraint on exec_runs — the
    #      second INSERT raises IntegrityError.
    #   2. On IntegrityError, retry once with a freshly-computed idx
    #      (the first rerun's row is now visible to MAX).
    #   3. total_runs is bumped via an atomic ``+ 1`` SQL UPDATE so
    #      the counter doesn't clobber under concurrent writes.
    async def _do_rerun_insert() -> ExecRun:
        max_idx_row = (
            await session.execute(
                select(func.max(ExecRun.idx)).where(ExecRun.execution_id == ex.id)
            )
        ).scalar()
        next_idx = (max_idx_row or 0) + 1
        new_run = ExecRun(execution_id=ex.id, idx=next_idx, status="pending")
        session.add(new_run)
        await session.execute(
            text(
                "UPDATE executions SET total_runs = total_runs + 1 "
                "WHERE id = :eid"
            ),
            {"eid": ex.id},
        )
        await session.commit()
        # ``new_run.id`` and other columns are populated by the INSERT
        # during commit; no separate refresh (it would round-trip again
        # and race with the connection pool under concurrent requests).
        return new_run

    try:
        new_run = await _do_rerun_insert()
    except IntegrityError:
        # Another concurrent rerun stole our idx; refresh and retry once.
        await session.rollback()
        new_run = await _do_rerun_insert()

    report_dir = settings.DATA_DIR / "reports" / f"exec_{ex.id}"
    report_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = report_dir / f"run_{new_run.id}.yaml"
    # Always render fresh — the new run id means the yaml must be
    # regenerated (no chance of clashing with a previous attempt's file).
    cfg: dict[str, Any] = ex.config_json or {}
    try:
        rendered = await render_execution_yaml(
            case_id=ex.case_id,
            owner_id=ex.owner_id,
            cfg=cfg,
            idx=new_run.idx,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case file vanished: {ex.case_id}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"render failed: {e}",
        )
    _write_temp_yaml(rendered, yaml_path)

    await _run_one(
        execution_id=ex.id,
        run_id=new_run.id,
        yaml_path=yaml_path,
        env=cfg.get("env", "dev"),
        report_dir=report_dir,
        # Rerun replays the original execution's config — including step_to
        # so the new attempt honors the same halt-at semantics.
        step_to=cfg.get("step_to"),
    )

    # Re-fetch the new row so the caller's response reflects
    # post-subprocess state (status, exit_code, duration, log_path,
    # command_line).  _run_one commits via its own session.
    await session.refresh(new_run)
    return new_run
