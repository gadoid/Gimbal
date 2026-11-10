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
        return ("user", user.id)
    raise HTTPException(422, detail={
        "code": "bad_scope",
        "message": "scope ∈ global | project | user"})


def _svc_map(rows) -> dict[str, dict[str, str | None]]:
    out: dict[str, dict[str, str | None]] = {}
    for r in rows:
        out.setdefault(r.service_name, {})[r.field_path] = r.value
    return out


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
    前层(与运行时 tier 同序),flat bindings = 合并视图,rows 带层。"""
    scopes = await carry_store.visible_scopes(db, user)
    rank = {sc: i for i, sc in enumerate(scopes)}
    rows = sorted(
        (r for r in (await db.execute(
            select(CarryServiceBinding))).scalars().all()
         if (r.scope, r.scope_id) in scopes),
        key=lambda r: rank[(r.scope, r.scope_id)])
    merged = _svc_map(rows)   # tier 序在后 → 同键覆盖(tier 靠后者赢)
    return BindingsOut(
        bindings=merged,
        rows=[{"scope": r.scope, "scopeId": r.scope_id,
               "serviceName": r.service_name, "fieldPath": r.field_path,
               "value": r.value} for r in rows])


@router.get("/bindings/{service}", response_model=ServiceBindingsOut)
async def get_bindings(
    service: str, user: CurrentUser, db=DbSession,
    scope: Annotated[str, Query(pattern="^(global|project|user)$")] = "global",
    project_id: Annotated[int | None, Query(alias="projectId", ge=1)] = None,
):
    sc = await _resolve_scope(db, user, scope, project_id, write=False)
    return ServiceBindingsOut(
        bindings=await carry_store.get_bindings(db, service, sc),
        scope=sc[0], scopeId=sc[1])


@router.put("/bindings/{service}", response_model=ServiceBindingsOut)
async def put_bindings(
    service: str, user: CurrentUser, body: CarryMapIn, db=DbSession,
    scope: Annotated[str, Query(pattern="^(global|project|user)$")] = "global",
    project_id: Annotated[int | None, Query(alias="projectId", ge=1)] = None,
):
    sc = await _resolve_scope(db, user, scope, project_id, write=True)
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
    无从归一,原样过滤 —— 退化为修复前行为,而不是全局面瘫痪。"""
    from ..schemas.carry import CarryEndpointMini
    from ..services import service_names
    from ..services.adaptation_service import _plate_full_endpoint

    # b2-9(D-M):别名表优先;未登记裸键走目录 derive_base,降级语义
    # 不变(plate 不可达 → 按原样服务名查,退化为修复前行为)。
    base = await service_names.resolve_base_with_aliases(db, service)
    if base is None:
        base = service
    try:
        client_items = await _plate_list_endpoints_filtered(base)
    except PlateUnavailableError as e:
        raise _plate_502(e) from e
    faces: dict[str, CarryFieldFace] = {}
    degraded = False
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
