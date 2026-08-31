"""carry 配置面路由(spec §3.2):读 CurrentUser(编排器提示要用),
写 AdminUser(平台配置维护者)。字段面聚合走 plate /full。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser, CurrentUser
from ..models.carry_binding import CarryServiceBinding
from ..schemas.carry import (
    BindingsOut,
    CarryFieldFace,
    CarryMapIn,
    DefaultsIn,
    DefaultsOut,
    DriftReport,
    ServiceBindingsOut,
    ServiceDrift,
    ServiceFieldsOut,
)
from ..services import carry_store
from ..services.plate_client import PlateUnavailableError
from .adaptations import _plate_502

router = APIRouter(prefix="/carry", tags=["carry"])

DbSession = Depends(get_db)


def _svc_map(rows) -> dict[str, dict[str, str | None]]:
    out: dict[str, dict[str, str | None]] = {}
    for r in rows:
        out.setdefault(r.service_name, {})[r.field_path] = r.value
    return out


@router.get("/defaults", response_model=DefaultsOut)
async def get_defaults(user: CurrentUser, db=DbSession):
    return DefaultsOut(defaults=await carry_store.get_defaults(db))


@router.put("/defaults", response_model=DefaultsOut)
async def put_defaults(user: AdminUser, body: DefaultsIn, db=DbSession):
    await carry_store.put_defaults(db, body.defaults, user.username)
    await db.commit()
    return DefaultsOut(defaults=await carry_store.get_defaults(db))


@router.get("/bindings", response_model=BindingsOut)
async def list_bindings(user: CurrentUser, db=DbSession):
    rows = (await db.execute(select(CarryServiceBinding))).scalars().all()
    return BindingsOut(bindings=_svc_map(rows))


@router.get("/bindings/{service}", response_model=ServiceBindingsOut)
async def get_bindings(service: str, user: CurrentUser, db=DbSession):
    return ServiceBindingsOut(
        bindings=await carry_store.get_bindings(db, service))


@router.put("/bindings/{service}", response_model=ServiceBindingsOut)
async def put_bindings(service: str, user: AdminUser, body: CarryMapIn,
                       db=DbSession):
    await carry_store.put_bindings(db, service, body.bindings, user.username)
    await db.commit()
    return ServiceBindingsOut(
        bindings=await carry_store.get_bindings(db, service))


@router.get("/drift", response_model=DriftReport)
async def drift(user: AdminUser, db=DbSession):
    return DriftReport(services=[
        ServiceDrift(**s) for s in await carry_store.carry_drift(db)])


@router.get("/bindings/{service}/fields", response_model=ServiceFieldsOut)
async def service_fields(service: str, user: AdminUser, db=DbSession):
    """该服务全部接口 carry 面并集:GET /api/endpoint?service= → 逐 id /full。"""
    from ..services.adaptation_service import _plate_full_endpoint

    try:
        client_items = await _plate_list_endpoints_filtered(service)
    except PlateUnavailableError as e:
        raise _plate_502(e) from e
    faces: dict[str, CarryFieldFace] = {}
    for item in client_items:
        try:
            full = await _plate_full_endpoint(item["id"])
        except PlateUnavailableError:
            continue  # 降级:该端点面缺席,不阻塞其余
        if full is None:
            continue
        carry = ((full.get("request") or {}).get("carry")) or {}
        for path, entry in carry.items():
            faces.setdefault(path, CarryFieldFace(
                path=path,
                type=str(entry.get("type") or "string"),
                description=str(entry.get("description") or ""),
            ))
    return ServiceFieldsOut(fields=sorted(faces.values(), key=lambda f: f.path))


async def _plate_list_endpoints_filtered(service: str) -> list[dict]:
    """轻量列表按 service 过滤(adaptation_service._plate_list_endpoints 复用)。"""
    from ..services.adaptation_service import _plate_list_endpoints

    items = await _plate_list_endpoints()
    return [it for it in items if it.get("service") == service]
