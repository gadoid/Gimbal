"""Case endpoints (V3 composer) + nested DataSet create.

Path layout (per docs/PLATFORM-SCENARIO-COMPOSER-API.md §4.8–4.11 +
the create-data-set sibling at §4.14):

* ``POST   /api/cases``                                 — create
* ``GET    /api/cases?scenarioId&q&system&module``     — list
* ``GET    /api/cases/{caseId}``                       — detail
* ``PATCH  /api/cases/{caseId}``                       — partial update
* ``DELETE /api/cases/{caseId}``                       — cascade-delete
* ``POST   /api/cases/{caseId}/data-sets``             — create data set

The ``/{case_id}`` routes use the ``v3_case_id`` custom path-converter
(registered in ``main.py``) so only composer-style ids (``case-…`` /
``sc-…-case-…``) match — other segments simply 404 instead of being
swallowed by a catch-all.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ._ownership import can_read_scenario, ensure_owner
from ._error_mapping import key_error_404, value_error_http
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
    ensure_owner(
        user,
        row.created_by,
        "not_owner: only the case's creator (or admin) can modify this case",
    )


async def _require_case_reader(
    db: AsyncSession, user: CurrentUser, row: ComposerCase
) -> None:
    """用例读权限跟随父场景(404 而非 403,不泄露存在性)。"""
    scen = await _load_scenario(db, row.scenario_id)
    if not can_read_scenario(
        user,
        scen.owner,
        owner_id=scen.owner_id,
        visibility=scen.visibility or "private",
    ):
        raise HTTPException(
            status_code=404, detail=f"case_not_found: {row.case_id}"
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
    # Load the parent scenario to verify ownership.  Empty owner =
    # locked (canonical rule in _ownership).
    scen = await _load_scenario(db, body.scenario_id)
    ensure_owner(
        user,
        scen.owner,
        "not_owner: only the scenario's owner (or admin) can create cases under it",
        owner_id=scen.owner_id,
    )
    try:
        return await case_store.create(
            db, body, created_by=user.display_name or user.username
        )
    except ValueError as e:
        raise value_error_http(e, {"case_id_exists": 409, "scenario_not_found": 404})


@router.get("", response_model=list[Case], operation_id="composer_list_cases")
async def list_cases(
    user: CurrentUser,
    db: DbSession,
    scenarioId: str | None = None,
    q: str | None = None,
    system: str | None = None,
    module: str | None = None,
) -> list[Case]:
    """读侧收紧:用例可见性跟随父场景(admin 全量;public + 自己的)。"""
    from app.models.composer_scenario import ComposerScenario as _CS

    readable_ids = {
        r.scenario_id
        for r in (
            await db.execute(
                select(
                    _CS.scenario_id,
                    _CS.owner,
                    _CS.owner_id,
                    _CS.visibility,
                )
            )
        )
        if can_read_scenario(
            user, r.owner, owner_id=r.owner_id, visibility=r.visibility or "private"
        )
    }
    cases = await case_store.list_cases(
        db,
        scenario_id=scenarioId,
        q=q,
        system=system,
        module=module,
    )
    return [c for c in cases if c.scenario_id in readable_ids]


# NOTE on routing: we use a custom Starlette path-converter
# (``v3_case_id``, registered in ``main.py``) to restrict ``/{case_id}``
# matching to the composer id pattern (``case-`` / ``sc-`` prefixes).


@router.get("/{case_id:v3_case_id}", response_model=Case, operation_id="composer_get_case")
async def get_case(
    user: CurrentUser,
    db: DbSession,
    case_id: str,
) -> Case:
    row = await _load_case(db, case_id)
    await _require_case_reader(db, user, row)
    try:
        return await case_store.get(db, case_id)
    except KeyError as e:
        raise key_error_404(e)


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
        raise key_error_404(e)


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
        raise key_error_404(e)


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
        raise value_error_http(e, {"case_not_found": 404, "inconsistent_row_columns": 422})
