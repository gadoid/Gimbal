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

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, MemberUser
from ..models import Service, SystemEnvInstance
from ..models.deployment import Deployment
from ..models.environment import Environment
from ..models.service_identity import ServiceIdentity

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


class ImportCatalogIn(BaseModel):
    """批量导入目录服务(空 = 全部未登记)。"""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    names: list[str] = Field(default_factory=list, max_length=200)


class ImportCatalogOut(BaseModel):
    """导入结果:created / skipped(已登记或不在目录)+ 剩余未登记。"""

    model_config = _CAMEL

    created: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    unregistered: list[str] = Field(default_factory=list)
    plate_reachable: bool = Field(default=True, alias="plateReachable")


class InstanceOut(BaseModel):
    model_config = _CAMEL

    system: str
    env_id: int = Field(alias="envId")
    env_name: str = Field(default="", alias="envName")
    # 标签组:同组行 = 一个实例的多枚标签(配置共享)
    group_id: str = Field(default="", alias="groupId")
    tags: list[str] = Field(default_factory=list)
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


class InstanceMove(BaseModel):
    """实例改标签(2026-11-18 环境降级交互补齐;标签即环境)。

    目标环境二选一:``envId``(既有环境)或 ``envTag``(自由标签,不存在
    则自动登记为环境定义)。登录口/版本线/说明随行;API 地址
    (deployments)与身份条目按各自环境维护,不随搬移。"""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    env_id: int | None = Field(default=None, ge=1, alias="envId")
    env_tag: str | None = Field(default=None, max_length=64, alias="envTag")


class InstanceTagsIn(BaseModel):
    """实例标签集合(多枚;整组一次提交)。"""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    tags: list[str] = Field(min_length=1, max_length=30)


# ── 服务实例(service × env 组合视图;编排器数据源)────────────────────
class InstanceIdentityOut(BaseModel):
    """实例下的调用身份条目(不含账户/密码)。"""

    model_config = _CAMEL

    alias_name: str = Field(alias="aliasName")
    ref_mode: Literal["default", "username"] = Field(
        default="default", alias="refMode")
    ref_username: str = Field(default="", alias="refUsername")
    display: str = ""


class ServiceInstanceOut(BaseModel):
    """服务×环境实例(组合 deployments + system_env_instances + identities)。"""

    model_config = _CAMEL

    env_id: int = Field(alias="envId")
    env_name: str = Field(default="", alias="envName")
    # 同组标签行 = 一个实例的多枚环境 tag(服务注册页同款口径);
    # 无系统实例行时为空串(前端按 env 自成一实例)。
    group_id: str = Field(default="", alias="groupId")
    tags: list[str] = Field(default_factory=list)
    base_url: str = Field(default="", alias="baseUrl")
    login_url: str = Field(default="", alias="loginUrl")
    line: str = ""
    note: str = ""
    identities: list[InstanceIdentityOut] = Field(default_factory=list)


class ServiceWithInstancesOut(BaseModel):
    model_config = _CAMEL

    name: str
    system: str
    kind: Literal["plate", "external", "integration"] = "plate"
    instances: list[ServiceInstanceOut] = Field(default_factory=list)


class ServiceInstanceOverviewOut(BaseModel):
    model_config = _CAMEL

    services: list[ServiceWithInstancesOut] = Field(default_factory=list)


class InstanceIdentityIn(BaseModel):
    """创建实例时可选携带的一条调用身份。"""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    alias_name: str = Field(min_length=1, max_length=64,
                            alias="aliasName",
                            pattern=r"^[A-Za-z0-9_-]+$")
    ref_mode: Literal["default", "username"] = Field(
        default="default", alias="refMode")
    ref_username: str = Field(default="", max_length=128,
                              alias="refUsername")
    display: str = Field(default="", max_length=128)

    @model_validator(mode="after")
    def _username_ref_requires_name(self) -> "InstanceIdentityIn":
        if self.ref_mode == "username" and not self.ref_username.strip():
            raise ValueError(
                "ref_username_required: refMode=username 必须填写引用用户名")
        return self


