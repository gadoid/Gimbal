"""CRUD store for composer_run_schemes(workbench spec §5)。

行形状:关系的做关系(scenario 归属/name 唯一/default 标记在列),
文档的做文档(方案体一个 JSON payload,camelCase wire 形状)。
store 层错误约定:ValueError("name_conflict") / ValueError("default_protected")
/ KeyError(scheme_id) — 路由层负责翻译成 409/405/404。
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_run_scheme import ComposerRunScheme

DEFAULT_SCHEME_NAME = "默认方案"

_EMPTY_PAYLOAD: dict = {
    "dataSetSelection": [], "injectionEntryIds": [], "serviceBindings": {},
    "stepTo": None, "nRuns": 1, "parallel": 1, "plugins": None, "logSub": None,
}


def normalized(payload: dict | None) -> dict:
    """合并缺省键,保证 wire 形状完整(存量/旧端点数据可能缺新键)。

    旧形状兼容:只有 dataSetIds(整库语义)而无行级选择时,合成
    dataSetSelection(spec v3 §4 权威键;rowIndexes 空 = 整库)。
    """
    p = dict(payload or {})
    out = dict(_EMPTY_PAYLOAD)
    if not p.get("dataSetSelection") and p.get("dataSetIds"):
        out["dataSetSelection"] = [
            {"datasetId": d, "rowIndexes": []} for d in p["dataSetIds"]
        ]
    out.update({k: v for k, v in p.items() if k in out})
    return out


def _sanitize_default(payload: dict) -> dict:
    p = normalized(payload)
    p["dataSetSelection"] = []
    p["injectionEntryIds"] = []
    return p


async def _next_scheme_id(db: AsyncSession) -> str:
    """分配最小未用的 rs-NNN(仿 data_set_store._next_dataset_id)。"""
    rows = (await db.execute(select(ComposerRunScheme.scheme_id))).scalars().all()
    used = {r for r in rows if r.startswith("rs-")}
    n = 1
    while f"rs-{n:03d}" in used:
        n += 1
    return f"rs-{n:03d}"


def _to_wire(row: ComposerRunScheme) -> dict:
    return {
        "schemeId": row.scheme_id,
        "name": row.name,
        "isDefault": bool(row.is_default),
        **normalized(row.payload),
    }


async def ensure_default_scheme(db: AsyncSession, scenario_id: str) -> None:
    hit = (await db.execute(
        select(ComposerRunScheme.id).where(
            ComposerRunScheme.scenario_id == scenario_id,
            ComposerRunScheme.is_default.is_(True),
        )
    )).scalar_one_or_none()
    if hit is None:
        db.add(ComposerRunScheme(
            scheme_id=await _next_scheme_id(db),
            scenario_id=scenario_id,
            name=DEFAULT_SCHEME_NAME,
            is_default=True,
            payload=dict(_EMPTY_PAYLOAD),
        ))
        await db.commit()


async def list_schemes(db: AsyncSession, scenario_id: str) -> list[dict]:
    rows = (await db.execute(
        select(ComposerRunScheme)
        .where(ComposerRunScheme.scenario_id == scenario_id)
        .order_by(ComposerRunScheme.is_default.desc(), ComposerRunScheme.name)
    )).scalars().all()
    return [_to_wire(r) for r in rows]


async def create_scheme(
    db: AsyncSession, scenario_id: str, *,
    name: str, payload: dict, is_default: bool = False,
) -> dict:
    if not is_default and name == DEFAULT_SCHEME_NAME:
        raise ValueError("name_conflict")
    exists = (await db.execute(
        select(ComposerRunScheme.id).where(
            ComposerRunScheme.scenario_id == scenario_id,
            ComposerRunScheme.name == name,
        )
    )).scalar_one_or_none()
    if exists is not None:
        raise ValueError("name_conflict")
    row = ComposerRunScheme(
        scheme_id=await _next_scheme_id(db),
        scenario_id=scenario_id, name=name, is_default=is_default,
        payload=_sanitize_default(payload) if is_default else normalized(payload),
    )
    db.add(row)
    await db.commit()
    return _to_wire(row)


async def get_row(
    db: AsyncSession, scenario_id: str, scheme_id: str,
) -> ComposerRunScheme:
    row = (await db.execute(
        select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == scenario_id,
            ComposerRunScheme.scheme_id == scheme_id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise KeyError(scheme_id)
    return row


async def update_scheme(
    db: AsyncSession, scenario_id: str, scheme_id: str, *,
    name: str | None, payload: dict | None,
) -> dict:
    row = await get_row(db, scenario_id, scheme_id)
    if row.is_default:
        if payload is not None:
            row.payload = _sanitize_default(payload)
    else:
        if name is not None:
            if name == DEFAULT_SCHEME_NAME:
                raise ValueError("name_conflict")
            dup = (await db.execute(
                select(ComposerRunScheme.id).where(
                    ComposerRunScheme.scenario_id == scenario_id,
                    ComposerRunScheme.name == name,
                    ComposerRunScheme.scheme_id != scheme_id,
                )
            )).scalar_one_or_none()
            if dup is not None:
                raise ValueError("name_conflict")
            row.name = name
        if payload is not None:
            row.payload = normalized(payload)
    await db.commit()
    return _to_wire(row)


async def delete_scheme(
    db: AsyncSession, scenario_id: str, scheme_id: str,
) -> None:
    row = await get_row(db, scenario_id, scheme_id)
    if row.is_default:
        raise ValueError("default_protected")
    await db.delete(row)
    await db.commit()


async def replace_all(
    db: AsyncSession, scenario_id: str, schemes: list[dict],
) -> list[dict]:
    """整表替换(旧 PUT /run-schemes 端点的桥接语义)。"""
    await db.execute(sa_delete(ComposerRunScheme).where(
        ComposerRunScheme.scenario_id == scenario_id,
        ComposerRunScheme.is_default.is_(False),
    ))
    for s in schemes:
        if s.get("isDefault"):
            continue  # default 行只更新不重建(调用方一般也不会传)
        await create_scheme(db, scenario_id,
            name=s["name"], payload=s, is_default=False)
    await ensure_default_scheme(db, scenario_id)
    return await list_schemes(db, scenario_id)


async def copy_schemes(
    db: AsyncSession, src_scenario_id: str, dst_scenario_id: str,
) -> None:
    """逐行复制(重新分配 scheme_id)。不 commit — 调用方
    (scenario_store.copy_scenario)把它并进自己的事务。"""
    rows = (await db.execute(
        select(ComposerRunScheme)
        .where(ComposerRunScheme.scenario_id == src_scenario_id)
    )).scalars().all()
    for r in rows:
        db.add(ComposerRunScheme(
            scheme_id=await _next_scheme_id(db),
            scenario_id=dst_scenario_id, name=r.name,
            is_default=r.is_default, payload=dict(r.payload or {}),
        ))


async def scheme_counts(db: AsyncSession) -> dict[str, int]:
    rows = (await db.execute(
        select(ComposerRunScheme.scenario_id, func.count())
        .group_by(ComposerRunScheme.scenario_id)
    )).all()
    return {sid: n for sid, n in rows}
