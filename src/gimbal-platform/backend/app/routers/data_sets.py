"""DataSet endpoints (V3 composer) — create / read / update / delete.

Path layout:

* ``GET    /api/data-sets?scenarioId=``         — list summaries
* ``GET    /api/data-sets/{datasetId}``         — full row
* ``PUT    /api/data-sets/{datasetId}``         — full update
* ``DELETE /api/data-sets/{datasetId}``         — hard delete
* ``POST   /api/scenarios/{scenarioId}/data-sets`` — **create**

Ownership: writes require the row's parent scenario's owner to match
the caller (``owner_id`` is authoritative) or ``user.is_admin``.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ._ownership import ensure_owner
from ._error_mapping import key_error_404, value_error_http
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import DataSet, DataSetDraft, DataSetSummary
from ..services import data_set_store


router = APIRouter(prefix="/data-sets", tags=["data-sets"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


# ── helpers ────────────────────────────────────────────────────────
async def _load_scenario(
    db: AsyncSession, scenario_id: str
) -> ComposerScenario | None:
    res = await db.execute(
        select(ComposerScenario).where(
            ComposerScenario.scenario_id == scenario_id
        )
    )
    return res.scalar_one_or_none()


async def _require_scenario_owner(
    db: AsyncSession, user: CurrentUser, scenario_id: str
) -> ComposerScenario:
    """Load the scenario, verify ownership, and return the row.

    Returns 404 on miss (no existence leak).  403 when the caller is
    neither owner nor admin.
    """
    scen = await _load_scenario(db, scenario_id)
    if scen is None:
        raise HTTPException(
            status_code=404, detail=f"scenario_not_found: {scenario_id}"
        )
    ensure_owner(
        user,
        scen.owner,
        "not_owner: only the scenario's owner (or admin) can manage its data sets",
        owner_id=scen.owner_id,
    )
    return scen


async def _require_dataset_owner(
    db: AsyncSession, user: CurrentUser, dataset_id: str
) -> ComposerDataSet:
    """Load the dataset, verify ownership via its parent scenario.

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
    await _require_scenario_owner(db, user, row.scenario_id)
    return row


# ── endpoints ─────────────────────────────────────────────────────
@router.get("", response_model=list[DataSetSummary])
async def list_data_sets(
    user: CurrentUser,
    db: DbSession,
    scenarioId: str | None = None,
) -> list[DataSetSummary]:
    """List summaries scoped to the caller.

    Data-set rows are business parameter matrices — listing every user's
    data (the previous behaviour) is a cross-user disclosure, so non-admin
    callers only see data-sets whose parent scenario they own.
    """
    if user.is_admin:
        return await data_set_store.list_summaries(db, scenario_id=scenarioId)
    own_ids = set(
        (
            await db.execute(
                select(ComposerScenario.scenario_id).where(
                    ComposerScenario.owner_id == user.id
                )
            )
        )
        .scalars()
        .all()
    )
    # Legacy rows (owner_id == 0) fall back to the owner display-name
    # snapshot so pre-migration scenarios remain visible to their
    # creators.
    own_names = {user.display_name or user.username}
    name_rows = (
        (
            await db.execute(
                select(ComposerScenario.scenario_id).where(
                    ComposerScenario.owner_id == 0,
                    ComposerScenario.owner.in_(own_names),
                )
            )
        )
        .scalars()
        .all()
    )
    own_ids.update(name_rows)
    if not own_ids:
        return []
    summaries = await data_set_store.list_summaries(db, scenario_id=None)
    out = [s for s in summaries if s.scenario_id in own_ids]
    if scenarioId is not None:
        out = [s for s in out if s.scenario_id == scenarioId]
    return out


@router.get("/{dataset_id}", response_model=DataSet)
async def get_data_set(
    user: CurrentUser, db: DbSession, dataset_id: str
) -> DataSet:
    # Same ownership rule as the write endpoints: full rows are business
    # data, not a shared library.
    await _require_dataset_owner(db, user, dataset_id)
    try:
        return await data_set_store.get(db, dataset_id)
    except KeyError as e:
        raise key_error_404(e)


@router.put("/{dataset_id}", response_model=DataSet)
async def put_data_set(
    user: CurrentUser,
    db: DbSession,
    dataset_id: str,
    body: DataSetDraft,
) -> DataSet:
    await _require_dataset_owner(db, user, dataset_id)
    try:
        return await data_set_store.update(db, dataset_id, body)
    except KeyError as e:
        raise key_error_404(e)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_set(
    user: CurrentUser, db: DbSession, dataset_id: str
) -> None:
    await _require_dataset_owner(db, user, dataset_id)
    try:
        await data_set_store.delete(db, dataset_id)
    except KeyError as e:
        raise key_error_404(e)


# ── create (scenario-nested path) ──────────────────────────────────
# Kept in this module (not scenarios.py) so all dataset CRUD lives in
# one place; the scenarios router's ``/{scenario_id}`` catch-all would
# otherwise shadow it.
create_router = APIRouter(tags=["data-sets"])


@create_router.post(
    "/scenarios/{scenario_id}/data-sets",
    response_model=DataSet,
    status_code=status.HTTP_201_CREATED,
)
async def create_data_set(
    user: CurrentUser,
    db: DbSession,
    scenario_id: str,
    body: DataSetDraft,
) -> DataSet:
    await _require_scenario_owner(db, user, scenario_id)
    try:
        return await data_set_store.create(db, scenario_id, body)
    except ValueError as e:
        raise value_error_http(e)
