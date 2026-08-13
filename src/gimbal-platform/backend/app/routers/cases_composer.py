"""Case endpoints (V3 composer) + nested DataSet create.

Path layout (per docs/PLATFORM-SCENARIO-COMPOSER-API.md §4.8–4.11 +
the create-data-set sibling at §4.14):

* ``POST   /api/cases``                                 — create
* ``GET    /api/cases?scenarioId&q&system&module``     — list
* ``GET    /api/cases/{caseId}``                       — detail
* ``PATCH  /api/cases/{caseId}``                       — partial update
* ``DELETE /api/cases/{caseId}``                       — cascade-delete
* ``POST   /api/cases/{caseId}/data-sets``             — create data set

**Routing co-existence with the legacy ``app.routers.cases``:** the
legacy router has GET/PATCH/DELETE on ``/{case_id:path}`` which would
otherwise shadow ours.  We restrict matching to the V3 ``case-`` id
pattern via a Starlette custom path-converter
(``register_url_convertor("v3_case_id", ...)``) — see ``main.py``.
Anything else (``mine``, ``public``, ``upload``, free-form legacy
ids) falls through to the legacy router, which is registered after
this one.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.composer_case import ComposerCase
from ..schemas.scenario_composer import (
    Case,
    CasePatch,
    DataSet,
    DataSetDraft,
)
from ..services import case_store, data_set_store
from sqlalchemy import select


router = APIRouter(prefix="/cases", tags=["cases-composer"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


# ── helpers ────────────────────────────────────────────────────────
async def _load_scenario(db: AsyncSession, scenario_id: str):
    """Load a scenario row or 404.  Used by the create-case handler to
    enforce parent-scenario ownership."""
    from app.models.composer_scenario import ComposerScenario

    res = await db.execute(
        select(ComposerScenario).where(
            ComposerScenario.scenario_id == scenario_id
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"scenario_not_found: {scenario_id}"
        )
    return row


async def _load_case(
    db: AsyncSession, case_id: str
) -> ComposerCase:
    res = await db.execute(
        select(ComposerCase).where(ComposerCase.case_id == case_id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"case_not_found: {case_id}"
        )
    return row


def _require_owner(
    user: CurrentUser, row: ComposerCase
) -> None:
    """403 unless the user is the creator or an admin."""
    owner_name = row.created_by or ""
    user_name = user.display_name or user.username
    if not user.is_admin and user_name != owner_name:
        raise HTTPException(
            status_code=403,
            detail="not_owner: only the case's creator (or admin) can modify this case",
        )


# ── case endpoints ─────────────────────────────────────────────────
@router.post("", response_model=Case, status_code=status.HTTP_201_CREATED, operation_id="composer_create_case")
async def create_case(
    user: CurrentUser, db: DbSession, body: Case
) -> Case:
    """Create a new Case.

    Authorisation: a case inherits ownership from its parent scenario, so
    the caller must own the scenario (or be an admin).  Prevents a
    logged-in user from creating cases under another user's scenario.
    """
    # Load the parent scenario to verify ownership.
    scen = await _load_scenario(db, body.scenario_id)
    user_name = user.display_name or user.username
    if not user.is_admin and scen.owner and scen.owner != user_name:
        raise HTTPException(
            status_code=403,
            detail="not_owner: only the scenario's owner (or admin) can create cases under it",
        )
    try:
        return await case_store.create(
            db, body, created_by=user.display_name or user.username
        )
    except ValueError as e:
        msg = str(e)
        code = msg.split(":", 1)[0]
        if code == "case_id_exists":
            raise HTTPException(status_code=409, detail=msg)
        if code == "scenario_not_found":
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)


@router.get("", response_model=list[Case], operation_id="composer_list_cases")
async def list_cases(
    user: CurrentUser,
    db: DbSession,
    scenarioId: str | None = None,
    q: str | None = None,
    system: str | None = None,
    module: str | None = None,
) -> list[Case]:
    return await case_store.list_cases(
        db,
        scenario_id=scenarioId,
        q=q,
        system=system,
        module=module,
    )


# NOTE on routing: the legacy ``app.routers.cases`` has
# ``GET/PATCH/DELETE /{case_id:path}`` which would shadow these routes.
# We use a custom Starlette path-converter (``v3_case_id``) registered
# in ``main.py`` to restrict matching to the V3 ``case-`` pattern.
# Anything else falls through to the legacy router registered after
# this one.


@router.get("/{case_id:v3_case_id}", response_model=Case, operation_id="composer_get_case")
async def get_case(
    user: CurrentUser,
    db: DbSession,
    case_id: str,
) -> Case:
    try:
        return await case_store.get(db, case_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).split(": ", 1)[-1])


@router.patch("/{case_id:v3_case_id}", response_model=Case, operation_id="composer_patch_case")
async def patch_case(
    user: CurrentUser,
    db: DbSession,
    case_id: str,
    body: CasePatch,
) -> Case:
    row = await _load_case(db, case_id)
    _require_owner(user, row)
    try:
        return await case_store.patch(db, case_id, body)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).split(": ", 1)[-1])


@router.delete("/{case_id:v3_case_id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="composer_delete_case")
async def delete_case(
    user: CurrentUser,
    db: DbSession,
    case_id: str,
) -> None:
    row = await _load_case(db, case_id)
    _require_owner(user, row)
    try:
        await case_store.delete(db, case_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).split(": ", 1)[-1])


# ── data-set create (POST /api/cases/{caseId}/data-sets) ──────────
@router.post(
    "/{case_id:v3_case_id}/data-sets",
    response_model=DataSet,
    status_code=status.HTTP_201_CREATED,
    operation_id="composer_create_data_set",
)
async def create_data_set(
    user: CurrentUser,
    db: DbSession,
    case_id: str,
    body: DataSetDraft,
) -> DataSet:
    row = await _load_case(db, case_id)
    _require_owner(user, row)
    try:
        return await data_set_store.create(db, case_id, body)
    except ValueError as e:
        msg = str(e)
        code = msg.split(":", 1)[0]
        if code == "case_not_found":
            raise HTTPException(status_code=404, detail=msg)
        if code == "inconsistent_row_columns":
            raise HTTPException(status_code=422, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
