"""DB-backed CRUD for the V3 Scenario Composer Scenario rows.

Mirrors the patterns from ``app/routers/cases.py`` (JSON-file favorites)
and ``app/services/case_loader.py`` (file-backed), but uses SQLAlchemy
async sessions against the existing ``composer_scenarios`` table.

All public methods take an ``AsyncSession`` (or use the default from
``get_db`` via the routers); they never hold module-level state, so
concurrent requests see consistent reads/writes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario
from ..models.composer_case import ComposerCase
from ..models.composer_data_set import ComposerDataSet
from ..schemas.scenario_composer import Scenario, ScenarioDraft, ScenarioMeta, ScenarioStep
from .stars_store import is_starred as stars_is_starred


# ─── write side ───────────────────────────────────────────────────
async def create(
    db: AsyncSession,
    draft: ScenarioDraft,
    *,
    owner: str = "",
) -> Scenario:
    """Insert a new scenario.  Raises ValueError on duplicate scenarioId.

    Server-side override: ``owner`` is always taken from the router's
    ``owner`` parameter (the authenticated user's display_name), so a
    caller cannot spoof the owner field by sending a different value in
    the request body.
    """
    server_owned = ScenarioMeta.model_validate({
        **draft.meta.model_dump(by_alias=True, mode="json"),
        "owner": owner or draft.meta.owner,
    })
    payload = ScenarioDraft(
        meta=server_owned, steps=draft.steps, caseMeta=draft.case_meta
    ).model_dump(by_alias=True, mode="json")
    row = ComposerScenario(
        scenario_id=server_owned.scenario_id,
        name=server_owned.name,
        description=server_owned.description,
        module=server_owned.module,
        priority=server_owned.priority,
        author=server_owned.author,
        owner=server_owned.owner,
        tags=server_owned.tags,
        system=server_owned.system,
        version=server_owned.version,
        expire=server_owned.expire,
        step_count=len(draft.steps),
        payload=payload,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ValueError(f"scenario_id_exists: {draft.meta.scenario_id}") from e
    await db.refresh(row)
    return await _to_read_shape(db, row)


async def update(
    db: AsyncSession,
    scenario_id: str,
    draft: ScenarioDraft,
    *,
    user_id: int | None = None,
    new_owner: str = "",
) -> Scenario:
    """Replace an existing scenario.  Raises KeyError on miss.

    Refuses to change ``scenarioId`` (the row's primary key in the table
    and the unique identity the rest of the system uses).

    Server-side override: if ``new_owner`` is supplied, it's used in
    place of ``draft.meta.owner`` so the caller can't re-assign the
    scenario to a different user mid-edit.
    """
    row = await _get_row(db, scenario_id)
    if draft.meta.scenario_id != scenario_id:
        raise ValueError("scenario_id_changed: cannot rename scenarioId")
    effective_owner = new_owner or draft.meta.owner or row.owner
    server_owned = ScenarioMeta.model_validate({
        **draft.meta.model_dump(by_alias=True, mode="json"),
        "owner": effective_owner,
    })
    row.name = server_owned.name
    row.description = server_owned.description
    row.module = server_owned.module
    row.priority = server_owned.priority
    row.author = server_owned.author
    row.owner = effective_owner
    row.tags = server_owned.tags
    row.system = server_owned.system
    row.version = server_owned.version
    row.expire = server_owned.expire
    row.step_count = len(draft.steps)
    row.payload = ScenarioDraft(
        meta=server_owned, steps=draft.steps, caseMeta=draft.case_meta
    ).model_dump(by_alias=True, mode="json")
    await db.commit()
    await db.refresh(row)
    return await _to_read_shape(db, row, user_id=user_id)


async def delete(db: AsyncSession, scenario_id: str) -> None:
    """Delete a scenario and cascade its cases + datasets.

    Raises KeyError on miss.  Uses a single transaction so a failure
    mid-cascade rolls everything back.
    """
    row = await _get_row(db, scenario_id)
    # Cascade order: data_sets → cases → scenario (reverse FK).
    case_ids_subq = select(ComposerCase.case_id).where(
        ComposerCase.scenario_id == scenario_id
    )
    await db.execute(
        sa_delete(ComposerDataSet).where(
            ComposerDataSet.case_id.in_(case_ids_subq)
        )
    )
    await db.execute(
        sa_delete(ComposerCase).where(ComposerCase.scenario_id == scenario_id)
    )
    await db.delete(row)
    await db.commit()


async def get(
    db: AsyncSession, scenario_id: str, *, user_id: int | None = None
) -> Scenario:
    row = await _get_row(db, scenario_id)
    return await _to_read_shape(db, row, user_id=user_id)


async def exists(db: AsyncSession, scenario_id: str) -> bool:
    res = await db.execute(
        select(ComposerScenario.scenario_id).where(
            ComposerScenario.scenario_id == scenario_id
        )
    )
    return res.scalar_one_or_none() is not None


# ─── read side ────────────────────────────────────────────────────
async def list_scenarios(
    db: AsyncSession,
    *,
    q: str | None = None,
    system: str | None = None,
    module: str | None = None,
    priority: int | None = None,
    user_id: int | None = None,
) -> list[Scenario]:
    """List scenarios with optional filters.

    ``q`` is a case-insensitive substring against scenarioId / name /
    module / description / tags.  ``system`` is a single-tag match
    (any of the scenario's ``system[]``).  ``priority`` and ``module``
    are exact matches.  ``user_id`` enables per-user ``starred`` flag.
    """
    stmt = select(ComposerScenario).order_by(ComposerScenario.updated_at.desc())
    rows = (await db.execute(stmt)).scalars().all()

    out: list[Scenario] = []
    for r in rows:
        meta = _meta_from_row(r)
        if not _passes_filters(meta, r, q=q, system=system, module=module, priority=priority):
            continue
        scenario = await _to_read_shape(db, r, user_id=user_id)
        out.append(scenario)
    return out


# ─── helpers ──────────────────────────────────────────────────────
async def _get_row(db: AsyncSession, scenario_id: str) -> ComposerScenario:
    res = await db.execute(
        select(ComposerScenario).where(
            ComposerScenario.scenario_id == scenario_id
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise KeyError(f"scenario_not_found: {scenario_id}")
    return row


async def _to_read_shape(
    db: AsyncSession,
    row: ComposerScenario,
    *,
    user_id: int | None = None,
) -> Scenario:
    """Reconstruct the full Scenario response shape from DB row + joins.

    Counts come from aggregate queries; tags come from the row; starred
    is per-user.
    """
    # caseCount
    case_count = (
        await db.execute(
            select(ComposerCase.case_id).where(
                ComposerCase.scenario_id == row.scenario_id
            )
        )
    ).all()
    case_count_n = len(case_count)
    # dataSetCount (sum of rowCount across datasets under those cases)
    data_set_count = 0
    if case_count_n:
        case_ids = [c[0] for c in case_count]
        ds_res = await db.execute(
            select(ComposerDataSet.row_count).where(
                ComposerDataSet.case_id.in_(case_ids)
            )
        )
        data_set_count = sum(int(r[0] or 0) for r in ds_res.all())

    meta = _meta_from_row(row)
    steps = _steps_from_payload(row.payload)
    starred = (
        stars_is_starred(user_id, row.scenario_id)
        if user_id is not None
        else False
    )
    return Scenario(
        meta=meta,
        steps=steps,
        caseCount=case_count_n,
        dataSetCount=data_set_count,
        stepCount=row.step_count or len(steps),
        tags=list(row.tags or []),
        starred=starred,
    )


def _meta_from_row(row: ComposerScenario) -> ScenarioMeta:
    payload = row.payload or {}
    meta_dict = payload.get("meta") or {}
    if meta_dict:
        return ScenarioMeta.model_validate(meta_dict)
    # Fallback: rebuild from column projection.
    return ScenarioMeta(
        scenarioId=row.scenario_id,
        name=row.name,
        description=row.description,
        module=row.module,
        priority=row.priority,
        author=row.author,
        owner=row.owner,
        tags=list(row.tags or []),
        system=list(row.system or ["fin"]),
        version=row.version or "v0.1.0",
        expire=bool(row.expire),
    )


def _steps_from_payload(payload: dict) -> list[ScenarioStep]:
    raw = payload.get("steps") or []
    out: list[ScenarioStep] = []
    for s in raw:
        try:
            out.append(ScenarioStep.model_validate(s))
        except Exception:  # noqa: BLE001  defensive — bad row in payload
            continue
    return out


def _passes_filters(
    meta: ScenarioMeta,
    row: ComposerScenario,
    *,
    q: str | None,
    system: str | None,
    module: str | None,
    priority: int | None,
) -> bool:
    if system and system not in (row.system or []):
        return False
    if module and (row.module or "") != module:
        return False
    if priority is not None and row.priority != priority:
        return False
    if q:
        ql = q.lower()
        haystacks = [
            row.scenario_id or "",
            row.name or "",
            row.module or "",
            row.description or "",
        ]
        haystacks.extend(row.tags or [])
        if not any(ql in (h or "").lower() for h in haystacks):
            return False
    return True
