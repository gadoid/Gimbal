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


def _validate_rows(scenario_payload: dict | None, rows: list[dict],
                   known_slots: set[str] | None = None) -> None:
    """行键 ⊆ 调色板,否则 ValueError("undeclared_var: …")(路由映射 422)。

    M2b Q3:账号列 ``@slot.<槽名>``(值 = 本次执行凭证池里的绑定名)豁免
    调色板;槽名须在场景的注入槽集合里(否则 ``undeclared_slot``),值须
    为字符串。绑定是否存在不在保存时校验(绑定属执行人 / 项目,保存者
    未必看得见)—— 派发 fail-fast 兜底。"""
    from .run_prepare import ROW_BINDING_PREFIX

    palette = _scalar_vars(scenario_payload)
    keys = {k for row in rows for k in row}
    slot_cols = {k for k in keys if k.startswith(ROW_BINDING_PREFIX)}
    bad = sorted(keys - slot_cols - palette)
    if bad:
        raise ValueError(
            f"undeclared_var: {', '.join(bad)} — 字段未声明为变量;"
            f"在编排中\"设为变量\"后即可作为数据集列"
        )
    if slot_cols:
        known = (known_slots if known_slots is not None
                 else _injection_slots(scenario_payload))
        unknown = sorted(k for k in slot_cols
                         if k[len(ROW_BINDING_PREFIX):] not in known)
        if unknown:
            raise ValueError(
                f"undeclared_slot: {', '.join(unknown)} — 账号列的槽位未被"
                "场景引用(${auth.<槽>} / 别名声明槽位)")
        non_str = sorted({k for row in rows for k in slot_cols
                          if row.get(k) is not None
                          and not isinstance(row.get(k), str)})
        if non_str:
            raise ValueError(
                f"undeclared_slot: {', '.join(non_str)} — 账号列的值须为"
                "绑定名(字符串)")


def _injection_slots(scenario_payload: dict | None) -> set[str]:
    """场景引用的注入槽名(静态扫描:``${auth.<槽>}`` / ``${slot.<槽>.…}``
    + 别名声明槽位)—— 与派发注入清单同源的保存期近似(不查库的部分)。"""
    from .auth_ref_scan import scan_auth_aliases
    from .scenario_store import definition_from_payload

    defn = definition_from_payload(scenario_payload or {}) or {}
    nodes = [defn.get("steps") or [], (defn.get("config") or {})]
    found = set(scan_auth_aliases(nodes))
    import re as _re
    found |= set(_re.findall(r"\$\{slot\.([A-Za-z0-9_-]+)\.",
                             str(nodes)))
    return found


