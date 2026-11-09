"""DataSet endpoints (V3 composer) — create / read / update / delete.

Path layout:

* ``GET    /api/data-sets?scenarioId=``         — list summaries
* ``GET    /api/data-sets/{datasetId}``         — full row
* ``PUT    /api/data-sets/{datasetId}``         — full update
* ``DELETE /api/data-sets/{datasetId}``         — delete
* ``POST   /api/scenarios/{scenarioId}/data-sets`` — **create**

(DELETE 随数据集编辑器重做回归(C9)。)

Ownership: writes require the row's parent scenario's owner to match
the caller (``owner_id`` is authoritative) or ``user.is_admin``.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
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

    Returns 404 on miss (no existence leak) and when the caller can't
    read the scenario either (authz W3:读判含 ref —— 完全不可见才 404,
    引用者/公共读者可读 ⇒ 403,不与可读性自相矛盾)。
    """
    from ._ownership import can, can_read_scenario_row

    scen = await _load_scenario(db, scenario_id)
    if scen is None:
        raise not_found_404("scenario", scenario_id)
    if not await can_read_scenario_row(db, user, scen):
        raise not_found_404("scenario", scenario_id)
    # S1.2:数据集随父场景 —— 写权 = 父场景 can(write)(owner ∨ 项目
    # 成员 ∨ 公共维护者),不再属主单判
    if not await can(db, user, "scenario", "write", scen):
        raise HTTPException(
            403,
            detail="not_owner: only the scenario's owner (or a project "
                   "member / maintainer) can manage its data sets")
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
    data would be a cross-user disclosure, so callers only see data-sets
    whose parent scenario they own or hold a share-ref into
    (P2 §7.4 引用闭包). authz W3: super_admin 全量分支删除 ——
    admin 与普通用户同镜头,排查走审计。
    """
    # S7.4:引用闭包随 share_refs 退役 —— 数据集只随自己场景
    owned = await scenario_store.owned_scenario_ids(db, user)
    own_ids = set(owned)
    if scenarioId is not None:
        # Scope to the requested scenario (still visibility-filtered).
        own_ids = own_ids & {scenarioId}
    # Ownership filter pushed down as a SQL IN (was: full list + Python filter).
    # authz W6:引用闭包读者(非属主)的预览剥敏感列
    return await data_set_store.list_summaries(
        db, scenario_ids=own_ids, owned_ids=set(owned))


@router.get("/{dataset_id}", response_model=DataSet)
async def get_data_set(
    user: CurrentUser, db: DbSession, dataset_id: str
) -> DataSet:
    # P2:读走引用闭包(§7.4 —— 属主/admin/引用者可读,与列表同口径);
    # 写端点仍走 _require_dataset_owner。
    row = await data_set_store.get_row(db, dataset_id)
    if row is None:
        raise not_found_404("data_set", dataset_id)
    scen = await _load_scenario(db, row.scenario_id)
    from ._ownership import can_read_scenario_row
    if scen is None or not await can_read_scenario_row(db, user, scen):
        raise not_found_404("data_set", dataset_id)
    try:
        # authz W6:非属主读剥敏感列(原件不动)
        return await data_set_store.get(
            db, dataset_id, redact=scenario_store.is_foreign_viewer(
                user.id, scen.owner_id))
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
        raise value_error_http(e, {"undeclared_var": 422,
                                   "undeclared_slot": 422})


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
        raise value_error_http(
            e, {"scenario_not_found": 404, "dataset_id_exists": 409,
                "undeclared_var": 422, "undeclared_slot": 422}
        )
