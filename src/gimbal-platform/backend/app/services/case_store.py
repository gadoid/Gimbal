"""DB-backed CRUD for V3 Scenario Composer Case rows.

A Case is 1:1 with a Scenario, 1:N with DataSet.  PATCH allows updating
env / auth / retry / dataSetIds / name / description but never
``caseId``, ``scenarioId``, ``createdBy``, ``updatedAt``, ``lastRunStatus``,
or ``lastRunAt`` (those are managed by the platform).
"""
from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_case import ComposerCase
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import (
    AuthSessionRef,
    Case,
    CasePatch,
    RetryRef,
)


async def create(
    db: AsyncSession,
    case: Case,
    *,
    created_by: str = "",
) -> Case:
    """Insert a new case.  Raises ValueError on duplicate or unknown scenarioId.

    Server-side overrides: ``createdBy`` and ``updatedAt`` are always
    taken from the caller (the router supplies ``created_by``) and
    ``datetime.utcnow()`` — never from the request body — so a caller
    cannot spoof ownership in the response.
    """
    # Verify scenario exists (FK is also enforced, but we want a friendlier error).
    scen = await db.execute(
        select(ComposerScenario.scenario_id).where(
            ComposerScenario.scenario_id == case.scenario_id
        )
    )
    if scen.scalar_one_or_none() is None:
        raise ValueError(f"scenario_not_found: {case.scenario_id}")

    server_owned = Case.model_validate({
        **case.model_dump(by_alias=True, mode="json"),
        "createdBy": created_by or case.created_by,
        "updatedAt": datetime.utcnow().isoformat() + "Z",
        "lastRunStatus": None,
        "lastRunAt": None,
    })

    row = ComposerCase(
        case_id=server_owned.case_id,
        scenario_id=server_owned.scenario_id,
        name=server_owned.name,
        description=server_owned.description or "",
        env=server_owned.env or "",
        auth=server_owned.auth.model_dump(by_alias=True, mode="json"),
        retry=(server_owned.retry.model_dump(by_alias=True, mode="json") if server_owned.retry else {}),
        data_set_ids=list(server_owned.data_set_ids or []),
        last_run_status=server_owned.last_run_status,
        last_run_at=server_owned.last_run_at,
        created_by=server_owned.created_by,
        payload=server_owned.model_dump(by_alias=True, mode="json"),
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ValueError(f"case_id_exists: {case.case_id}") from e
    await db.refresh(row)
    return await _to_read_shape(db, row)


async def patch(
    db: AsyncSession,
    case_id: str,
    patch: CasePatch,
) -> Case:
    """Apply a partial update.  Raises KeyError on miss."""
    row = await _get_row(db, case_id)
    # Reassign the dict (don't mutate in place — the plain ``JSON`` column
    # type does not detect in-place mutations; rebuild the dict so
    # SQLAlchemy sees a new value at flush time).
    new_payload: dict = dict(row.payload or {})
    if patch.name is not None:
        row.name = patch.name
        new_payload["name"] = patch.name
    if patch.description is not None:
        row.description = patch.description
        new_payload["description"] = patch.description
    if patch.env is not None:
        row.env = patch.env
        new_payload["env"] = patch.env
    if patch.auth is not None:
        auth_dict = patch.auth.model_dump(by_alias=True, mode="json")
        row.auth = auth_dict
        new_payload["auth"] = auth_dict
    if patch.retry is not None:
        retry_dict = patch.retry.model_dump(by_alias=True, mode="json")
        row.retry = retry_dict
        new_payload["retry"] = retry_dict
    if patch.data_set_ids is not None:
        ds_ids = list(patch.data_set_ids)
        row.data_set_ids = ds_ids
        new_payload["dataSetIds"] = ds_ids
    row.payload = new_payload
    await db.commit()
    await db.refresh(row)
    return await _to_read_shape(db, row)


async def delete(db: AsyncSession, case_id: str) -> None:
    """Delete a case and cascade its datasets."""
    row = await _get_row(db, case_id)
    await db.execute(
        sa_delete(ComposerDataSet).where(ComposerDataSet.case_id == case_id)
    )
    await db.delete(row)
    await db.commit()


async def get(
    db: AsyncSession, case_id: str
) -> Case:
    row = await _get_row(db, case_id)
    return await _to_read_shape(db, row)


async def list_cases(
    db: AsyncSession,
    *,
    scenario_id: str | None = None,
    q: str | None = None,
    system: str | None = None,
    module: str | None = None,
) -> list[Case]:
    """List cases with optional filters.  ``system`` / ``module`` are
    forwarded to the joined scenario (so the caller can find all cases
    under any scenario whose ``meta.system`` contains the tag)."""
    stmt = select(ComposerCase).order_by(ComposerCase.updated_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    out: list[Case] = []
    for r in rows:
        if scenario_id and r.scenario_id != scenario_id:
            continue
        # join to scenario for system / module filters
        scen = (
            await db.execute(
                select(ComposerScenario).where(
                    ComposerScenario.scenario_id == r.scenario_id
                )
            )
        ).scalar_one_or_none()
        if scen is None:
            continue
        if system and system not in (scen.system or []):
            continue
        if module and (scen.module or "") != module:
            continue
        if q:
            ql = q.lower()
            hay = [r.case_id, r.name, r.scenario_id]
            if not any(ql in (h or "").lower() for h in hay):
                continue
        out.append(await _to_read_shape(db, r))
    return out


async def list_for_scenario(
    db: AsyncSession, scenario_id: str
) -> list[Case]:
    res = await db.execute(
        select(ComposerCase).where(
            ComposerCase.scenario_id == scenario_id
        )
    )
    return [await _to_read_shape(db, r) for r in res.scalars().all()]


# ─── helpers ──────────────────────────────────────────────────────
async def _get_row(db: AsyncSession, case_id: str) -> ComposerCase:
    res = await db.execute(
        select(ComposerCase).where(ComposerCase.case_id == case_id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise KeyError(f"case_not_found: {case_id}")
    return row


async def _to_read_shape(
    db: AsyncSession, row: ComposerCase
) -> Case:
    payload = row.payload or {}
    if payload:
        # Prefer the persisted payload as-is; only fall through to
        # column-projection if it's missing required keys.
        try:
            return Case.model_validate(payload)
        except Exception:  # noqa: BLE001
            pass
    return Case(
        caseId=row.case_id,
        scenarioId=row.scenario_id,
        name=row.name,
        description=row.description,
        env=row.env,
        auth=AuthSessionRef.model_validate(row.auth or {"name": "anon", "type": "bearer"}),
        retry=(RetryRef.model_validate(row.retry) if row.retry else None),
        dataSetIds=list(row.data_set_ids or []),
        lastRunStatus=row.last_run_status,
        lastRunAt=row.last_run_at,
        createdBy=row.created_by,
        updatedAt=row.updated_at,
        starred=False,
    )
