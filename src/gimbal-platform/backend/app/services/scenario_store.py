"""DB-backed CRUD for the V3 Scenario Composer Scenario rows.

Mirrors the patterns from ``app/routers/cases.py`` (JSON-file favorites)
and ``app/services/case_loader.py`` (file-backed), but uses SQLAlchemy
async sessions against the existing ``composer_scenarios`` table.

All public methods take an ``AsyncSession`` (or use the default from
``get_db`` via the routers); they never hold module-level state, so
concurrent requests see consistent reads/writes.
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario
from ..models.composer_case import ComposerCase
from ..models.composer_data_set import ComposerDataSet
# 删除 ScenarioStep;ScenarioMeta 仍保留(读侧用)
from ..schemas.scenario_composer import (
    Orchestration,
    Scenario,
    ScenarioDraft,
    ScenarioMeta,
)
from .marks_store import stars


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
    def_meta = draft.definition.get("meta") or {}
    scenario_id = draft.definition.get("scenarioId") or def_meta.get("scenarioId") or ""
    server_owned = ScenarioMeta.model_validate({
        **def_meta,
        "scenarioId": scenario_id,
        "owner": owner or def_meta.get("owner", ""),
    })
    # Write the server-owned meta back into the stored definition so the
    # owner override (and any server-side meta normalization) survives a
    # read-back via _meta_from_row, which reads definition.meta.
    stored_definition = {
        **draft.definition,
        "scenarioId": server_owned.scenario_id,
        "meta": server_owned.model_dump(by_alias=True, mode="json"),
    }
    payload = ScenarioDraft(
        definition=stored_definition,
        orchestration=draft.orchestration,
        caseMeta=draft.case_meta,
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
        step_count=len(draft.definition.get("steps") or []),
        payload=payload,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ValueError(f"scenario_id_exists: {scenario_id}") from e
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
    place of ``draft.definition["meta"]["owner"]`` so the caller can't
    re-assign the scenario to a different user mid-edit.
    """
    row = await _get_row(db, scenario_id)
    def_meta = draft.definition.get("meta") or {}
    req_sid = draft.definition.get("scenarioId") or def_meta.get("scenarioId") or ""
    if req_sid != scenario_id:
        raise ValueError("scenario_id_changed: cannot rename scenarioId")
    effective_owner = new_owner or def_meta.get("owner") or row.owner
    server_owned = ScenarioMeta.model_validate({
        **def_meta, "scenarioId": scenario_id, "owner": effective_owner,
    })
    # Write the server-owned meta back into the stored definition so the
    # owner override (and any server-side meta normalization) survives a
    # read-back via _meta_from_row, which reads definition.meta.
    stored_definition = {
        **draft.definition,
        "scenarioId": server_owned.scenario_id,
        "meta": server_owned.model_dump(by_alias=True, mode="json"),
    }
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
    row.step_count = len(draft.definition.get("steps") or [])
    row.payload = ScenarioDraft(
        definition=stored_definition,
        orchestration=draft.orchestration,
        caseMeta=draft.case_meta,
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
    config, resource, orchestration = _extras_from_payload(row.payload)
    starred = (
        stars.has(user_id, row.scenario_id)
        if user_id is not None
        else False
    )
    return Scenario(
        meta=meta,
        steps=steps,
        config=config,
        resource=resource,
        orchestration=orchestration,
        caseCount=case_count_n,
        dataSetCount=data_set_count,
        stepCount=row.step_count or len(steps),
        tags=list(row.tags or []),
        starred=starred,
    )


def _meta_from_row(row: ComposerScenario) -> ScenarioMeta:
    payload = row.payload or {}
    definition = payload.get("definition") or {}
    meta_dict = definition.get("meta") or {}
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


def _steps_from_payload(payload: dict) -> list[dict]:
    """Steps live inside the container's definition now (plate-shaped dicts)."""
    definition = (payload or {}).get("definition") or {}
    raw = definition.get("steps") or []
    return [s for s in raw if isinstance(s, dict)]


def _extras_from_payload(
    payload: dict | None,
) -> tuple[dict | None, dict | None, Orchestration | None]:
    """Round-trip the persisted container's render-side sub-structure.

    The payload is the container ``{definition, orchestration, caseMeta}``.
    config/resource live under ``definition`` (plate-shaped); orchestration
    is a sibling of definition (platform render state). Returns ``(None,
    None, None)`` when absent so the frontend's default-rebuild fallback
    kicks in. Guards every read so a malformed legacy row never 500s.
    """
    definition = (payload or {}).get("definition") or {}
    config = definition.get("config") if isinstance(definition, dict) else None
    if not isinstance(config, dict):
        config = None
    resource = definition.get("resource") if isinstance(definition, dict) else None
    if not isinstance(resource, dict):
        resource = None
    orch_raw = (payload or {}).get("orchestration")
    orchestration: Orchestration | None = None
    if isinstance(orch_raw, dict):
        try:
            orchestration = Orchestration.model_validate(orch_raw)
        except Exception:
            orchestration = None
    return config, resource, orchestration


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