class ServiceInstancePut(BaseModel):
    """创建/编辑一个服务×环境实例。

    * ``envId`` / ``envTag`` 二选一(自由标签不存在时自动登记);
    * ``baseUrl`` 写 deployments(API 地址);
    * ``loginUrl``/``line``/``note`` 写 system_env_instances(登录口按
      系统×环境共享);
    * ``identity`` 可选:同时登记一条调用身份(别名全局唯一)。
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    env_id: int | None = Field(default=None, ge=1, alias="envId")
    env_tag: str | None = Field(default=None, max_length=64, alias="envTag")
    base_url: str | None = Field(default=None, max_length=512,
                                 alias="baseUrl")
    login_url: str | None = Field(default=None, max_length=512,
                                  alias="loginUrl")
    line: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=256)
    identity: InstanceIdentityIn | None = None

    @model_validator(mode="after")
    def _exactly_one_env(self) -> "ServiceInstancePut":
        if (self.env_id is None) == (self.env_tag is None):
            raise ValueError("exactly one of envId / envTag is required")
        return self


async def _find_or_create_env_by_tag(db: Any, tag: str, user: Any) -> Any:
    """标签 → 环境行(不存在则登记;幂等)。写面与其它环境写门同源:
    调用方已过 MemberUser(ops.write)。"""
    from ..models.environment import Environment as Env

    name = tag.strip()
    if not name:
        raise HTTPException(422, "environment tag must not be blank")
    env = (await db.execute(
        select(Env).where(Env.name == name))).scalar_one_or_none()
    if env is None:
        env = Env(name=name, description="", owner_id=user.id)
        db.add(env)
        await db.flush()
        from ..services import audit as audit_svc

        await audit_svc.record(
            db, actor_id=user.id,
            actor_name=user.display_name or user.username,
            action="environment.write", resource_type="environment",
            resource_id=str(env.id), resource_name=env.name,
            detail={"op": "create", "source": "instance_tag"})
    return env


async def _tags_by_group(db: Any, group_ids: set[str]) -> dict[str, list[str]]:
    """组 id → 该实例的标签名集(一实例多标签;按组内行聚合)。"""
    if not group_ids:
        return {}
    from ..models.environment import Environment as Env

    rows = (await db.execute(
        select(SystemEnvInstance.group_id, Env.name).join(
            Env, Env.id == SystemEnvInstance.env_id).where(
            SystemEnvInstance.group_id.in_(group_ids)))).all()
    out: dict[str, list[str]] = {}
    for gid, name in rows:
        out.setdefault(gid, []).append(name)
    return {gid: sorted(names) for gid, names in out.items()}


async def _instance_out(db: Any, inst: SystemEnvInstance) -> InstanceOut:
    """行 → 对外视图(带同组标签集;登录口/版本线/说明为组共享值)。"""
    from ..models.environment import Environment as Env

    env_name = (await db.execute(
        select(Env.name).where(Env.id == inst.env_id))).scalar() or ""
    tags = await _tags_by_group(db, {inst.group_id})
    return InstanceOut(
        system=inst.system, env_id=inst.env_id, env_name=env_name,
        group_id=inst.group_id, tags=tags.get(inst.group_id, []),
        login_url=inst.login_url, line=inst.line, note=inst.note,
        updated_at=(inst.updated_at.isoformat()
                    if inst.updated_at else None))


async def _sync_instance_fields(
    db: Any, system: str, env_id: int, *,
    login_url: str | None = None,
    line: str | None = None,
    note: str | None = None,
) -> SystemEnvInstance:
    """upsert (system, env) 实例配置并同步同组标签行(**不 commit**)。

    登录口/版本线/说明是系统×环境共享事实;``None`` = 不修改该字段。
    """
    inst = (await db.execute(
        select(SystemEnvInstance).where(
            SystemEnvInstance.system == system,
            SystemEnvInstance.env_id == env_id))).scalar_one_or_none()
    if inst is None:
        inst = SystemEnvInstance(system=system, env_id=env_id,
                                 group_id=uuid.uuid4().hex)
        db.add(inst)
        group_rows = [inst]
    else:
        group_rows = (await db.execute(
            select(SystemEnvInstance).where(
                SystemEnvInstance.system == system,
                SystemEnvInstance.group_id == inst.group_id))).scalars().all()
    for row in group_rows:
        if login_url is not None:
            row.login_url = login_url
        if line is not None:
            row.line = line
        if note is not None:
            row.note = note
    await db.flush()
    return inst


def _checked_login_url(value: str | None) -> str | None:
    """loginUrl scheme 闸(口径与 baseUrl 一致,2026-11-21)。

    登录口由引擎登录流程直接当 URL 消费,任意串入库会在执行期被打
    出去 —— 非空必须以 http:// 或 https:// 开头;空串/None = 清空/
    不改,放行。返回去空格后的值(写侧与 baseUrl 同款去空格口径)。
    """
    if value is None:
        return None
    url = value.strip()
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, {
                "code": "login_url_invalid",
                "message": "登录口地址必须以 http:// 或 https:// 开头,"
                           "(留空 = 清除登录口)"})
    return url


def _instance_integrity_conflict(e: Exception) -> tuple[str, str]:
    """提交点 IntegrityError → (code, message),按约束名分派。

    同 scenario_store._integrity_conflict_code 教训(评审 2026-11-20)
    的复发修复:提交点冲突多源 —— 身份别名唯一 / 部署 (service, env)
    唯一 / 系统实例行唯一,一律映射「身份撞名」会把 deployment 竞态
    误报成调用身份名已登记。别名唯一 → service_instance_identity_taken;
    其余保守回落 service_instance_conflict(409 不 500,消息带约束名
    便于诊断)。
    """
    orig = getattr(e, "orig", None)
    name = str(getattr(orig, "constraint_name", "")
               or getattr(getattr(orig, "diag", None),
                          "constraint_name", "") or "")
    if "service_identities" in name or "alias_name" in name:
        return ("service_instance_identity_taken",
                "并发冲突:调用身份名刚被他处登记")
    return ("service_instance_conflict",
            f"并发冲突({name or '唯一约束'}):实例事实刚被他处写入,"
            "请重试")


async def _load_instance_overview(
    db: Any, *, service_name: str | None = None,
) -> list[ServiceWithInstancesOut]:
    """服务×环境实例组合读模型(一次批量,不做逐服务 N+1)。

    实例存在性 = 该服务在该环境有 deployment 或 identity;登录口/
    版本线/说明/tags 从 system_env_instances 按 (service.system, env)
    联表 —— 同一系统下多个服务共享登录口。
    """
    svc_stmt = select(Service).order_by(Service.system, Service.name)
    if service_name is not None:
        svc_stmt = svc_stmt.where(Service.name == service_name)
    services = list((await db.execute(svc_stmt)).scalars())
    if not services:
        return []

    deps = list((await db.execute(select(Deployment))).scalars())
    idents = list((await db.execute(select(ServiceIdentity))).scalars())
    insts = list((await db.execute(select(SystemEnvInstance))).scalars())
    envs = {e.id: e.name for e in
            (await db.execute(select(Environment))).scalars()}
    tags_by_group = await _tags_by_group(
        db, {i.group_id for i in insts})

    dep_map = {(d.base_service, d.env_id): d.base_url for d in deps}
    ident_map: dict[tuple[str, int], list[ServiceIdentity]] = {}
    for ident in idents:
        ident_map.setdefault(
            (ident.base_service, ident.env_id), []).append(ident)
    inst_map = {(i.system, i.env_id): i for i in insts}

    out: list[ServiceWithInstancesOut] = []
    for svc in services:
        env_ids = {d.env_id for d in deps
                   if d.base_service == svc.name}
        env_ids |= {i.env_id for i in idents
                    if i.base_service == svc.name}
        instances: list[ServiceInstanceOut] = []
        for env_id in sorted(env_ids):
            inst = inst_map.get((svc.system, env_id))
            rows = sorted(ident_map.get((svc.name, env_id), []),
                          key=lambda r: r.alias_name)
            instances.append(ServiceInstanceOut(
                env_id=env_id, env_name=envs.get(env_id, ""),
                group_id=(inst.group_id if inst is not None else ""),
                tags=(tags_by_group.get(inst.group_id, [])
                      if inst is not None else []),
                base_url=dep_map.get((svc.name, env_id), ""),
                login_url=inst.login_url if inst is not None else "",
                line=inst.line if inst is not None else "",
                note=inst.note if inst is not None else "",
                identities=[InstanceIdentityOut(
                    alias_name=r.alias_name,
                    ref_mode=r.ref_mode,  # type: ignore[arg-type]
                    ref_username=r.ref_username or "",
                    display=r.display or "",
                ) for r in rows],
            ))
        out.append(ServiceWithInstancesOut(
            name=svc.name, system=svc.system,
            kind=svc.kind,  # type: ignore[arg-type]
            instances=instances))
    return out


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
    except Exception as e:  # noqa: BLE001 — 对账是增强,不可达不阻塞读面
        logger.warning("services: plate 目录对账不可达,reachable=false:{}", e)
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


@router.post("/import-catalog", response_model=ImportCatalogOut,
             response_model_by_alias=True)
async def import_catalog(
    user: MemberUser, body: ImportCatalogIn, db: DbSession,
) -> ImportCatalogOut:
    """批量登记 plate 目录服务(M5 对账横幅「立即批量映射」)。

    * 目标 = ``names``(空 = 目录中全部未登记);
    * 已登记 / 不在目录 → ``skipped``(不报错,幂等);
    * ``system`` 取目录聚合行(服务真实归属),``kind``:目录 ``sut`` →
    主档 ``plate``,``integration`` → ``integration``;可选目录缺席时
    不登记(与单条登记防错别字同口径);
    * plate 不可达 → ``plateReachable=false``,created 空(读面自足)。
    """
    from ..services import plate_client

    reachable = True
    try:
        rows = await plate_client.catalog_service_rows(refresh=True)
    except Exception as e:  # noqa: BLE001 — 目录不可达不阻塞主档
        logger.warning("services: plate 目录拉取失败,目录对账面降级:{}", e)
        rows = []
        reachable = False
    catalog = {r["name"]: r for r in rows if r.get("name")}
    existing = set((await db.execute(select(Service.name))).scalars().all())
    targets = body.names or sorted(set(catalog) - existing)
    created: list[str] = []
    skipped: list[str] = []
    for name in targets:
        meta = catalog.get(name)
        if meta is None or name in existing:
            skipped.append(name)
            continue
        row = Service(
            name=name,
            system=str(meta.get("system") or name.split("-")[0]),
            kind="integration" if meta.get("kind") == "integration" else "plate",
            abbr="", description="")
        db.add(row)
        existing.add(name)
        created.append(name)
    if created:
        await db.commit()
        from ..services import audit as audit_svc

        await audit_svc.record(
            db, actor_id=user.id,
            actor_name=user.display_name or user.username,
            action="service_registry.write", resource_type="service",
            resource_id=",".join(created)[:128],
            detail={"fn": "import_catalog", "created": created})
    return ImportCatalogOut(
        created=created, skipped=skipped,
        unregistered=sorted(set(catalog) - existing) if reachable else [],
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
        except Exception as e:  # noqa: BLE001 — plate 不可达放行(主档自足)
            logger.warning("services: 登记防错字对账不可达,放行登记:{}", e)
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
@router.get("/instance-overview", response_model=ServiceInstanceOverviewOut)
async def service_instance_overview(
    user: CurrentUser, db: DbSession,
) -> ServiceInstanceOverviewOut:
    """服务×环境实例组合读模型(编排器「服务范围/凭证映射」数据源)。

    实例 = 有 deployment 或 identity 的 (service, env);登录口/版本线/
    说明/tags 按 (service.system, env) 从 system_env_instances 联表。
    读全员;写面见 ``PUT /{service}/instances``。
    """
    return ServiceInstanceOverviewOut(
        services=await _load_instance_overview(db))


@router.get("/instances", response_model=list[InstanceOut])
async def list_instances(
    user: CurrentUser, db: DbSession,
    env_id: Annotated[int | None, Query(alias="envId", ge=1)] = None,
) -> list[InstanceOut]:
    """实例列表(可按环境过滤;环境配置页数据源)。

    一实例多标签:每个 (system, env) 行回带同组标签集(tags),前端按
    标签聚合展示。"""
    from ..models.environment import Environment as Env

    stmt = select(SystemEnvInstance, Env.name).join(
        Env, Env.id == SystemEnvInstance.env_id)
    if env_id is not None:
        stmt = stmt.where(SystemEnvInstance.env_id == env_id)
    rows = (await db.execute(stmt.order_by(
        SystemEnvInstance.system, SystemEnvInstance.env_id))).all()
    tags_by_group = await _tags_by_group(
        db, {inst.group_id for inst, _ in rows})
    return [InstanceOut(
        system=inst.system, env_id=inst.env_id, env_name=env_name,
        group_id=inst.group_id,
        tags=tags_by_group.get(inst.group_id, []),
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
    的落库面;``environments`` 的 lines 视图与本端点同表(line 字段)。

    一实例多标签:写入同步到同一 group_id 的全部标签行(组共享配置)。"""
    from ..models.environment import Environment as Env

    if await db.get(Env, env_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"environment not found: {env_id}")
    inst = await _sync_instance_fields(
        db, system, env_id,
        login_url=_checked_login_url(body.login_url),
        line=body.line, note=body.note)
    await db.commit()
    await db.refresh(inst)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="service_registry.write", resource_type="instance",
        resource_id=f"{system}/{env_id}",
        detail={"fn": "put", "loginUrl": inst.login_url, "line": inst.line})
    return await _instance_out(db, inst)


