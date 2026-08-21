"""DB-backed CRUD for V3 Scenario Composer DataSet rows.

A DataSet is a parameter matrix ``rows[]`` attached directly to a
Scenario.  Used to fan out the same Scenario into N parameterised runs.
(The former 1:1 Case layer was dissolved — datasets parameterise the
scenario's ``config.vars`` directly.)

The frontend shows a ``preview[0:3]`` on list views; we slice server-
side and never send the full row set in list responses.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_data_set import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import DataSet, DataSetDraft, DataSetSummary
from .scenario_store import get_row as get_scenario_row


def _scalar_vars(payload: dict | None) -> set[str]:
    """列调色板:definition.config.vars 中值为标量的键(spec §4.3)。

    结构化声明(如 {"kind": "seq"})不进调色板 —— 行覆盖会破坏
    引擎生成器语义。
    """
    definition = (payload or {}).get("definition")
    config = definition.get("config") if isinstance(definition, dict) else None
    vars_map = config.get("vars") if isinstance(config, dict) else None
    if not isinstance(vars_map, dict):
        return set()
    return {
        k for k, v in vars_map.items()
        if v is None or isinstance(v, (str, int, float, bool))
    }


def _validate_rows(scenario_payload: dict | None, rows: list[dict]) -> None:
    """行键 ⊆ 调色板,否则 ValueError("undeclared_var: …")(路由映射 422)。"""
    palette = _scalar_vars(scenario_payload)
    bad = sorted({k for row in rows for k in row if k not in palette})
    if bad:
        raise ValueError(
            f"undeclared_var: {', '.join(bad)} — 字段未声明为变量;"
            f"在编排中\"设为变量\"后即可作为数据集列"
        )


async def create(
    db: AsyncSession,
    scenario_id: str,
    draft: DataSetDraft,
) -> DataSet:
    """Insert a new dataset.  Raises ValueError on unknown scenario or duplicate id."""
    scenario = (
        await db.execute(
            select(ComposerScenario).where(
                ComposerScenario.scenario_id == scenario_id
            )
        )
    ).scalar_one_or_none()
    if scenario is None:
        raise ValueError(f"scenario_not_found: {scenario_id}")
    _validate_rows(scenario.payload, list(draft.rows or []))

    dataset_id = await _next_dataset_id(db)
    row = ComposerDataSet(
        dataset_id=dataset_id,
        scenario_id=scenario_id,
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
    return _to_full_shape(row)


async def update(
    db: AsyncSession,
    dataset_id: str,
    draft: DataSetDraft,
) -> DataSet:
    row = await _get_row(db, dataset_id)
    scenario = await get_scenario_row(db, row.scenario_id)
    if scenario is None:  # 理论不可达(FK 在);防御孤儿行
        raise KeyError(f"data_set_not_found: {dataset_id}")
    _validate_rows(scenario.payload, list(draft.rows or []))
    row.name = draft.name
    row.description = draft.description or ""
    row.rows = list(draft.rows or [])
    row.row_count = len(draft.rows or [])
    await db.commit()
    await db.refresh(row)
    return _to_full_shape(row)


async def get(
    db: AsyncSession, dataset_id: str
) -> DataSet:
    row = await _get_row(db, dataset_id)
    return _to_full_shape(row)


async def list_summaries(
    db: AsyncSession,
    *,
    scenario_id: str | None = None,
    scenario_ids: list[str] | set[str] | None = None,
) -> list[DataSetSummary]:
    """Return DataSetSummary (preview[3]) for list views.

    ``scenario_ids`` pushes the caller's ownership filter down as a SQL
    ``IN``(non-admin data-sets list);空集合直接短路为 []。
    """
    stmt = select(ComposerDataSet).order_by(ComposerDataSet.updated_at.desc())
    if scenario_id:
        stmt = stmt.where(ComposerDataSet.scenario_id == scenario_id)
    if scenario_ids is not None:
        if not scenario_ids:
            return []
        stmt = stmt.where(ComposerDataSet.scenario_id.in_(scenario_ids))
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_summary_shape(r) for r in rows]


async def list_for_scenario(
    db: AsyncSession, scenario_id: str
) -> list[DataSet]:
    """Full DataSet rows for one scenario(测试/诊断用;dispatcher 直查模型)。"""
    res = await db.execute(
        select(ComposerDataSet).where(ComposerDataSet.scenario_id == scenario_id)
    )
    return [_to_full_shape(r) for r in res.scalars().all()]


# ─── helpers ──────────────────────────────────────────────────────
async def get_row(
    db: AsyncSession, dataset_id: str
) -> ComposerDataSet | None:
    """单行查询(dataset_id 是 string PK)— 全后端唯一实现。

    data_sets 路由的属主检查与 run_dispatcher 的数据集解析都收敛到
    这里(镜像 scenario_store.get_row 的收敛约定),避免多份拷贝在
    加 scope/soft-delete 过滤时各自漂移。
    """
    res = await db.execute(
        select(ComposerDataSet).where(
            ComposerDataSet.dataset_id == dataset_id
        )
    )
    return res.scalar_one_or_none()


async def _get_row(db: AsyncSession, dataset_id: str) -> ComposerDataSet:
    row = await get_row(db, dataset_id)
    if row is None:
        raise KeyError(f"data_set_not_found: {dataset_id}")
    return row


def _to_full_shape(row: ComposerDataSet) -> DataSet:
    return DataSet(
        datasetId=row.dataset_id,
        scenarioId=row.scenario_id,
        name=row.name,
        description=row.description,
        rowCount=row.row_count,
        rows=list(row.rows or []),
    )


def _to_summary_shape(row: ComposerDataSet) -> DataSetSummary:
    preview = list(row.rows or [])[:3]
    return DataSetSummary(
        datasetId=row.dataset_id,
        scenarioId=row.scenario_id,
        name=row.name,
        rowCount=row.row_count,
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
