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
    tags = (await _tags_by_group(db, {inst.group_id})).get(inst.group_id, [])
    return InstanceOut(
        system=inst.system, env_id=inst.env_id, env_name=env_name,
        group_id=inst.group_id, tags=tags,
        login_url=inst.login_url, line=inst.line, note=inst.note,
        updated_at=(inst.updated_at.isoformat()
                    if inst.updated_at else None))


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
    except Exception:  # noqa: BLE001 — 目录不可达不阻塞主档
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
        if body.login_url is not None:
            row.login_url = body.login_url
        if body.line is not None:
            row.line = body.line
        if body.note is not None:
            row.note = body.note
    await db.commit()
    await db.refresh(inst)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id, actor_name=user.display_name or user.username,
        action="service_registry.write", resource_type="instance",
        resource_id=f"{system}/{env_id}",
        detail={"fn": "put", "loginUrl": inst.login_url, "line": inst.line})
    return await _instance_out(db, inst)


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