@router.put("/{service}/instances", response_model=ServiceInstanceOut)
async def put_service_instance(
    service: str, body: ServiceInstancePut,
    user: MemberUser, db: DbSession,
) -> ServiceInstanceOut:
    """创建/编辑「服务×环境」实例(ops.write,单事务)。

    * envId / envTag 二选一;自由标签不存在时自动登记为环境定义;
    * baseUrl → deployments(API 地址);
    * loginUrl/line/note → system_env_instances(登录口按系统×环境共享);
    * identity → 可选同时登记一条调用身份(别名全局唯一;只建声明,
      不建账户 —— 凭证走 ``POST /auths`` / 项目凭证端点)。

    新建实例至少要有 baseUrl 或 identity(否则没有可组合的实例事实)。
    任一写入失败整单回滚。
    """
    from sqlalchemy.exc import IntegrityError

    from ..services.service_aliases import (
        UnknownBaseService, create_alias_in_transaction)

    svc = (await db.execute(select(Service).where(
        Service.name == service))).scalar_one_or_none()
    if svc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, {
            "code": "service_not_found",
            "message": f"服务不在主档:{service} —— 请先在服务注册页登记"})

    if body.env_id is not None:
        env = await db.get(Environment, body.env_id)
        if env is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, {
                "code": "environment_not_found",
                "message": f"环境不存在:{body.env_id}"})
    else:
        env = await _find_or_create_env_by_tag(
            db, body.env_tag or "", user)
    env_id = int(env.id)

    existing_dep = (await db.execute(
        select(Deployment.id).where(
            Deployment.base_service == service,
            Deployment.env_id == env_id).limit(1))).scalar()
    existing_ident = (await db.execute(
        select(ServiceIdentity.id).where(
            ServiceIdentity.base_service == service,
            ServiceIdentity.env_id == env_id).limit(1))).scalar()
    if (body.base_url is None and body.identity is None
            and existing_dep is None and existing_ident is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {
            "code": "service_instance_empty",
            "message": "新建实例至少需要 API 地址或一条调用身份"})

    login_url = _checked_login_url(body.login_url)

    if body.base_url is not None:
        url = body.base_url.strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, {
                    "code": "deployment_url_invalid",
                    "message": "API 地址必须以 http:// 或 https:// 开头"})
        dep = (await db.execute(select(Deployment).where(
            Deployment.base_service == service,
            Deployment.env_id == env_id))).scalar_one_or_none()
        if dep is None:
            db.add(Deployment(base_service=service, env_id=env_id,
                              base_url=url))
        else:
            dep.base_url = url

    if any(v is not None
           for v in (login_url, body.line, body.note)):
        if not svc.system:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, {
                    "code": "service_system_missing",
                    "message": f"服务 {service} 未设置 system,"
                               "无法登记登录口/版本线"})
        await _sync_instance_fields(
            db, svc.system, env_id,
            login_url=login_url, line=body.line, note=body.note)

    if body.identity is not None:
        ident = body.identity
        taken = (await db.execute(
            select(ServiceIdentity.id).where(
                ServiceIdentity.alias_name == ident.alias_name).limit(1)
        )).scalar()
        if taken is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, {
                "code": "service_instance_identity_taken",
                "message": f"调用身份名已登记:{ident.alias_name}"})
        try:
            await create_alias_in_transaction(
                db, alias_name=ident.alias_name, kind=svc.kind,
                base_service=service, env_id=env_id,
                ref_mode=ident.ref_mode, ref_username=ident.ref_username,
                display=ident.display)
        except UnknownBaseService as e:
            raise HTTPException(status.HTTP_409_CONFLICT, {
                "code": "unknown_base_service", "message": str(e)}) from e
        except ValueError as e:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                str(e)) from e

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        # 按约束名分派(见 _instance_integrity_conflict):deployment/
        # 系统实例行竞态不再误报成身份撞名
        code, message = _instance_integrity_conflict(e)
        raise HTTPException(status.HTTP_409_CONFLICT,
                            {"code": code, "message": message}) from None

    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="service_registry.write", resource_type="service_instance",
        resource_id=f"{service}/{env_id}",
        detail={"fn": "put", "baseUrl": body.base_url,
                "loginUrl": login_url,
                "identity": (body.identity.alias_name
                             if body.identity is not None else None)})

    overview = await _load_instance_overview(db, service_name=service)
    for svc_out in overview:
        for inst in svc_out.instances:
            if inst.env_id == env_id:
                return inst
    raise HTTPException(  # 理论不可达:写入后组合视图缺失
        status.HTTP_404_NOT_FOUND,
        f"instance not found after write: {service}/{env_id}")


