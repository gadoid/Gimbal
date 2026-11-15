"""服务级元数据路由:服务注册页「说明」列的读写面。

读 = 登录用户(对齐部署表/环境组读门 —— 说明不是秘密,矩阵/子页都要
展示);写 = Admin+(ops.write,经 MemberUser,与部署表写面同级)。
upsert 语义:存在则覆写、不存在则建(目录服务名不做存在性校验 ——
目录来自 plate 代理,平台侧只存文本;写入审计 ``service_meta.write``)。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser, MemberUser
from ..models import ServiceMeta

router = APIRouter(prefix="/service-meta", tags=["service-meta"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class ServiceMetaOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    service_name: str = Field(alias="serviceName")
    description: str
    updated_at: str | None = Field(default=None, alias="updatedAt")


class ServiceMetaIn(BaseModel):
    description: str = Field(max_length=512)


def _out(m: ServiceMeta) -> ServiceMetaOut:
    return ServiceMetaOut(serviceName=m.service_name,
                          description=m.description,
                          updatedAt=m.updated_at.isoformat() if m.updated_at else None)


@router.get("", response_model=list[ServiceMetaOut],
            response_model_by_alias=True)
async def list_service_meta(user: CurrentUser, db: DbSession) -> Any:
    stmt = select(ServiceMeta).order_by(ServiceMeta.service_name)
    return [_out(m) for m in (await db.execute(stmt)).scalars().all()]


@router.put("/{service_name}", response_model=ServiceMetaOut,
            response_model_by_alias=True)
async def put_service_meta(
    service_name: str, body: ServiceMetaIn, user: MemberUser, db: DbSession,
) -> Any:
    m = await db.get(ServiceMeta, service_name)
    if m is None:
        m = ServiceMeta(service_name=service_name,
                        description=body.description, updated_by=user.id)
        db.add(m)
        op = "create"
    else:
        m.description = body.description
        m.updated_by = user.id
        op = "update"
    await db.commit()
    await db.refresh(m)

    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="service_meta.write", resource_type="service_meta",
        resource_id=service_name, resource_name=service_name,
        detail={"op": op, "description": m.description})
    return _out(m)
