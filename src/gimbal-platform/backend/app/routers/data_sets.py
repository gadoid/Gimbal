"""DataSet endpoints (V3 composer) — create / read / update.

Path layout:

* ``GET    /api/data-sets?scenarioId=``         — list summaries
* ``GET    /api/data-sets/{datasetId}``         — full row
* ``PUT    /api/data-sets/{datasetId}``         — full update
* ``POST   /api/scenarios/{scenarioId}/data-sets`` — **create**

(DELETE 曾存在但零消费者已移除;数据集随场景删除或由 PUT 覆盖。)

Ownership: writes require the row's parent scenario's owner to match
the caller (``owner_id`` is authoritative) or ``user.is_admin``.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ._ownership import ensure_owner
from ._error_mapping import key_error_404, not_found_404, value_error_http
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import DataSet, DataSetDraft, DataSetSummary
from ..services import data_set_store, scenario_store


router = APIRouter(prefix="/data-sets", tags=["data-sets"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


# ── helpers ────────────────────────────────────────────────────────
async def _load_scenario(
    db: AsyncSession, scenario_id: str
) -> ComposerScenario | None:
    return await scenario_store.get_row(db, scenario_id)


async def _require_scenario_owner(
    db: AsyncSession, user: CurrentUser, scenario_id: str
) -> ComposerScenario:
    """Load the scenario, verify ownership, and return the row.

    Returns 404 on miss (no existence leak).  403 when the caller is
    neither owner nor admin.
    """
    scen = await _load_scenario(db, scenario_id)
    if scen is None:
        raise not_found_404("scenario", scenario_id)
    ensure_owner(
        user,
        scen.owner_id,
        "not_owner: only the scenario's owner (or admin) can manage its data sets",
    )
    return scen


async def _require_dataset_owner(
    db: AsyncSession, user: CurrentUser, dataset_id: str
) -> ComposerDataSet:
    """Load the dataset, verify ownership via its parent scenario.

    Returns 404 on miss (so we don't leak existence of others' data
    sets).  403 when the user is neither owner nor admin.
    """
    row = await data_set_store.get_row(db, dataset_id)
    if row is None:
        raise not_found_404("data_set", dataset_id)
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
    own_ids = await scenario_store.owned_scenario_ids(db, user)
    if scenarioId is not None:
        # Scope to the requested scenario (still ownership-filtered).
        own_ids = own_ids & {scenarioId}
    # Ownership filter pushed down as a SQL IN (was: full list + Python filter).
    return await data_set_store.list_summaries(db, scenario_ids=own_ids)


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
    except ValueError as e:
        raise value_error_http(e, {"undeclared_var": 422})


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
        raise value_error_http(
            e, {"scenario_not_found": 404, "dataset_id_exists": 409,
                "undeclared_var": 422}
        )