@router.put("/instances/{system}/{env_id}/tags", response_model=InstanceOut)
async def put_instance_tags(
    system: str, env_id: int, body: InstanceTagsIn,
    user: MemberUser, db: DbSession,
) -> InstanceOut:
    """实例标签编辑(ops.write):整组标签一次提交(双击编辑落点)。

    标签不存在 → 自动登记为环境定义;组内行增/删;新增行复制当前实例
    配置(登录口/版本线/说明),共享语义随组。最少保留一枚标签。
    目标环境已被该系统的**其它实例组**占用 → 409 instance_tag_conflict。"""
    inst = (await db.execute(
        select(SystemEnvInstance).where(
            SystemEnvInstance.system == system,
            SystemEnvInstance.env_id == env_id))).scalar_one_or_none()
    if inst is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"instance not found: {system}/{env_id}")
    names: list[str] = []
    for t in body.tags:
        n = t.strip()
        if n and n not in names:
            names.append(n)
    if not names:
        raise HTTPException(422, "at least one tag is required")
    envs = [await _find_or_create_env_by_tag(db, n, user) for n in names]
    target_ids = {e.id for e in envs}

    group_rows = (await db.execute(
        select(SystemEnvInstance).where(
            SystemEnvInstance.system == system,
            SystemEnvInstance.group_id == inst.group_id))).scalars().all()
    by_env = {r.env_id: r for r in group_rows}

    # 冲突:目标标签已有该系统的行,但属于别的实例组
    missing = target_ids - set(by_env)
    if missing:
        clash = (await db.execute(
            select(SystemEnvInstance).where(
                SystemEnvInstance.system == system,
                SystemEnvInstance.env_id.in_(missing)))).scalars().all()
        if clash:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {"code": "instance_tag_conflict",
                 "message": "目标标签已属于该系统的其它实例 —— "
                            "请先从那边移除该标签再挂到这里"})

    # 增:新标签行复制当前实例配置(组内共享)
    for e in envs:
        if e.id not in by_env:
            db.add(SystemEnvInstance(
                system=system, env_id=e.id, group_id=inst.group_id,
                login_url=inst.login_url, line=inst.line, note=inst.note))
    # 减:组内不再保留的行删除
    for old_env, row in by_env.items():
        if old_env not in target_ids:
            await db.delete(row)
    await db.commit()

    # 代表行:当前 env 仍在组里则用当前行,否则取组内第一枚标签
    rep = (await db.execute(
        select(SystemEnvInstance).where(
            SystemEnvInstance.system == system,
            SystemEnvInstance.group_id == inst.group_id).order_by(
            SystemEnvInstance.id).limit(1))).scalar_one_or_none()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="service_registry.write", resource_type="instance",
        resource_id=f"{system}/{env_id}",
        detail={"fn": "tags", "tags": names})
    return await _instance_out(db, rep)