async def _known_slots(db: AsyncSession, scenario_payload: dict | None,
                       rows: list[dict]) -> set[str] | None:
    """账号列校验用的槽集合 = 派发注入清单(模板扫描 ∪ 别名声明槽位,
    ``exec_auth_aliases_of_definition`` 同源)∪ 静态扫描。行无账号列时
    不查库(返回 None)。"""
    from .run_prepare import ROW_BINDING_PREFIX
    if not any(isinstance(k, str) and k.startswith(ROW_BINDING_PREFIX)
               for row in rows for k in row):
        return None
    from .scenario_store import definition_from_payload
    from .service_aliases import exec_auth_aliases_of_definition
    names = await exec_auth_aliases_of_definition(
        db, definition_from_payload(scenario_payload or {}))
    return set(names) | _injection_slots(scenario_payload)


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
    _validate_rows(scenario.payload, list(draft.rows or []),
                   await _known_slots(db, scenario.payload,
                                      list(draft.rows or [])))

    dataset_id = await _next_dataset_id(db)
    row = ComposerDataSet(
        dataset_id=dataset_id,
        scenario_id=scenario_id,
        name=draft.name,
        description=draft.description or "",
        rows=list(draft.rows or []),
        var_unlocks=list(draft.var_unlocks or []),
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        # Only treat as a duplicate-id collision when SQLite reports it
        # through the dataset_id unique index. Without this scope check
        # the catch-all used to mask schema-level errors (e.g. a stale
        # `case_id NOT NULL` column) behind a misleading "dataset_id_exists"
        # message that pointed the operator at the wrong fix.
        if _is_dataset_id_collision(e):
            raise ValueError(f"dataset_id_exists: {dataset_id}") from e
        raise
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
    _validate_rows(scenario.payload, list(draft.rows or []),
                   await _known_slots(db, scenario.payload,
                                      list(draft.rows or [])))
    row.name = draft.name
    row.description = draft.description or ""
    row.rows = list(draft.rows or [])
    row.var_unlocks = list(draft.var_unlocks or [])
    await db.commit()
    await db.refresh(row)
    return _to_full_shape(row)


async def get(
    db: AsyncSession, dataset_id: str, *, redact: bool = False,
) -> DataSet:
    """``redact``:读者非场景属主 → 剥敏感列(authz W6,原件不动)。"""
    row = await _get_row(db, dataset_id)
    return _to_full_shape(row, redact=redact)


async def delete(db: AsyncSession, dataset_id: str) -> None:
    """Delete a dataset row.  Raises KeyError on miss."""
    row = await _get_row(db, dataset_id)
    await db.delete(row)
    await db.commit()


async def list_summaries(
    db: AsyncSession,
    *,
    scenario_id: str | None = None,
    scenario_ids: list[str] | set[str] | None = None,
    owned_ids: set[str] | None = None,
) -> list[DataSetSummary]:
    """Return DataSetSummary (preview[3]) for list views.

    ``scenario_ids`` pushes the caller's ownership filter down as a SQL
    ``IN``(non-admin data-sets list);空集合直接短路为 []。
    ``owned_ids`` 给定时,不在其中的场景(引用闭包读者)预览剥敏感列。
    """
    stmt = select(ComposerDataSet).order_by(ComposerDataSet.updated_at.desc())
    if scenario_id:
        stmt = stmt.where(ComposerDataSet.scenario_id == scenario_id)
    if scenario_ids is not None:
        if not scenario_ids:
            return []
        stmt = stmt.where(ComposerDataSet.scenario_id.in_(scenario_ids))
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_summary_shape(
        r, redact=owned_ids is not None and r.scenario_id not in owned_ids)
        for r in rows]


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


def _rows_for(rows: list | None, redact: bool) -> list:
    if not redact:
        return list(rows or [])
    from .scenario_store import strip_sensitive_columns

    return strip_sensitive_columns(rows or [])


def _to_full_shape(row: ComposerDataSet, *, redact: bool = False) -> DataSet:
    return DataSet(
        datasetId=row.dataset_id,
        scenarioId=row.scenario_id,
        name=row.name,
        description=row.description,
        rowCount=row.row_count,
        rows=_rows_for(row.rows, redact),
        varUnlocks=list(row.var_unlocks or []),
    )


def _to_summary_shape(row: ComposerDataSet, *,
                      redact: bool = False) -> DataSetSummary:
    preview = _rows_for(list(row.rows or [])[:3], redact)
    return DataSetSummary(
        datasetId=row.dataset_id,
        scenarioId=row.scenario_id,
        name=row.name,
        rowCount=row.row_count,
        preview=preview,
    )


_NNN_RE = re.compile(r"^ds-(\d+)$")


def _is_dataset_id_collision(err: IntegrityError) -> bool:
    """True iff the IntegrityError is the dataset_id unique-index collision.

    SQLite puts the constraint / index name in the message; we accept any
    form that mentions ``dataset_id`` *and* isn't a NOT NULL / FK
    violation, so genuine schema-level bugs surface with their real
    message instead of being flattened into "dataset_id_exists".
    """
    msg = str(getattr(err, "orig", err) or "")
    if not msg:
        return False
    if "dataset_id" not in msg:
        return False
    # Filter out the unrelated IntegrityError flavours we don't want to
    # mis-classify as a duplicate id. Note: we don't blacklist
    # "UNIQUE constraint failed: composer_data_sets." itself — SQLite's
    # unique-index collision message starts with that prefix, and the
    # `dataset_id` substring check above already scopes the match.
    bad = ("NOT NULL", "FOREIGN KEY", "CHECK constraint")
    return not any(token in msg for token in bad)


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
