"""DataSet endpoints (V3 composer) — read / update / delete.

Path layout (per docs/PLATFORM-SCENARIO-COMPOSER-API.md §4.12–4.16):

* ``GET    /api/data-sets?caseId=``       — list summaries
* ``GET    /api/data-sets/{datasetId}``   — full row
* ``PUT    /api/data-sets/{datasetId}``   — full update
* ``DELETE /api/data-sets/{datasetId}``   — hard delete
* ``POST   /api/cases/{caseId}/data-sets`` — **create** (lives in
  :mod:`app.routers.cases_composer` so the prefix matches).

Ownership: writes require the row's parent case's ``created_by`` to
match ``user.display_name`` (or ``user.is_admin``).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.composer_case import ComposerCase
from ..models.composer_data_set import ComposerDataSet
from ..schemas.scenario_composer import DataSet, DataSetDraft, DataSetSummary
from ..services import data_set_store
from sqlalchemy import select


router = APIRouter(prefix="/data-sets", tags=["data-sets"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


# ── helpers ────────────────────────────────────────────────────────
async def _require_owner(
    db: AsyncSession, user: CurrentUser, dataset_id: str
) -> ComposerDataSet:
    """Load the dataset, verify ownership, and return the row.

    Returns 404 on miss (so we don't leak existence of others' data
    sets).  403 when the user is neither owner nor admin.
    """
    res = await db.execute(
        select(ComposerDataSet).where(
            ComposerDataSet.dataset_id == dataset_id
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"data_set_not_found: {dataset_id}"
        )
    case = await db.execute(
        select(ComposerCase).where(ComposerCase.case_id == row.case_id)
    )
    case_row = case.scalar_one_or_none()
    owner_name = case_row.created_by if case_row is not None else ""
    if not user.is_admin and (user.display_name or user.username) != owner_name:
        raise HTTPException(
            status_code=403,
            detail="not_owner: only the case's creator (or admin) can modify this data set",
        )
    return row


# ── endpoints ─────────────────────────────────────────────────────
@router.get("", response_model=list[DataSetSummary])
async def list_data_sets(
    user: CurrentUser,
    db: DbSession,
    caseId: str | None = None,
) -> list[DataSetSummary]:
    """List summaries scoped to the caller.

    Data-set rows are business parameter matrices — listing every user's
    data (the previous behaviour) is a cross-user disclosure, so non-admin
    callers only see data-sets whose parent case they created.
    """
    if user.is_admin:
        return await data_set_store.list_summaries(db, case_id=caseId)
    user_name = user.display_name or user.username
    own_case_ids = set(
        (
            await db.execute(
                select(ComposerCase.case_id).where(
                    ComposerCase.created_by == user_name
                )
            )
        )
        .scalars()
        .all()
    )
    if not own_case_ids:
        return []
    summaries = await data_set_store.list_summaries(db, case_id=None)
    out = [s for s in summaries if s.case_id in own_case_ids]
    if caseId is not None:
        out = [s for s in out if s.case_id == caseId]
    return out


@router.get("/{dataset_id}", response_model=DataSet)
async def get_data_set(
    user: CurrentUser, db: DbSession, dataset_id: str
) -> DataSet:
    # Same ownership rule as the write endpoints: full rows are business
    # data, not a shared library.
    await _require_owner(db, user, dataset_id)
    try:
        return await data_set_store.get(db, dataset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).split(": ", 1)[-1])


@router.put("/{dataset_id}", response_model=DataSet)
async def put_data_set(
    user: CurrentUser,
    db: DbSession,
    dataset_id: str,
    body: DataSetDraft,
) -> DataSet:
    await _require_owner(db, user, dataset_id)
    try:
        return await data_set_store.update(db, dataset_id, body)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).split(": ", 1)[-1])


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_set(
    user: CurrentUser, db: DbSession, dataset_id: str
) -> None:
    await _require_owner(db, user, dataset_id)
    try:
        await data_set_store.delete(db, dataset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).split(": ", 1)[-1])
