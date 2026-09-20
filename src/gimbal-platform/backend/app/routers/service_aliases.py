"""服务别名路由(服务画像方案 §4.1;基础层)— 读全员 / 写 admin。

配置池语义同 carry(读开放、写收口):别名影响的是所有引用该服务的
场景的执行解析,写面收在 admin;``owner_user_id`` 字段承载个人默认 /
团队共享的语义区分,不等于编辑权限。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser, CurrentUser
from ..services import service_aliases
from ..services.service_aliases import UnknownBaseService

router = APIRouter(prefix="/service-aliases", tags=["service-aliases"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_CAMEL = ConfigDict(populate_by_name=True)


class AliasOut(BaseModel):
    model_config = _CAMEL

    alias_name: str = Field(alias="aliasName")
    base_service: str = Field(alias="baseService")
    group_tag: str | None = Field(default=None, alias="groupTag")
    credential_alias: str | None = Field(default=None, alias="credentialAlias")
    owner_user_id: int | None = Field(default=None, alias="ownerUserId")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class AliasCreate(BaseModel):
    model_config = _CAMEL

    alias_name: str = Field(min_length=1, max_length=128, alias="aliasName")
    group_tag: str | None = Field(default=None, max_length=64, alias="groupTag")
    credential_alias: str | None = Field(
        default=None, max_length=64, alias="credentialAlias")
    owner_user_id: int | None = Field(default=None, alias="ownerUserId")


class AliasPatch(BaseModel):
    model_config = _CAMEL

    group_tag: str | None = Field(default=None, max_length=64, alias="groupTag")
    credential_alias: str | None = Field(
        default=None, max_length=64, alias="credentialAlias")


@router.get("", response_model=list[AliasOut])
async def list_aliases(
    user: CurrentUser, db: DbSession,
    base: str | None = Query(default=None),
) -> list[AliasOut]:
    return [AliasOut.model_validate(a) for a in await service_aliases.list_aliases(db, base=base)]


@router.post("", response_model=AliasOut, status_code=201)
async def create_alias(
    user: AdminUser, body: AliasCreate, db: DbSession,
) -> AliasOut:
    try:
        return AliasOut.model_validate(await service_aliases.create_alias(
            db, alias_name=body.alias_name, group_tag=body.group_tag,
            credential_alias=body.credential_alias,
            owner_user_id=body.owner_user_id,
        ))
    except UnknownBaseService as e:
        # 强约束(§4.1 拍板):裸声明不猜;plate 宕机期间不能登记
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e


@router.patch("/{alias_name}", response_model=AliasOut)
async def patch_alias(
    alias_name: str, user: AdminUser, body: AliasPatch, db: DbSession,
) -> AliasOut:
    try:
        explicit_group = ("group_tag" in body.model_fields_set
                          or "groupTag" in body.model_fields_set)
        explicit_cred = ("credential_alias" in body.model_fields_set
                         or "credentialAlias" in body.model_fields_set)
        return AliasOut.model_validate(await service_aliases.patch_alias(
            db, alias_name,
            group_tag=body.group_tag if explicit_group else ...,
            credential_alias=body.credential_alias if explicit_cred else ...,
        ))
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e


@router.delete("/{alias_name}", status_code=204)
async def delete_alias(alias_name: str, user: AdminUser, db: DbSession) -> None:
    await service_aliases.delete_alias(db, alias_name)
