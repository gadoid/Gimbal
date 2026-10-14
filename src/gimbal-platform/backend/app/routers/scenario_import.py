"""场景导入流水线端点(W3/W4,场景导入 v2.3 方案 §3)。

* 权限 ``MemberUser``(P1:导入含建别名/写 carry,与别名写权限一致;
  旧 R19 端点的 ``CurrentUser`` 随本模块上线收紧);
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
from ..core.deps import MemberUser
from ..services import scenario_import

router = APIRouter(prefix="/scenarios/import", tags=["scenarios"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _http(e: scenario_import.ImportRejected) -> HTTPException:
    return HTTPException(
        status_code=e.http, detail={"code": e.code, "message": e.message})


async def _read(request: Request) -> dict:
    try:
        return await scenario_import.read_bundle(request)
    except scenario_import.ImportRejected as e:
        raise _http(e) from e


@router.post("/precheck")
async def import_precheck(
    user: MemberUser, db: DbSession, request: Request,
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
    user: MemberUser, db: DbSession, request: Request,
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
