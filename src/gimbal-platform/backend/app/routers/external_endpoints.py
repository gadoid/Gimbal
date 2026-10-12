"""外部接口登记路由(外部接口登记批 X1,设计 v1.0 §4.1)。

读写口径同 service_aliases:读全员(编排器下拉/服务信息页数据源)、
写 admin(登记影响所有锚定该接口的场景的表单与校验提示)。
OpenAPI 导入默认演练,``?apply=true`` 落库(单事务)。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser, CurrentUser
from ..services import external_endpoints as svc

router = APIRouter(prefix="/external-endpoints", tags=["external-endpoints"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
_CAMEL = ConfigDict(populate_by_name=True)


class EndpointCreateIn(BaseModel):
    """登记入参(wire camelCase)。"""

    model_config = _CAMEL
    aliasName: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    title: str = ""
    method: str = "GET"
    path: str = "/"
    requestSchema: dict[str, Any] | None = None
    auth: str = "none"
    notes: str | None = None


class EndpointPatchIn(BaseModel):
    """更新入参(name 是锚点段不可改;全部字段可选,缺省不改)。"""

    model_config = _CAMEL
    title: str | None = None
    method: str | None = None
    path: str | None = None
    requestSchema: dict[str, Any] | None = None
    auth: str | None = None
    notes: str | None = None


class ImportIn(BaseModel):
    aliasName: str = Field(min_length=1, max_length=128)
    document: dict[str, Any]           # OpenAPI 文档对象(JSON 形态)


def _err(e: ValueError) -> HTTPException:
    msg = str(e)
    if msg.startswith(("alias_not_found", "not_found")):
        return HTTPException(status.HTTP_404_NOT_FOUND, msg)
    if msg.startswith(("name_conflict", "alias_not_external")):
        return HTTPException(status.HTTP_409_CONFLICT, msg)
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, msg)


@router.get("")
async def list_endpoints(
    user: CurrentUser, db: DbSession,
    alias: str | None = Query(default=None, max_length=128),
    q: str | None = Query(default=None, max_length=64),
) -> dict:
    return {"items": await svc.list_endpoints(db, alias=alias, q=q)}


@router.get("/{alias_name}/{name}")
async def get_endpoint(
    user: CurrentUser, db: DbSession,
    alias_name: str, name: str,
) -> dict:
    out = await svc.get_endpoint(db, alias_name, name)
    if out is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"not_found: {alias_name}.{name}")
    return out


@router.post("", status_code=201)
async def create_endpoint(
    admin: AdminUser, db: DbSession, body: EndpointCreateIn,
) -> dict:
    try:
        return await svc.create_endpoint(
            db, alias_name=body.aliasName, name=body.name,
            title=body.title, method=body.method, path=body.path,
            request_schema=body.requestSchema, auth=body.auth,
            notes=body.notes)
    except ValueError as e:
        raise _err(e) from e


@router.patch("/{alias_name}/{name}")
async def update_endpoint(
    admin: AdminUser, db: DbSession,
    alias_name: str, name: str, body: EndpointPatchIn,
) -> dict:
    try:
        return await svc.update_endpoint(
            db, alias_name=alias_name, name=name,
            title=body.title, method=body.method, path=body.path,
            request_schema=body.requestSchema, auth=body.auth,
            notes=body.notes)
    except ValueError as e:
        raise _err(e) from e


@router.delete("/{alias_name}/{name}", status_code=204)
async def delete_endpoint(
    admin: AdminUser, db: DbSession, alias_name: str, name: str,
) -> None:
    try:
        await svc.delete_endpoint(db, alias_name=alias_name, name=name)
    except ValueError as e:
        raise _err(e) from e


@router.post("/import-openapi")
async def import_openapi(
    admin: AdminUser, db: DbSession, body: ImportIn,
    apply: bool = Query(default=False),
) -> dict:
    """OpenAPI 导入:默认演练(报告不落库);``?apply=true`` 单事务落库。

    同名条目跳过并报告(幂等复跑);文档 ``servers[0].url`` 在别名
    base_url 为空时补默认层。
    """
    try:
        return await svc.import_openapi(
            db, alias_name=body.aliasName, doc=body.document, apply=apply)
    except ValueError as e:
        raise _err(e) from e
