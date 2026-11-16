"""服务主档路由(重构 2026-11-16 §1.1 注册簿制)— 读全员 / 写 ops.write。

主档 = 平台侧注册簿(不是 plate 目录镜像):登记了才可被条目/部署/
账户挂靠;对账状态(未注册/漂移/不可达)运行时算,不落库。说明列原
``/service-meta`` 端点随本表并入(description 字段)退役。

实例端点(``/services/instances``)维护 (system, env) 部署事实:
登录口/版本线/说明 —— 环境配置页的落库面;``environments`` 路由的
lines 视图与本端点同表 upsert(line 字段双写路径,一致性由 upsert
保证)。
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, MemberUser
from ..models import Service, SystemEnvInstance
from ..models.environment import Environment

router = APIRouter(prefix="/services", tags=["services"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_CAMEL = ConfigDict(populate_by_name=True)


class ServiceOut(BaseModel):
    model_config = _CAMEL

    name: str
    system: str
    kind: Literal["plate", "external", "integration"] = "plate"
    abbr: str = ""
    description: str = ""
    # 对账状态(运行时算):inCatalog = plate 目录在场(drifted = 主档
    # plate 行不在目录);plate 不可达 → plateReachable=False,对账跳过
    in_catalog: bool = Field(default=False, alias="inCatalog")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class ServiceListOut(BaseModel):
    model_config = _CAMEL

    services: list[ServiceOut] = Field(default_factory=list)
    # 对账提示:目录里还没拉入主档的服务名(一键登记候选)
    unregistered: list[str] = Field(default_factory=list)
    plate_reachable: bool = Field(default=True, alias="plateReachable")


class ServiceCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    system: str = Field(default="", max_length=128)
    kind: Literal["plate", "external", "integration"] = "plate"
    abbr: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=1024)


class ServicePatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    system: str | None = Field(default=None, max_length=128)
    abbr: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=1024)


class InstanceOut(BaseModel):
    model_config = _CAMEL

    system: str
    env_id: int = Field(alias="envId")
    env_name: str = Field(default="", alias="envName")
    login_url: str = Field(default="", alias="loginUrl")
    line: str = ""
    note: str = ""
    updated_at: str | None = Field(default=None, alias="updatedAt")


class InstancePut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    login_url: str | None = Field(default=None, max_length=512,
                                  alias="loginUrl")
    line: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=256)


@router.get("", response_model=ServiceListOut)
async def list_services(
    user: CurrentUser, db: DbSession,
    q: str | None = Query(default=None, max_length=128),
) -> ServiceListOut:
    """主档列表 + 对账条(未注册候选 / 目录在场标记 / plate 可达性)。"""
    from ..services import plate_client

    rows = (await db.execute(
        select(Service).order_by(Service.system, Service.name)
    )).scalars().all()
    catalog: set[str] = set()
    reachable = True
    try:
        catalog = {e["name"] for e in
                   await plate_client.catalog_service_entries()
                   if e.get("name")}
    except Exception:  # noqa: BLE001 — 对账是增强,不可达不阻塞读面
        reachable = False
    by_name = {s.name: s for s in rows}
    services = [
        ServiceOut(
            name=s.name, system=s.system, kind=s.kind,  # type: ignore[arg-type]
            abbr=s.abbr, description=s.description,
            in_catalog=(s.name in catalog) if reachable else False,
            created_at=(s.created_at.isoformat()
                        if s.created_at else None),
            updated_at=(s.updated_at.isoformat()
                        if s.updated_at else None))
        for s in rows]
    unregistered = sorted(catalog - set(by_name)) if reachable else []
    if q:
        ql = q.lower()
        services = [s for s in services if ql in s.name.lower()
                    or ql in s.system.lower()]
    return ServiceListOut(services=services, unregistered=unregistered,
                          plate_reachable=reachable)


@router.post("", response_model=ServiceOut, status_code=201)
async def create_service(
    user: MemberUser, body: ServiceCreate, db: DbSession,
) -> ServiceOut:
    """登记主档(ops.write)。plate 名校验:``kind=plate`` 且目录可达时,
    名字必须在目录内(防登记错别字);external/integration 自由命名。"""
    if body.kind == "plate":
        from ..services import plate_client

        try:
            catalog = {e["name"] for e in
                       await plate_client.catalog_service_entries(refresh=True)
                       if e.get("name")}
            if catalog and body.name not in catalog:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"unknown_service_name: {body.name!r} 不在 plate 目录"
                    "(登记防错别字;第三方服务请用 kind=external)")
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001 — plate 不可达放行(主档自足)
            pass
    dup = (await db.execute(select(Service.id).where(
        Service.name == body.name))).scalar()
    if dup is not None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"service '{body.name}' already registered")
    row = Service(name=body.name, system=body.system, kind=body.kind,
                  abbr=body.abbr, description=body.description)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="service_registry.write", resource_type="service",
        resource_id=row.name, detail={"fn": "create", "kind": row.kind})
    return ServiceOut(name=row.name, system=row.system, kind=row.kind,  # type: ignore[arg-type]
                      abbr=row.abbr, description=row.description)


@router.patch("/{name}", response_model=ServiceOut)
async def patch_service(
    name: str, user: MemberUser, body: ServicePatch, db: DbSession,
) -> ServiceOut:
    row = (await db.execute(select(Service).where(
        Service.name == name))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"service not found: {name}")
    if body.system is not None:
        row.system = body.system
    if body.abbr is not None:
        row.abbr = body.abbr
    if body.description is not None:
        row.description = body.description
    await db.commit()
    await db.refresh(row)
    return ServiceOut(name=row.name, system=row.system, kind=row.kind,  # type: ignore[arg-type]
                      abbr=row.abbr, description=row.description)


@router.delete("/{name}", status_code=204)
async def delete_service(
    name: str, user: MemberUser, db: DbSession,
) -> None:
    """删主档:有部署行/身份条目挂靠 → 409(先处置挂靠再删)。"""
    from ..models.deployment import Deployment
    from ..models.service_identity import ServiceIdentity

    row = (await db.execute(select(Service).where(
        Service.name == name))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"service not found: {name}")
    dep = (await db.execute(select(Deployment.id).where(
        Deployment.base_service == name).limit(1))).scalar()
    ident = (await db.execute(select(ServiceIdentity.id).where(
        ServiceIdentity.base_service == name).limit(1))).scalar()
    if dep is not None or ident is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "service_in_use: 该服务仍有部署地址或身份条目挂靠,"
            "请先处置(删部署行/条目)再删主档")
    await db.delete(row)
    await db.commit()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="service_registry.write", resource_type="service",
        resource_id=name, detail={"fn": "delete"})


# ── 实例(环境×系统部署事实)────────────────────────────────────
@router.get("/instances", response_model=list[InstanceOut])
async def list_instances(
    user: CurrentUser, db: DbSession,
    env_id: Annotated[int | None, Query(alias="envId", ge=1)] = None,
) -> list[InstanceOut]:
    """实例列表(可按环境过滤;环境配置页数据源)。"""
    from ..models.environment import Environment as Env

    stmt = select(SystemEnvInstance, Env.name).join(
        Env, Env.id == SystemEnvInstance.env_id)
    if env_id is not None:
        stmt = stmt.where(SystemEnvInstance.env_id == env_id)
    rows = (await db.execute(
        stmt.order_by(SystemEnvInstance.system))).all()
    return [InstanceOut(
        system=inst.system, env_id=inst.env_id, env_name=env_name,
        login_url=inst.login_url, line=inst.line, note=inst.note,
        updated_at=(inst.updated_at.isoformat()
                    if inst.updated_at else None))
        for inst, env_name in rows]


@router.put("/instances/{system}/{env_id}", response_model=InstanceOut,
            status_code=201)
async def put_instance(
    system: str, env_id: int, body: InstancePut,
    user: MemberUser, db: DbSession,
) -> InstanceOut:
    """维护实例(ops.write;upsert):登录口/版本线/说明 —— 环境配置页
    的落库面;``environments`` 的 lines 视图与本端点同表(line 字段)。"""
    from ..models.environment import Environment as Env

    if await db.get(Env, env_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"environment not found: {env_id}")
    inst = (await db.execute(
        select(SystemEnvInstance).where(
            SystemEnvInstance.system == system,
            SystemEnvInstance.env_id == env_id))).scalar_one_or_none()
    if inst is None:
        inst = SystemEnvInstance(system=system, env_id=env_id)
        db.add(inst)
    if body.login_url is not None:
        inst.login_url = body.login_url
    if body.line is not None:
        inst.line = body.line
    if body.note is not None:
        inst.note = body.note
    await db.commit()
    await db.refresh(inst)
    env_name = (await db.execute(
        select(Env.name).where(Env.id == env_id))).scalar() or ""
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="service_registry.write", resource_type="instance",
        resource_id=f"{system}/{env_id}",
        detail={"fn": "put", "loginUrl": inst.login_url, "line": inst.line})
    return InstanceOut(system=inst.system, env_id=inst.env_id,
                       env_name=env_name, login_url=inst.login_url,
                       line=inst.line, note=inst.note,
                       updated_at=(inst.updated_at.isoformat()
                                   if inst.updated_at else None))
