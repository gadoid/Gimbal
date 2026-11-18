"""carry 配置面路由(spec §3.2):读 CurrentUser(编排器提示要用),
写面按层分权(authz M2a S4):``?scope=global``(默认,兼容旧客户端)=
公共项目层,ops.write;``?scope=project&projectId=`` = 项目层,项目管理员;
``?scope=user`` = 个人层,本人(普通用户可写自己的层)。字段面聚合走
plate /full。

读面(10.5):列表/单服务读返回**可见层并集**(公共项目 + 我所在项目 +
我的个人层);响应带逐行 scope 标签,flat `bindings` 仍为合并视图
(编排器提示的既有消费面零变化)。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, MemberUser
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
from ..services.field_state_resolution import carry_entries
from ..services.plate_client import PlateUnavailableError
from ._error_mapping import _plate_502

router = APIRouter(prefix="/carry", tags=["carry"])

DbSession = Depends(get_db)


async def _notify_shadow(db, sc, service: str | None, old: dict,
                         new: dict, actor_name: str) -> None:
    """S7.6:公共层写后的项目层遮蔽通知(best-effort,失败仅记日志)。"""
    from ..services import carry_shadow

    try:
        await carry_shadow.notify_public_carry_change(
            db, scope=sc, service=service, old=old, new=new,
            actor_name=actor_name)
    except Exception:  # noqa: BLE001 — 通知是增强,不是写面前置
        logger.opt(exception=True).warning("carry: shadow notify failed")


async def _resolve_scope(
    db, user, scope: str, project_id: int | None,
    *, write: bool,
) -> "tuple[str, int]":
    """查询参数 → 作用域元组 + 分权。读面:global/user 不设门(可见层
    并集在端点内过滤);project = 项目成员(r3二.2:项目层 carry 是
    项目内共享值,非成员 404 —— 此前读面完全不设门)。写面:global=
    ops.write(MemberUser 已挡)、project=项目管理员 ∨ Admin+、user=
    本人。"""
    if scope == "global":
        from ._ownership import has_capability

        if write and not has_capability(user, "ops.write"):
            raise HTTPException(403, detail={
                "code": "capability_required",
                "message": "全局(公共项目)层 carry 由 Admin+ 维护"})
        return await carry_store.public_scope(db)
    if scope == "project":
        if project_id is None:
            raise HTTPException(422, detail={
                "code": "project_id_required",
                "message": "scope=project 需要 projectId"})
        from ..models.project import Project, ProjectMember
        if await db.get(Project, project_id) is None:
            raise HTTPException(404, detail={
                "code": "not_found",
                "message": f"project not found: {project_id}"})
        from ._ownership import has_capability

        if write and has_capability(user, "ops.write"):
            return ("project", project_id)   # Admin+ 写旁路照旧(漂移同门)
        role = (await db.execute(select(ProjectMember.role).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id))).scalar_one_or_none()
        if role is None:
            raise HTTPException(404, detail={
                "code": "not_found",
                "message": f"project not found: {project_id}"})
        if write and role != "admin":
            raise HTTPException(403, detail={
                "code": "not_project_admin",
                "message": "项目层 carry 由项目管理员维护"})
        return ("project", project_id)
    if scope == "user":
        # 决策 8(执行配置分层⑥):个人层已收编为默认执行配置 —— 迁后
        # 停读、不做双源回落;本面 422 指路,不再接受读写
        raise HTTPException(422, detail={
            "code": "carry_user_scope_retired",
            "message": "个人 carry 层已收编为默认执行配置 —— 请在"
                       "/exec-configs 的默认配置里维护覆盖值"})
    raise HTTPException(422, detail={
        "code": "bad_scope",
        "message": "scope ∈ global | project | user"})


def _svc_map(rows) -> dict[str, dict[str, str | None]]:
    out: dict[str, dict[str, str | None]] = {}
    for r in rows:
        if r.instance_env_id:
            continue  # §8.9 实例行不进 flat 合并视图(逐实例维护面另读)
        out.setdefault(r.config_key, {})[r.field_path] = r.value
    return out


async def _reject_pure_system_key(db, service: str) -> None:
    """§8.9:裸系统名不再是合法值表键(系统档退场,实例档接棒 —— 按部署
    差异化走 ``/bindings/{system}/instances/{envId}``)。同名碰撞(键既是
    服务名又是系统名)按服务名放行 —— 服务档行合法。"""
    if await carry_store.is_pure_system_key(db, service):
        raise HTTPException(422, detail={
            "code": "carry_system_key_retired",
            "message": "系统级 carry 键已退场 —— 按部署差异化请写实例档 "
                       f"PUT /carry/bindings/{service}/instances/{{envId}}"
                       "(坐标 = 系统 × 环境)"})


async def _require_instance_key(db, system: str, env_id: int) -> None:
    """§8.9 实例键校验:system 须命中主档系统名(有成员服务)、
    (system, env) 须存在实例行 —— 实例是值的宿主,未接入的环境无档。"""
    from ..models.service import Service as DBService
    from ..models.system_env_instance import SystemEnvInstance

    members = (await db.execute(
        select(DBService.id).where(DBService.system == system).limit(1))
    ).scalar() is not None
    if not members:
        raise HTTPException(404, detail={
            "code": "not_found",
            "message": f"主档无系统 {system!r}(实例键 = 系统名 × 环境)"})
    inst = (await db.execute(
        select(SystemEnvInstance.id).where(
            SystemEnvInstance.system == system,
            SystemEnvInstance.env_id == env_id).limit(1))).scalar() is not None
    if not inst:
        raise HTTPException(404, detail={
            "code": "not_found",
            "message": f"系统 {system!r} 在环境 #{env_id} 没有实例行 —— "
                       "先在服务注册接入实例(登记登录口/API 地址)"})


@router.get("/defaults", response_model=DefaultsOut)
async def get_defaults(
    user: CurrentUser, db=DbSession,
    scope: Annotated[str, Query(pattern="^(global|project|user)$")] = "global",
    project_id: Annotated[int | None, Query(alias="projectId", ge=1)] = None,
):
    sc = await _resolve_scope(db, user, scope, project_id, write=False)
    return DefaultsOut(defaults=await carry_store.get_defaults(db, sc),
                       scope=sc[0], scopeId=sc[1])


@router.put("/defaults", response_model=DefaultsOut)
async def put_defaults(
    user: CurrentUser, body: DefaultsIn, db=DbSession,
    scope: Annotated[str, Query(pattern="^(global|project|user)$")] = "global",
    project_id: Annotated[int | None, Query(alias="projectId", ge=1)] = None,
):
    sc = await _resolve_scope(db, user, scope, project_id, write=True)
    old = await carry_store.get_defaults(db, sc)
    await carry_store.put_defaults(
        db, body.defaults,
        updated_by_id=user.id,
        updated_by_name=user.display_name or user.username,
        scope=sc,
    )
    await db.commit()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="carry.write", resource_type="carry", resource_id="defaults",
        detail={"keys": sorted((body.defaults or {}).keys()),
                "scope": sc[0], "scopeId": sc[1]},
    )
    # S7.6:公共层写 → 项目层同键遮蔽通知(非公共层内部直通)
    await _notify_shadow(db, sc, None, old, body.defaults or {},
                         user.display_name or user.username)
    return DefaultsOut(defaults=await carry_store.get_defaults(db, sc),
                       scope=sc[0], scopeId=sc[1])


@router.get("/bindings", response_model=BindingsOut)
async def list_bindings(user: CurrentUser, db=DbSession):
    """可见层并集(公共项目 + 我所在项目 + 我的个人层);后层覆盖
    前层(与运行时 tier 同序),flat bindings = 合并视图,rows 带层。
    §8.9:仅基线行(条目/服务档)—— 实例档行逐实例维护,不进 flat 面。"""
    scopes = await carry_store.visible_scopes(db, user)
    rank = {sc: i for i, sc in enumerate(scopes)}
    rows = sorted(
        (r for r in (await db.execute(
            select(CarryServiceBinding))).scalars().all()
         if (r.scope, r.scope_id) in scopes and not r.instance_env_id),
        key=lambda r: rank[(r.scope, r.scope_id)])
    merged = _svc_map(rows)   # tier 序在后 → 同键覆盖(tier 靠后者赢)
    return BindingsOut(
        bindings=merged,
        rows=[{"scope": r.scope, "scopeId": r.scope_id,
               "serviceName": r.config_key, "fieldPath": r.field_path,
               "value": r.value} for r in rows])


@router.get("/bindings/{service}", response_model=ServiceBindingsOut)
async def get_bindings(
    service: str, user: CurrentUser, db=DbSession,
    scope: Annotated[str, Query(pattern="^(global|project|user)$")] = "global",
    project_id: Annotated[int | None, Query(alias="projectId", ge=1)] = None,
):
    """读某键的生效绑定(基线层:条目/服务档键;系统档已退场 §8.9,
    实例档走 ``/bindings/{system}/instances/{envId}``)。"""
    sc = await _resolve_scope(db, user, scope, project_id, write=False)
    await _reject_pure_system_key(db, service)
    return ServiceBindingsOut(
        bindings=await carry_store.get_bindings(db, service, sc),
        scope=sc[0], scopeId=sc[1])


@router.put("/bindings/{service}", response_model=ServiceBindingsOut)
async def put_bindings(
    service: str, user: CurrentUser, body: CarryMapIn, db=DbSession,
    scope: Annotated[str, Query(pattern="^(global|project|user)$")] = "global",
    project_id: Annotated[int | None, Query(alias="projectId", ge=1)] = None,
):
    """替换坐标 = (scope, config_key, 基线行);系统档已退场(§8.9)。"""
    sc = await _resolve_scope(db, user, scope, project_id, write=True)
    await _reject_pure_system_key(db, service)
    old = await carry_store.get_bindings(db, service, sc)
    await carry_store.put_bindings(
        db, service, body.bindings,
        updated_by_id=user.id,
        updated_by_name=user.display_name or user.username,
        scope=sc,
    )
    await db.commit()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="carry.write", resource_type="carry", resource_id=service,
        detail={"service": service, "scope": sc[0], "scopeId": sc[1]},
    )
    # S7.6:公共层写 → 项目层同键遮蔽通知(非公共层内部直通)
    await _notify_shadow(db, sc, service, old, body.bindings or {},
                         user.display_name or user.username)
    return ServiceBindingsOut(
        bindings=await carry_store.get_bindings(db, service, sc),
        scope=sc[0], scopeId=sc[1])


@router.get("/bindings/{system}/instances/{env_id}",
            response_model=ServiceBindingsOut)
async def get_instance_bindings(
    system: str, env_id: int, user: CurrentUser, db=DbSession,
    scope: Annotated[str, Query(pattern="^(global|project|user)$")] = "global",
    project_id: Annotated[int | None, Query(alias="projectId", ge=1)] = None,
):
    """§8.9 实例档读:坐标 = (scope, 系统名, 环境) —— 部署级默认值
    (测试/预发布/生产同字段不同值);链序 条目 > 实例 > 服务 > 层默认。"""
    sc = await _resolve_scope(db, user, scope, project_id, write=False)
    await _require_instance_key(db, system, env_id)
    return ServiceBindingsOut(
        bindings=await carry_store.get_instance_bindings(
            db, system, env_id, sc),
        scope=sc[0], scopeId=sc[1])


@router.put("/bindings/{system}/instances/{env_id}",
            response_model=ServiceBindingsOut)
async def put_instance_bindings(
    system: str, env_id: int, user: CurrentUser, body: CarryMapIn, db=DbSession,
    scope: Annotated[str, Query(pattern="^(global|project|user)$")] = "global",
    project_id: Annotated[int | None, Query(alias="projectId", ge=1)] = None,
):
    """§8.9 实例档整表替换:值对该系统全部服务在本环境生效(实例 =
    系统 × 环境,非单服务);权限门与裸键写面同口径(层 + Admin+)。"""
    sc = await _resolve_scope(db, user, scope, project_id, write=True)
    await _require_instance_key(db, system, env_id)
    old = await carry_store.get_instance_bindings(db, system, env_id, sc)
    await carry_store.put_instance_bindings(
        db, system, env_id, body.bindings,
        updated_by_id=user.id,
        updated_by_name=user.display_name or user.username,
        scope=sc,
    )
    await db.commit()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="carry.write", resource_type="carry",
        resource_id=f"{system}#{env_id}",
        detail={"service": system, "instanceEnvId": env_id,
                "scope": sc[0], "scopeId": sc[1]},
    )
    # S7.6:公共层写 → 项目层同键遮蔽通知(实例键坐标 = 系统×环境)
    await _notify_shadow(db, sc, system, old, body.bindings or {},
                         user.display_name or user.username)
    return ServiceBindingsOut(
        bindings=await carry_store.get_instance_bindings(
            db, system, env_id, sc),
        scope=sc[0], scopeId=sc[1])


@router.get("/drift", response_model=DriftReport)
async def drift(
    user: CurrentUser, db=DbSession,
    scope: Annotated[str, Query(pattern="^(global|project|user)$")] = "global",
    project_id: Annotated[int | None, Query(alias="projectId", ge=1)] = None,
):
    """S7.6 漂移按层:``global``(默认)= 公共项目层(Admin+);``project``
    = 项目层(项目管理员 ∨ Admin+);``user`` = 个人层(本人)。分权与
    写面同口径(``_resolve_scope(write=True)``)—— 漂移是维护视图,
    看层 = 能写层。"""
    sc = await _resolve_scope(db, user, scope, project_id, write=True)
    raw = await carry_store.carry_drift(db, scope=sc)
    return DriftReport(
        plateReachable=raw["plateReachable"],
        services=[ServiceDrift(**s) for s in raw["services"]],
        scope=sc[0], scopeId=sc[1])


@router.get("/bindings/{service}/fields", response_model=ServiceFieldsOut)
async def service_fields(service: str, user: MemberUser, db=DbSession):
    """该服务全部接口 carry 面并集:GET /api/endpoint?service= → 逐 id /full。
    任一端点 /full 失败(抛错或 404)→ degraded=True:面不完整,
    配置页整表替换保存会删不可见端点的绑定值,须据此禁存。

    键归一(配套方案 §2.3):``service`` 允许传别名全名 —— Plate 只认
    目录服务,先 ``derive_base`` 归一到 base 再过滤。裸声明键(目录内
    无此服务也无其 base)无面可言,返回空面且不标 degraded(空是确定
    结论,不是面不完整);目录本身不可得(services dim 失败 → 空集)时
    无从归一,原样过滤 —— 退化为修复前行为,而不是全局面瘫痪。

    三档键域的系统档(registry 重构 §1.7):键命中主档**系统名**(且自身
    不是已登记服务名)→ 面并集 = 该系统全部服务的声明并集(系统级值
    作用于系统内每个服务,面按并集给)。服务名键不受同名系统影响
    (写到别家服务的键上取不到值,并集面只会制造死值)。"""
    from ..schemas.carry import CarryEndpointMini
    from ..services import service_names
    from ..services.adaptation_service import _plate_full_endpoint

    # b2-9(D-M):别名表优先;未登记裸键走目录 derive_base,降级语义
    # 不变(plate 不可达 → 按原样服务名查,退化为修复前行为)。
    base = await service_names.resolve_base_with_aliases(db, service)
    if base is None:
        base = service
    # 系统档:纯系统名(非服务名)→ 成员服务并集;否则本键单面
    from ..models.service import Service as DBService

    is_service_name = (await db.execute(
        select(DBService.id).where(DBService.name == base))).scalar() is not None
    face_keys: list[str] = [base]
    if not is_service_name:
        members = (await db.execute(
            select(DBService.name).where(DBService.system == base)
        )).scalars().all()
        if members:
            face_keys = sorted(members)
    faces: dict[str, CarryFieldFace] = {}
    degraded = False
    for key in face_keys:
        try:
            client_items = await _plate_list_endpoints_filtered(key)
        except PlateUnavailableError as e:
            raise _plate_502(e) from e
        for item in client_items:
            try:
                full = await _plate_full_endpoint(item["id"])
            except PlateUnavailableError:
                degraded = True
                continue  # 降级:该端点面缺席,不阻塞其余
            if full is None:
                degraded = True
                continue
            # G6:贡献端点上下文(字段 → 服务内哪些接口声明了它)
            ep_mini = CarryEndpointMini(
                id=str(item.get("id") or ""),
                name=str(item.get("name") or ""),
                method=str(item.get("method") or ""),
                path=str(item.get("path") or ""),
            )
            # 解析态 == 'carry' 投影(2026-09-05 目录化 §4):面基准 =
            # entry.state 共识默认 —— 值表是环境级,不 join step 增量
            # (场景覆盖是 step 级意图,不改值表候选宇宙)。投影走
            # field_state_resolution 单一实现(与 carry_injection 同款,
            # 含祖先吸收:整容器是绑定/注入单元)。
            decls = ((full.get("request") or {}).get("declarations")) or []
            for entry in carry_entries(decls):
                path = str(entry.get("path") or "")
                face = faces.setdefault(path, CarryFieldFace(
                    path=path,
                    type=str(entry.get("type") or "string"),
                    description=str(entry.get("description") or ""),
                ))
                if ep_mini not in face.endpoints:
                    face.endpoints.append(ep_mini)
    return ServiceFieldsOut(fields=sorted(faces.values(), key=lambda f: f.path),
                            degraded=degraded)


async def _plate_list_endpoints_filtered(service: str) -> list[dict]:
    """轻量列表按 service 过滤(adaptation_service._plate_list_endpoints 复用)。"""
    from ..services.adaptation_service import _plate_list_endpoints

    items = await _plate_list_endpoints()
    return [it for it in items if it.get("service") == service]
