"""服务别名路由(服务画像方案 §4.1;基础层)— 读全员 / 写 admin。

配置池语义同 carry(读开放、写收口):别名影响的是所有引用该服务的
场景的执行解析,写面收在 admin;``owner_user_id`` 字段承载个人默认 /
团队共享的语义区分,不等于编辑权限。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.page import PageOut
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser, CurrentUser, OperatorUser
from ..models.service_alias import ServiceAlias
from ..services import service_aliases
from ..services.service_aliases import UnknownBaseService

router = APIRouter(prefix="/service-aliases", tags=["service-aliases"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_CAMEL = ConfigDict(populate_by_name=True)


class AliasOut(BaseModel):
    model_config = _CAMEL

    alias_name: str = Field(alias="aliasName")
    base_service: str = Field(alias="baseService")
    # F4 方案 B:环境级端点默认层(物化优先级链第三档;NULL = 不提供)
    base_url: str | None = Field(default=None, alias="baseUrl")
    group_tag: str | None = Field(default=None, alias="groupTag")
    credential_alias: str | None = Field(default=None, alias="credentialAlias")
    owner_user_id: int | None = Field(default=None, alias="ownerUserId")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class AliasListOut(PageOut[AliasOut]):
    """M4 Page 信封(§6.3)。"""


class AliasCreate(BaseModel):
    model_config = _CAMEL

    alias_name: str = Field(min_length=1, max_length=128, alias="aliasName")
    # 2026-09-23 调整:别名 = 环境端点的登记,URL 必填(缺省/空串 422);
    # patch 保持可空兼容(存量行可在触达时补齐)。
    base_url: str = Field(min_length=1, max_length=512, alias="baseUrl")
    group_tag: str | None = Field(default=None, max_length=64, alias="groupTag")
    credential_alias: str | None = Field(
        default=None, max_length=64, alias="credentialAlias")
    owner_user_id: int | None = Field(default=None, alias="ownerUserId")


class AliasPatch(BaseModel):
    model_config = _CAMEL

    base_url: str | None = Field(
        default=None, max_length=512, alias="baseUrl")
    group_tag: str | None = Field(default=None, max_length=64, alias="groupTag")
    credential_alias: str | None = Field(
        default=None, max_length=64, alias="credentialAlias")


@router.get("", response_model=AliasListOut)
async def list_aliases(
    user: CurrentUser, db: DbSession,
    base: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> AliasListOut:
    """M4(§6.3):Page 信封 + ``q``(alias/base/credential 子串)下推。"""
    items, total = await service_aliases.list_aliases(
        db, base=base, q=q, page=page, page_size=page_size)
    return AliasListOut(
        items=[AliasOut.model_validate(a) for a in items],
        total=total, page=page, page_size=page_size,
    )


@router.post("", response_model=AliasOut, status_code=201)
async def create_alias(
    user: OperatorUser, body: AliasCreate, db: DbSession,
) -> AliasOut:
    """登记别名(M2.5,权限方案 §1.2 两类归属拆行):
    团队共享(owner_user_id 空)= operator+;个人默认(owner_user_id
    非空,即「归属字段」)= admin —— 人事/内容权不落进技术运营角色。"""
    if body.owner_user_id is not None and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_only: personal aliases (ownerUserId) are managed by admins",
        )
    try:
        created = await service_aliases.create_alias(
            db, alias_name=body.alias_name, group_tag=body.group_tag,
            credential_alias=body.credential_alias,
            owner_user_id=body.owner_user_id,
            base_url=body.base_url,
        )
    except UnknownBaseService as e:
        # 强约束(§4.1 拍板):裸声明不猜;plate 宕机期间不能登记
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="alias.write", resource_type="alias",
        resource_id=body.alias_name, detail={"fn": "create"},
    )
    return AliasOut.model_validate(created)


@router.patch("/{alias_name}", response_model=AliasOut)
async def patch_alias(
    alias_name: str, user: OperatorUser, body: AliasPatch, db: DbSession,
) -> AliasOut:
    """改别名:共享行 operator+;个人行 admin(归属域的写权只属 admin)。"""
    row = (await db.execute(
        select(ServiceAlias).where(ServiceAlias.alias_name == alias_name)
    )).scalar_one_or_none()
    if row is not None and row.owner_user_id is not None and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_only: personal aliases are managed by admins",
        )
    try:
        explicit_group = ("group_tag" in body.model_fields_set
                          or "groupTag" in body.model_fields_set)
        explicit_cred = ("credential_alias" in body.model_fields_set
                         or "credentialAlias" in body.model_fields_set)
        explicit_url = ("base_url" in body.model_fields_set
                        or "baseUrl" in body.model_fields_set)
        patched = await service_aliases.patch_alias(
            db, alias_name,
            group_tag=body.group_tag if explicit_group else ...,
            credential_alias=body.credential_alias if explicit_cred else ...,
            base_url=body.base_url if explicit_url else ...,
        )
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="alias.write", resource_type="alias",
        resource_id=alias_name, detail={"fn": "patch"},
    )
    return AliasOut.model_validate(patched)


@router.delete("/{alias_name}", status_code=204)
async def delete_alias(
    alias_name: str, user: OperatorUser, db: DbSession
) -> None:
    row = (await db.execute(
        select(ServiceAlias).where(ServiceAlias.alias_name == alias_name)
    )).scalar_one_or_none()
    if row is not None and row.owner_user_id is not None and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_only: personal aliases are managed by admins",
        )
    await service_aliases.delete_alias(db, alias_name)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="alias.write", resource_type="alias",
        resource_id=alias_name, detail={"fn": "delete"},
    )
