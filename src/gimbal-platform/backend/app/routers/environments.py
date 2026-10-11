"""环境组路由（Release v4.4 §11 V5 已定按 B）。

CRUD + lines 管理。环境声明「每个系统部署的是哪条版本线」——
版本线只能从 plate 已有的版本线中选择（平台不做 scheme 校验）。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy import select
from ..core.db import get_db

from app.models import Environment, User
from ..core.deps import CurrentUser


router = APIRouter(prefix="/environments", tags=["environments"])


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


@router.get("", response_model=list[EnvironmentView])
def list_environments(
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Any:
    stmt = select(Environment).order_by(Environment.name)
    return db.scalars(stmt).all()


@router.post("", response_model=EnvironmentView, status_code=201)
def create_environment(
    body: EnvironmentCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Any:
    existing = db.scalar(
        select(Environment).where(Environment.name == body.name))
    if existing:
        raise HTTPException(409, f"environment '{body.name}' already exists")
    env = Environment(
        name=body.name, description=body.description,
        lines=body.lines, owner_id=user.id)
    db.add(env)
    db.commit()
    db.refresh(env)
    return env


@router.get("/{env_id}", response_model=EnvironmentView)
def get_environment(
    env_id: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Any:
    env = db.get(Environment, env_id)
    if not env:
        raise HTTPException(404, "environment not found")
    return env


@router.put("/{env_id}", response_model=EnvironmentView)
def update_environment(
    env_id: int,
    body: EnvironmentUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Any:
    env = db.get(Environment, env_id)
    if not env:
        raise HTTPException(404, "environment not found")
    if body.description is not None:
        env.description = body.description
    if body.lines is not None:
        env.lines = body.lines
    db.commit()
    db.refresh(env)
    return env


@router.delete("/{env_id}", status_code=204)
def delete_environment(
    env_id: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> None:
    env = db.get(Environment, env_id)
    if not env:
        raise HTTPException(404, "environment not found")
    db.delete(env)
    db.commit()
