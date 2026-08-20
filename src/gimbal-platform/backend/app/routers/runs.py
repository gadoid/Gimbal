"""POST /api/runs — trigger a Scenario run (V3 composer).

Thin wrapper around :func:`app.services.run_dispatcher.dispatch_run`.
Creates a Spec-2 ``Execution`` row, spawns a background task that fans
out per (dataset × row) and POSTs each composed Scenario to Plate's
``/api/scenario/action/convert``.

The former Case layer was dissolved — the run recipe (env / dataSetIds /
auths / retry / …) lives entirely in ``RunRequest``.

Error mapping (per the agreed run-failure semantics):
* scenario / env / data_set missing → 404
* no data sets selected       → 409
* plate unavailable mid-fan-out → the Execution row is marked
  ``status='failed'`` and the JSONL log records the error, but the
  response is **201 with runId** (so the UI can navigate to
  ``/executions`` and see what happened).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ._ownership import ensure_owner
from ..models.composer_scenario import ComposerScenario
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
    # Access check (mirrors V1 executions create / composer ownership):
    # dispatching a run has real side effects (subprocesses hitting the
    # configured env services), so it must not be open to every member —
    # only the scenario's owner (or an admin) may run it.
    scen = (
        await db.execute(
            select(ComposerScenario).where(
                ComposerScenario.scenario_id == body.scenario_id
            )
        )
    ).scalar_one_or_none()
    if scen is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "scenario_not_found",
                "message": f"scenario not found: {body.scenario_id}",
            },
        )
    # owner_id is authoritative; legacy rows (owner_id == 0) fall back
    # to matching the owner display-name snapshot.
    ensure_owner(
        user,
        scen.owner,
        {
            "code": "not_owner",
            "message": "only the scenario's owner (or admin) can run this scenario",
        },
        owner_id=scen.owner_id,
    )
    try:
        return await run_dispatcher.dispatch_run(
            db,
            user_id=user.id,
            req=body,
            preloaded_scenario=scen,  # 已为归属检查加载,不再二次查询
        )
    except run_dispatcher._NotFound as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except run_dispatcher._Conflict as e:
        raise HTTPException(status_code=409, detail={"code": e.code, "message": e.message})
