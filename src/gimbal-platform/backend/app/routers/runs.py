"""POST /api/runs — trigger a Case run (V3 composer).

Thin wrapper around :func:`app.services.run_dispatcher.dispatch_run`.
Creates a Spec-2 ``Execution`` row, spawns a background task that fans
out per (dataset × row) and POSTs each composed Scenario to Plate's
``/api/scenario/action/convert``.

Error mapping (per the agreed run-failure semantics):
* case / env / data_set missing → 404
* no data sets selected       → 409
* plate unavailable mid-fan-out → the Execution row is marked
  ``status='failed'`` and the JSONL log records the error, but the
  response is **201 with runId** (so the UI can navigate to
  ``/executions`` and see what happened).  We only return 502 if
  *validation itself* fails (e.g. case has no scenario) — the runId is
  included in the detail so the toast can still show it.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.composer_case import ComposerCase
from ..schemas.scenario_composer import RunRequest, RunResponse
from ..services import run_dispatcher


router = APIRouter(prefix="/runs", tags=["runs"])


DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def post_run(
    user: CurrentUser,
    db: DbSession,
    body: RunRequest,
) -> RunResponse:
    # Access check (mirrors V1 executions create / composer _require_owner):
    # dispatching a run has real side effects (subprocesses hitting the
    # configured env services), so it must not be open to every member —
    # only the case's creator (or an admin) may run it.
    case = (
        await db.execute(
            select(ComposerCase).where(ComposerCase.case_id == body.case_id)
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "case_not_found", "message": f"case not found: {body.case_id}"},
        )
    owner_name = case.created_by or ""
    user_name = user.display_name or user.username
    if not user.is_admin and user_name != owner_name:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "not_owner",
                "message": "only the case's creator (or admin) can run this case",
            },
        )
    try:
        return await run_dispatcher.dispatch_run(
            db,
            user_id=user.id,
            req=body,
        )
    except run_dispatcher._NotFound as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except run_dispatcher._Conflict as e:
        raise HTTPException(status_code=409, detail={"code": e.code, "message": e.message})
