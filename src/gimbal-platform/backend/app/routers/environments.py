"""环境路由（Release v4.4 §11 V5 已定按 B;重构 2026-11-16 版本线迁实例）。

CRUD + lines 管理(读面形状不变)。环境声明「每个系统部署的是哪条
版本线」—— 版本线只能从 plate 已有的版本线中选择（平台不做 scheme
校验）;**落库点已迁 ``system_env_instances.line``**（重构 §1.2 收口:
(系统, 环境) 的全部部署事实一处),本路由负责 lines 视图 ↔ 实例行的
双向同步。写面统一 ops.write（Admin+，经 MemberUser）：lines 影响所有
引用该环境的执行语义，是团队共享配置;owner_id 仅作创建溯源展示，
不构成写门。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, MemberUser
from ..models import Environment
from ..models.system_env_instance import SystemEnvInstance
from ..services.env_chain import instance_lines

router = APIRouter(prefix="/environments", tags=["environments"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class EnvironmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = ""
    lines: dict[str, str] = Field(default_factory=dict,
                                   description="{系统名: 版本线}")


class EnvironmentUpdate(BaseModel):
    description: str | None = None
    lines: dict[str, str] | None = None


class EnvironmentView(BaseModel):
    id: int
    name: str
    description: str
    # 聚合自实例行(instance_lines);API 形状不变(前端零适配)
    lines: dict[str, str] = Field(default_factory=dict)
    owner_id: int | None = None
    # S2:默认环境(环境链末位兜底,D2);visibility 随 0044 删除
    is_default: bool = False


async def _view(db: AsyncSession, env: Environment) -> EnvironmentView:
    return EnvironmentView(
        id=env.id, name=env.name, description=env.description,
        lines=await instance_lines(db, env.id),
        owner_id=env.owner_id, is_default=env.is_default)


async def _sync_instance_lines(
    db: AsyncSession, env_id: int, lines: dict[str, str],
) -> None:
    """lines 视图 ↔ 实例行 upsert:有声明的系统 upsert ``line``;未声明
    的既有实例行 line 置空(**不删行** —— 实例行还承载 login_url)。"""
    rows = (await db.execute(select(SystemEnvInstance).where(
        SystemEnvInstance.env_id == env_id))).scalars().all()
    by_system = {r.system: r for r in rows}
    for sysname, ln in sorted(lines.items()):
        row = by_system.get(sysname)
        if row is None:
            db.add(SystemEnvInstance(
                system=sysname, env_id=env_id, line=str(ln or "")))
        else:
            row.line = str(ln or "")
    declared = set(lines)
    for sysname, row in by_system.items():
        if sysname not in declared:
            row.line = ""


async def _validate_lines(db: AsyncSession, lines: dict[str, str]) -> None:
    """b2-8(归一 v1.0 §3.3):integration 系统无版本,环境不得为其声明
    版本线(kind 预检;plate 不可达时跳过 —— 与保存端
    validate_meta_plate_refs 的「不可达跳过」口径一致)。"""
    from ..services import plate_client

    try:
        for sysname in lines:
            if await plate_client.get_system_kind(sysname) == "integration":
                raise HTTPException(
                    422, f"integration_system_no_lines: {sysname} 是 "
                    "kind=integration 的系统(第三方不发版),环境不能"
                    "为其声明版本线")
    except (plate_client.PlateUnavailableError,
            plate_client.PlateRejectedError):
        pass  # plate 异常跳过(环境是配置面;执行期门仍在)


@router.get("", response_model=list[EnvironmentView])
async def list_environments(
    user: CurrentUser, db: DbSession,
) -> Any:
    rows = (await db.execute(
        select(Environment).order_by(Environment.name)
    )).scalars().all()
    return [await _view(db, env) for env in rows]


@router.post("", response_model=EnvironmentView, status_code=201)
async def create_environment(
    body: EnvironmentCreate,
    user: MemberUser, db: DbSession,
) -> Any:
    existing = (await db.execute(
        select(Environment).where(Environment.name == body.name)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, f"environment '{body.name}' already exists")
    await _validate_lines(db, body.lines)
    env = Environment(
        name=body.name, description=body.description, owner_id=user.id)
    db.add(env)
    await db.flush()  # 拿 env.id 供实例行挂靠
    await _sync_instance_lines(db, env.id, body.lines)
    await db.commit()
    await db.refresh(env)
    # authz W9-3:环境写操作补审计(对比 users.py 写法;配置面变更留痕)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="environment.write", resource_type="environment",
        resource_id=str(env.id), resource_name=env.name,
        detail={"op": "create", "lines": body.lines})
    return await _view(db, env)


@router.get("/{env_id}", response_model=EnvironmentView)
async def get_environment(
    env_id: int,
    user: CurrentUser, db: DbSession,
) -> Any:
    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(404, "environment not found")
    return await _view(db, env)


@router.put("/{env_id}", response_model=EnvironmentView)
async def update_environment(
    env_id: int,
    body: EnvironmentUpdate,
    user: MemberUser, db: DbSession,
) -> Any:
    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(404, "environment not found")
    if body.description is not None:
        env.description = body.description
    if body.lines is not None:
        await _validate_lines(db, body.lines)
        await _sync_instance_lines(db, env.id, body.lines)
    await db.commit()
    await db.refresh(env)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="environment.write", resource_type="environment",
        resource_id=str(env.id), resource_name=env.name,
        detail={"op": "update",
                "description": body.description, "lines": body.lines})
    return await _view(db, env)


@router.post("/{env_id}/default", response_model=EnvironmentView)
async def set_default_environment(
    env_id: int, user: MemberUser, db: DbSession,
) -> Any:
    """置为默认环境(D2:环境链末位兜底,Admin+ 指定)。原子切换:同一
    事务里先清旧默认再置新默认;部分唯一索引兜并发(撞索引 → 409)。"""
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(404, "environment not found")
    await db.execute(update(Environment).where(
        Environment.is_default.is_(True), Environment.id != env_id
    ).values(is_default=False))
    env.is_default = True
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "default environment changed concurrently; "
                                 "retry") from None
    await db.refresh(env)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="environment.write", resource_type="environment",
        resource_id=str(env.id), resource_name=env.name,
        detail={"op": "set_default"})
    return await _view(db, env)


@router.delete("/{env_id}/default", response_model=EnvironmentView)
async def unset_default_environment(
    env_id: int, user: MemberUser, db: DbSession,
) -> Any:
    """取消默认(之后无默认环境:没显式选环境的执行在环境链末位悬空,
    身份条目解析将明确报「未指定环境」,预检可见)。"""
    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(404, "environment not found")
    if env.is_default:
        env.is_default = False
        await db.commit()
        await db.refresh(env)
        from ..services import audit as audit_svc

        await audit_svc.record(
            db, actor_id=user.id,
            actor_name=user.display_name or user.username,
            action="environment.write", resource_type="environment",
            resource_id=str(env.id), resource_name=env.name,
            detail={"op": "unset_default"})
    return await _view(db, env)


@router.delete("/{env_id}", status_code=204)
async def delete_environment(
    env_id: int,
    user: MemberUser, db: DbSession,
) -> None:
    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(404, "environment not found")
    # 账户是密文资产,不随环境级联(NO ACTION)—— 有引用先 409 提示处置;
    # 身份条目/部署行/实例行随环境级联删(FK CASCADE)
    from ..models.auth_account import AuthAccount

    used = (await db.execute(
        select(AuthAccount.id).where(AuthAccount.env_id == env_id)
        .limit(1))).scalar()
    if used is not None:
        raise HTTPException(
            409, "environment_in_use_accounts: 该环境下仍有登录账户,"
            "请先删除或迁移这些账户(改密/账户归档是资产处置,不随环境级联)")
    name = env.name
    await db.delete(env)
    await db.commit()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="environment.write", resource_type="environment",
        resource_id=str(env_id), resource_name=name,
        detail={"op": "delete"})