@router.patch("/instances/{system}/{env_id}", response_model=InstanceOut)
async def move_instance(
    system: str, env_id: int, body: InstanceMove,
    user: MemberUser, db: DbSession,
) -> InstanceOut:
    """实例改标签(ops.write;单行搬移,兼容口)。

    多标签编辑的主入口是 PUT /instances/{system}/{env_id}/tags;本端点
    把该行搬到目标标签:目标行同组 → 合并(删源行);目标行属别的组 →
    409;目标不存在 → 改 env_id。"""
    from ..models.environment import Environment as Env

    has_id = body.env_id is not None
    has_tag = bool((body.env_tag or "").strip())
    if has_id == has_tag:
        raise HTTPException(
            422, "exactly one of envId / envTag is required")
    inst = (await db.execute(
        select(SystemEnvInstance).where(
            SystemEnvInstance.system == system,
            SystemEnvInstance.env_id == env_id))).scalar_one_or_none()
    if inst is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"instance not found: {system}/{env_id}")
    if has_tag:
        target_env = await _find_or_create_env_by_tag(db, body.env_tag, user)
        target_id = target_env.id
    else:
        assert body.env_id is not None
        if await db.get(Env, body.env_id) is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"environment not found: {body.env_id}")
        target_id = body.env_id
    rep = inst
    if target_id != env_id:
        target = (await db.execute(
            select(SystemEnvInstance).where(
                SystemEnvInstance.system == system,
                SystemEnvInstance.env_id == target_id))).scalar_one_or_none()
        if target is not None and target.group_id != inst.group_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {"code": "instance_target_exists",
                 "message": f"该系统在目标环境已有实例({system}/"
                            f"{target_id});请先处理目标实例再搬移"})
        from_env = inst.env_id
        if target is not None:
            # 同组合并:源行删除,目标行承接
            await db.delete(inst)
            rep = target
        else:
            inst.env_id = target_id
        await db.commit()
        await db.refresh(rep)
        from ..services import audit as audit_svc

        await audit_svc.record(
            db, actor_id=user.id,
            actor_name=user.display_name or user.username,
            action="service_registry.write", resource_type="instance",
            resource_id=f"{system}/{target_id}",
            detail={"fn": "move", "fromEnvId": from_env,
                    "toEnvId": target_id})
    return await _instance_out(db, rep)


@router.delete("/instances/{system}/{env_id}", status_code=204)
async def delete_instance(
    system: str, env_id: int, user: MemberUser, db: DbSession,
) -> None:
    """移除实例(ops.write):删除该实例**全部标签行**(登录口/版本线/
    说明);部署地址与身份条目按各自环境独立维护,不受影响。"""
    inst = (await db.execute(
        select(SystemEnvInstance).where(
            SystemEnvInstance.system == system,
            SystemEnvInstance.env_id == env_id))).scalar_one_or_none()
    if inst is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"instance not found: {system}/{env_id}")
    rows = (await db.execute(
        select(SystemEnvInstance).where(
            SystemEnvInstance.system == system,
            SystemEnvInstance.group_id == inst.group_id))).scalars().all()
    for row in rows:
        await db.delete(row)
    await db.commit()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="service_registry.write", resource_type="instance",
        resource_id=f"{system}/{env_id}", detail={"fn": "delete"})
