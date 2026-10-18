"""环境组路由（Release v4.4 §11 V5 已定按 B）。

CRUD + lines 管理。环境声明「每个系统部署的是哪条版本线」——
版本线只能从 plate 已有的版本线中选择（平台不做 scheme 校验）。
写面收在 owner/admin（迁移产生的无主行 → admin）：lines 影响所有
引用该环境的执行语义，是团队共享配置。
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
from ..models.service_alias import ServiceAlias

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
    visibility: str
    lines: dict[str, str]
    owner_id: int | None = None

    class Config:
        from_attributes = True


def _require_env_write(env: Environment, user: Any) -> None:
    if user.role != "admin" and env.owner_id != user.id:
        raise HTTPException(403, "environment writes are owner/admin only")


@router.get("", response_model=list[EnvironmentView])
async def list_environments(
    user: CurrentUser, db: DbSession,
) -> Any:
    rows = (await db.execute(
        select(Environment).order_by(Environment.name)
    )).scalars().all()
    return rows


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
    env = Environment(
        name=body.name, description=body.description,
        lines=body.lines, owner_id=user.id)
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


@router.get("/{env_id}", response_model=EnvironmentView)
async def get_environment(
    env_id: int,
    user: CurrentUser, db: DbSession,
) -> Any:
    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(404, "environment not found")
    return env


@router.put("/{env_id}", response_model=EnvironmentView)
async def update_environment(
    env_id: int,
    body: EnvironmentUpdate,
    user: MemberUser, db: DbSession,
) -> Any:
    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(404, "environment not found")
    _require_env_write(env, user)
    if body.description is not None:
        env.description = body.description
    if body.lines is not None:
        # b2-8(归一 v1.0 §3.3):integration 系统无版本,环境不得为其声明
        # 版本线(kind 预检;plate 不可达时跳过 —— 与保存端
        # validate_meta_plate_refs 的「不可达跳过」口径一致)。
        from ..services import plate_client

        try:
            for sysname in (body.lines or {}):
                if await plate_client.get_system_kind(sysname) == "integration":
                    raise HTTPException(
                        422, f"integration_system_no_lines: {sysname} 是 "
                        "kind=integration 的系统(第三方不发版),环境不能"
                        "为其声明版本线")
        except (plate_client.PlateUnavailableError,
                plate_client.PlateRejectedError):
            pass  # plate 异常跳过(环境是配置面;执行期门仍在)
        env.lines = body.lines
    await db.commit()
    await db.refresh(env)
    return env


@router.delete("/{env_id}", status_code=204)
async def delete_environment(
    env_id: int,
    user: MemberUser, db: DbSession,
) -> None:
    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(404, "environment not found")
    _require_env_write(env, user)
    # 引用检查：仍有服务别名指向该环境时拒绝删除（悬空外键防患）
    ref = (await db.execute(select(ServiceAlias.alias_name).where(
        ServiceAlias.environment_id == env_id).limit(1)
    )).scalar_one_or_none()
    if ref:
        raise HTTPException(
            409, f"environment is referenced by alias '{ref}'")
    await db.delete(env)
    await db.commit()
