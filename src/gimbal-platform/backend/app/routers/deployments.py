"""部署表路由(authz M2a S2.2):(基础服务, 环境) → 地址。

读 = 登录用户(地址不是秘密,编排/运行面要展示将生效的地址);写 =
Admin+(ops.write,与环境组写面同级的团队共享配置)。同键重复 409;
审计 ``deployment.write``。S6 起部署表是地址的唯一来源(别名自带地址
随 0047 退役;S2 的「冲突裁定」读面一并退役,0047 的未落行冲突进迁移
报告与 Admin 通知)。
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, MemberUser
from ..models import Deployment, Environment

router = APIRouter(prefix="/deployments", tags=["deployments"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_CAMEL = ConfigDict(populate_by_name=True)


def _check_url(v: str) -> str:
    v = (v or "").strip()
    if not (v.startswith("http://") or v.startswith("https://")):
        raise ValueError("baseUrl 必须以 http:// 或 https:// 开头")
    return v


class DeploymentIn(BaseModel):
    model_config = _CAMEL
    base_service: str = Field(min_length=1, max_length=128,
                              alias="baseService")
    env_id: int = Field(ge=1, alias="envId")
    base_url: str = Field(min_length=1, max_length=512, alias="baseUrl")

    @field_validator("base_url")
    @classmethod
    def _url(cls, v: str) -> str:
        return _check_url(v)


class DeploymentPatch(BaseModel):
    model_config = _CAMEL
    base_url: str = Field(min_length=1, max_length=512, alias="baseUrl")

    @field_validator("base_url")
    @classmethod
    def _url(cls, v: str) -> str:
        return _check_url(v)


class DeploymentOut(BaseModel):
    model_config = _CAMEL
    id: int
    base_service: str = Field(alias="baseService")
    env_id: int = Field(alias="envId")
    base_url: str = Field(alias="baseUrl")


def _out(d: Deployment) -> DeploymentOut:
    return DeploymentOut(id=d.id, baseService=d.base_service,
                         envId=d.env_id, baseUrl=d.base_url)


async def _audit(db, user, op: str, d: Deployment, extra: dict) -> None:
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="deployment.write", resource_type="deployment",
        resource_id=str(d.id), resource_name=f"{d.base_service}@{d.env_id}",
        detail={"op": op, "baseService": d.base_service,
                "envId": d.env_id, **extra})


@router.get("", response_model=list[DeploymentOut],
            response_model_by_alias=True)
async def list_deployments(
    user: CurrentUser, db: DbSession,
    env_id: Annotated[int | None, Query(alias="envId", ge=1)] = None,
) -> Any:
    stmt = select(Deployment).order_by(Deployment.env_id,
                                       Deployment.base_service)
    if env_id is not None:
        stmt = stmt.where(Deployment.env_id == env_id)
    return [_out(d) for d in (await db.execute(stmt)).scalars().all()]


@router.post("", response_model=DeploymentOut, status_code=201,
             response_model_by_alias=True)
async def create_deployment(
    body: DeploymentIn, user: MemberUser, db: DbSession,
) -> Any:
    if await db.get(Environment, body.env_id) is None:
        raise HTTPException(404, detail={
            "code": "environment_not_found",
            "message": f"environment not found: {body.env_id}"})
    d = Deployment(base_service=body.base_service, env_id=body.env_id,
                   base_url=body.base_url)
    db.add(d)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, detail={
            "code": "deployment_exists",
            "message": f"{body.base_service} 在该环境已有部署地址"}) from None
    await db.refresh(d)
    await _audit(db, user, "create", d, {"baseUrl": d.base_url})
    return _out(d)


@router.patch("/{deployment_id}", response_model=DeploymentOut,
              response_model_by_alias=True)
async def patch_deployment(
    deployment_id: int, body: DeploymentPatch,
    user: MemberUser, db: DbSession,
) -> Any:
    d = await db.get(Deployment, deployment_id)
    if d is None:
        raise HTTPException(404, detail={
            "code": "deployment_not_found",
            "message": f"deployment not found: {deployment_id}"})
    before = d.base_url
    d.base_url = body.base_url
    d.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(d)
    await _audit(db, user, "update", d,
                 {"from": before, "baseUrl": d.base_url})
    return _out(d)


@router.delete("/{deployment_id}", status_code=204)
async def delete_deployment(
    deployment_id: int, user: MemberUser, db: DbSession,
) -> None:
    d = await db.get(Deployment, deployment_id)
    if d is None:
        raise HTTPException(404, detail={
            "code": "deployment_not_found",
            "message": f"deployment not found: {deployment_id}"})
    snap = Deployment(id=d.id, base_service=d.base_service,
                      env_id=d.env_id, base_url=d.base_url)
    await db.delete(d)
    await db.commit()
    await _audit(db, user, "delete", snap, {"baseUrl": snap.base_url})
