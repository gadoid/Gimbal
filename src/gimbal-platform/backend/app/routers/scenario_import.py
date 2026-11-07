"""场景导入流水线端点(W3/W4,场景导入 v2.3 方案 §3)。

* 权限 ``CurrentUser``(authz W7:导入开放至全体用户 —— User 可导入
  并映射到已有别名;``decision=create`` 建新别名另需 ``alias.write``
  能力,services 层 land() 拒 403 capability_forbidden);
* 体积门在 ``scenario_import.read_bundle``(N3:原始 Request +
  Content-Length 预检 + 限长读,json.loads 之前拒绝);
* 注册必须在 scenarios.router 之前(``/scenarios/import`` 先于
  ``/{scenario_id}`` catch-all);旧 definition-only 裸导入端点已随
  本模块退役。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..services import scenario_import

router = APIRouter(prefix="/scenarios/import", tags=["scenarios"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _http(e: scenario_import.ImportRejected) -> HTTPException:
    detail: dict = {"code": e.code, "message": e.message}
    if e.capability:                       # 9.7 能力门契约:附能力名(W7)
        detail["capability"] = e.capability
    return HTTPException(status_code=e.http, detail=detail)


async def _read(request: Request) -> dict:
    try:
        return await scenario_import.read_bundle(request)
    except scenario_import.ImportRejected as e:
        raise _http(e) from e


@router.post("/precheck")
async def import_precheck(
    user: CurrentUser, db: DbSession, request: Request,
) -> dict:
    """纯读预检(方案 §3.1):结论走 200 信封,fatal 作为字段返回。"""
    body = await _read(request)
    try:
        definition = scenario_import.bundle_definition(body)
        return await scenario_import.precheck(
            db, definition=definition, user=user)
    except scenario_import.ImportRejected as e:
        raise _http(e) from e


@router.post("", status_code=201)
async def import_scenario(
    user: CurrentUser, db: DbSession, request: Request,
) -> dict:
    """一次性落库(方案 §3.3):``{bundle, idMode?, newId?, mappings?}``。"""
    body = await _read(request)
    try:
        definition = scenario_import.bundle_definition(body)
        return await scenario_import.land(
            db, definition=definition,
            mappings=body.get("mappings"),
            id_mode=body.get("idMode") or "keep",
            new_id=body.get("newId"),
            user=user)
    except scenario_import.ImportRejected as e:
        raise _http(e) from e
