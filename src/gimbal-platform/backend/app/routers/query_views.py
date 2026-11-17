"""query-views rows 路由 —— 组合期取数解释器入口(2026-09-07 spec §4.1)。

CurrentUser 鉴权(查询身份是场景执行账号,不是平台用户自己);
service_url/query_alias 由前端按 authored config.services /
config.users 首键(2026-09-09 裁定:查询身份 = 执行身份)求值后传入
(组合上下文在调用方;后端无集中 resolver,与 _apply_services 同语义)。
"""
from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthSession
from app.core.db import get_db
from app.core.deps import CurrentUser
from app.services import query_view_runner
from app.services.run_prepare import _materialize_identities, _resolve_identities

router = APIRouter(prefix="/query-views", tags=["query-views"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _loader(db: DbSession):
    """凭证装载闭包:runner 在凭证闸内按需调用(黑名单键在它之前
    已降级 —— 绝不急切装载,保持"401 拉黑不打 DB"语义)。

    重构 + §8.3:``alias`` = 身份条目名 → 条目 ref → 账户(取用不
    校验标签 —— 同标签优先 → system 唯一;解不到 = None,与旧缺行
    同语义)。"""
    async def load(owner_id: int, alias: str) -> AuthSession | None:
        picked, _miss, _amb = await _resolve_identities(db, owner_id, [alias])
        if not picked:
            return None
        resolved = await _materialize_identities(db, picked)
        r = resolved.get(alias)
        if r is None:
            return None
        return AuthSession(
            url=r.url,
            username=r.username,
            password=r.password,
        )
    return load


@router.get("")
async def list_views(user: CurrentUser) -> dict:
    """索引代理(§13.3):前端参数段消费 query_params;复用 runner 的
    plate memo + 熔断,零新增状态。"""
    items = await query_view_runner.fetch_query_view_index()
    return {"items": items}


@router.get("/{name}/rows")
async def get_rows(
    name: str,
    user: CurrentUser,
    db: DbSession,
    refresh: bool = False,
    service_url: str = "",
    query_alias: str | None = None,
    service: str | None = None,
    params: str = "",
) -> dict:
    click: dict[str, Any] | None = None
    if params:
        try:
            parsed = json.loads(params)
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail={"code": "bad_params", "msg": "params 非合法 JSON"}) from e
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=422,
                detail={"code": "bad_params", "msg": "params 须为 JSON 对象"})
        # §13.7 手工逃生口:参数值须为标量 —— dict/list/null 会污染下游序列化
        # (httpx 在 GET 上会把非标量 repr 字符串化)。
        if any(not isinstance(v, (str, int, float, bool))
               for v in parsed.values()):
            raise HTTPException(
                status_code=422,
                detail={"code": "bad_params",
                        "msg": "params 值须为标量(str/int/float/bool)"})
        click = {str(k): v for k, v in parsed.items()}
    try:
        r = await query_view_runner.fetch_rows(
            name, refresh=refresh, service_url=service_url,
            owner_id=user.id, query_alias=query_alias, service=service,
            load_credential=_loader(db), click_params=click)
    except query_view_runner.QueryViewError as e:
        raise HTTPException(status_code=e.status,
                            detail={"code": e.code, "msg": e.message}) from e
    return {"view": r.view, "rows": r.rows, "truncated": r.truncated,
            "fetched_at": r.fetched_at, "cached": r.cached, "stale": r.stale}
