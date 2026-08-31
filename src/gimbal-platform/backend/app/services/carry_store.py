"""carry 值层读写(spec §3.2 API 的 store 面)。

PUT 语义 = 整体替换(行集 diff:删缺键、upsert 在键);调用方负责 commit。
"""
from __future__ import annotations

from sqlalchemy import delete, select

from ..models.carry_binding import CarryGlobalDefault, CarryServiceBinding


async def get_bindings(db, service_name: str) -> dict[str, str | None]:
    rows = (await db.execute(
        select(CarryServiceBinding).where(
            CarryServiceBinding.service_name == service_name)
    )).scalars().all()
    return {r.field_path: r.value for r in rows}


async def put_bindings(
    db, service_name: str, entries: dict[str, str | None], updated_by: str
) -> None:
    await db.execute(delete(CarryServiceBinding).where(
        CarryServiceBinding.service_name == service_name))
    for path, value in sorted(entries.items()):
        db.add(CarryServiceBinding(service_name=service_name,
                                   field_path=path, value=value,
                                   updated_by=updated_by))


async def get_defaults(db) -> dict[str, str | None]:
    rows = (await db.execute(select(CarryGlobalDefault))).scalars().all()
    return {r.field_path: r.value for r in rows}


async def put_defaults(
    db, entries: dict[str, str | None], updated_by: str
) -> None:
    await db.execute(delete(CarryGlobalDefault))
    for path, value in sorted(entries.items()):
        db.add(CarryGlobalDefault(field_path=path, value=value,
                                  updated_by=updated_by))
