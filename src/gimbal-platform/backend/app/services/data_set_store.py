"""DB-backed CRUD for V3 Scenario Composer DataSet rows.

A DataSet is a parameter matrix ``rows[]`` attached to a Case.  Used to
fan out the same Scenario into N parameterised runs.

The frontend shows a ``preview[0:3]`` on list views; we slice server-
side and never send the full row set in list responses.
"""
from __future__ import annotations

import re

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_case import ComposerCase
from ..models.composer_data_set import ComposerDataSet
from ..schemas.scenario_composer import DataSet, DataSetDraft, DataSetSummary


async def create(
    db: AsyncSession,
    case_id: str,
    draft: DataSetDraft,
) -> DataSet:
    """Insert a new dataset.  Raises ValueError on unknown case or duplicate id."""
    case_row = (
        await db.execute(
            select(ComposerCase.case_id).where(ComposerCase.case_id == case_id)
        )
    ).scalar_one_or_none()
    if case_row is None:
        raise ValueError(f"case_not_found: {case_id}")

    dataset_id = await _next_dataset_id(db)
    row = ComposerDataSet(
        dataset_id=dataset_id,
        case_id=case_id,
        name=draft.name,
        description=draft.description or "",
        rows=list(draft.rows or []),
        row_count=len(draft.rows or []),
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ValueError(f"dataset_id_exists: {dataset_id}") from e
    await db.refresh(row)
    return await _to_full_shape(row)


async def update(
    db: AsyncSession,
    dataset_id: str,
    draft: DataSetDraft,
) -> DataSet:
    row = await _get_row(db, dataset_id)
    row.name = draft.name
    row.description = draft.description or ""
    row.rows = list(draft.rows or [])
    row.row_count = len(draft.rows or [])
    await db.commit()
    await db.refresh(row)
    return await _to_full_shape(row)


async def delete(db: AsyncSession, dataset_id: str) -> None:
    row = await _get_row(db, dataset_id)
    await db.delete(row)
    await db.commit()


async def get(
    db: AsyncSession, dataset_id: str
) -> DataSet:
    row = await _get_row(db, dataset_id)
    return await _to_full_shape(row)


async def list_summaries(
    db: AsyncSession, *, case_id: str | None = None
) -> list[DataSetSummary]:
    """Return DataSetSummary (preview[3]) for list views.

    Joins to the Case to populate ``caseName``.
    """
    stmt = select(ComposerDataSet).order_by(ComposerDataSet.updated_at.desc())
    if case_id:
        stmt = stmt.where(ComposerDataSet.case_id == case_id)
    rows = (await db.execute(stmt)).scalars().all()
    out: list[DataSetSummary] = []
    for r in rows:
        case_name = ""
        if r.case_id:
            cname = (
                await db.execute(
                    select(ComposerCase.name).where(
                        ComposerCase.case_id == r.case_id
                    )
                )
            ).scalar_one_or_none()
            case_name = cname or ""
        out.append(_to_summary_shape(r, case_name))
    return out


async def list_for_case(
    db: AsyncSession, case_id: str
) -> list[DataSet]:
    """Full DataSet rows (used by the run dispatcher)."""
    res = await db.execute(
        select(ComposerDataSet).where(ComposerDataSet.case_id == case_id)
    )
    return [await _to_full_shape(r) for r in res.scalars().all()]


def validate_rows(rows: list[dict]) -> None:
    """Raise ValueError("inconsistent_row_columns: ...") on key-set mismatch.

    The same check is wired into DataSet / DataSetDraft as a Pydantic
    model_validator, so this standalone helper is only needed when
    accepting rows as plain dicts (e.g. JSONL imports).
    """
    if not rows:
        return
    keys = set(rows[0].keys())
    for i, r in enumerate(rows[1:], start=1):
        if set(r.keys()) != keys:
            raise ValueError(
                f"inconsistent_row_columns: row {i} keys {sorted(r.keys())} != {sorted(keys)}"
            )


# ─── helpers ──────────────────────────────────────────────────────
async def _get_row(db: AsyncSession, dataset_id: str) -> ComposerDataSet:
    res = await db.execute(
        select(ComposerDataSet).where(
            ComposerDataSet.dataset_id == dataset_id
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise KeyError(f"data_set_not_found: {dataset_id}")
    return row


async def _to_full_shape(row: ComposerDataSet) -> DataSet:
    return DataSet(
        datasetId=row.dataset_id,
        caseId=row.case_id,
        name=row.name,
        description=row.description,
        rowCount=row.row_count,
        rows=list(row.rows or []),
        lastRunStatus=row.last_run_status,
        lastRunAt=row.last_run_at,
    )


def _to_summary_shape(
    row: ComposerDataSet, case_name: str
) -> DataSetSummary:
    preview = list(row.rows or [])[:3]
    return DataSetSummary(
        datasetId=row.dataset_id,
        caseId=row.case_id,
        caseName=case_name,
        name=row.name,
        rowCount=row.row_count,
        lastRunStatus=row.last_run_status,
        lastRunAt=row.last_run_at,
        preview=preview,
    )


_NNN_RE = re.compile(r"^ds-(\d+)$")


async def _next_dataset_id(db: AsyncSession) -> str:
    """Return the smallest unused ``ds-NNN`` (zero-padded 3 digits).

    Mirrors the doc's example style (`ds-001`).  Falls back to `ds-NNN`
    even when the gap exceeds 999.
    """
    res = await db.execute(select(ComposerDataSet.dataset_id))
    used: set[int] = set()
    for (did,) in res.all():
        m = _NNN_RE.match(did or "")
        if m:
            try:
                used.add(int(m.group(1)))
            except ValueError:
                pass
    n = 1
    while n in used:
        n += 1
    return f"ds-{n:03d}" if n <= 999 else f"ds-{n}"
