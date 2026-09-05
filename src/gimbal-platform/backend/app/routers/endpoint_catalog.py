"""Endpoint catalog proxy — Platform → Plate.

The V3 composer front-end needs the full ``declarations`` shape for
each endpoint so it can render the request body form correctly.  The
canonical view lives on Plate (``GET /api/endpoint/{id}/full``); this
module proxies the call so the front-end can hit a single API surface
(Platform) and not have to know the Plate URL.

与 strategy_catalog.py 共用错误映射 helper 与 plate_client 的进程级
AsyncClient 单例(共享连接池,MockTransport 测试替换随之生效)。
"""
from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.deps import CurrentUser
from ..services.field_state_resolution import validate_field_states
from ..services.plate_client import get_client
from .strategy_catalog import proxy_error, unavailable

router = APIRouter(prefix="/endpoint-catalog", tags=["endpoint-catalog"])


class ResolvePathsRequest(BaseModel):
    """B1 路径推断入参 — 透传 plate resolve-paths action 的 body。"""

    response_body_sample: Any
    path_prefix: Optional[str] = None


class FieldStatesValidateRequest(BaseModel):
    """§3.5 配置编辑校验入参:step 的 field_states 增量(可空)。"""

    field_states: dict[str, str] = Field(default_factory=dict)


@router.get("/{endpoint_id:path}/full")
async def get_full_endpoint(
    user: CurrentUser,
    endpoint_id: str,
) -> dict:
    """Proxy ``GET {plate}/api/endpoint/{id}/full`` and unwrap the envelope.

    Returns the ``item`` payload (with full ``request.declarations``
    carrying ``DeclarationEntry`` shape; response assertion candidates
    are the ``assertable=True`` entries — 响应面单脸,state 不被读取,
    2026-09-05 目录化). Surfaces Plate's status code + error envelope
    to the client.
    """
    client = get_client()
    try:
        resp = await client.get(f"/api/endpoint/{endpoint_id}/full")
    except httpx.HTTPError as e:
        raise unavailable(e) from e
    if resp.status_code != 200:
        raise proxy_error(
            resp,
            context=endpoint_id,
            not_found_code="endpoint_not_found",
            not_found_msg="endpoint not found",
        )

    envelope = resp.json()
    item = (envelope.get("data") or {}).get("item")
    if not item:
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope", "message": "no item in response"},
        )
    return item


@router.post("/resolve-paths")
async def resolve_paths(user: CurrentUser, body: ResolvePathsRequest) -> list[dict]:
    """Proxy ``POST {plate}/api/endpoint/action/resolve-paths``.

    B1 路径推断: 响应样本 → 候选 JSONPath(数组展开下标),供编排页
    策略路径字段(assertion.target / extract.expression)点选 — 替代
    断言面缺失时的静默猜测。action 名是连字符(fin 系统
    endpoint dim 注册名)。解 ``data.paths`` 返回数组(前端下拉直接用)。
    """
    client = get_client()
    try:
        resp = await client.post(
            "/api/endpoint/action/resolve-paths",
            json={
                "response_body_sample": body.response_body_sample,
                "path_prefix": body.path_prefix,
            },
        )
    except httpx.HTTPError as e:
        raise unavailable(e) from e
    if resp.status_code != 200:
        raise proxy_error(resp, context="resolve-paths")

    paths = (resp.json().get("data") or {}).get("paths")
    if not isinstance(paths, list):
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope", "message": "no paths in response"},
        )
    return paths


@router.post("/{endpoint_id:path}/field-states/validate")
async def validate_step_field_states(
    user: CurrentUser,
    endpoint_id: str,
    body: FieldStatesValidateRequest,
) -> dict:
    """§3.5 配置编辑校验:plate 目录 + step.field_states 增量 → 合成态裁决。

    编辑器在改字段状态时调用:``errors`` 非空 = 拒(树一致性),
    ``warnings`` 仅提示(required 落 carry / DESCRIPTIVE 进 form /
    目录外 stale path)。校验跑在合成态上 —— 目录本身一致但增量
    破坏整传一致性同样拒。目录拉取复用 /full 代理语义(错误映射
    同款:plate 不可达 502 / 404 endpoint_not_found)。
    """
    client = get_client()
    try:
        resp = await client.get(f"/api/endpoint/{endpoint_id}/full")
    except httpx.HTTPError as e:
        raise unavailable(e) from e
    if resp.status_code != 200:
        raise proxy_error(
            resp,
            context=endpoint_id,
            not_found_code="endpoint_not_found",
            not_found_msg="endpoint not found",
        )
    item = (resp.json().get("data") or {}).get("item")
    if not isinstance(item, dict):
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope",
                    "message": "no item in response"},
        )
    decls = ((item.get("request") or {}).get("declarations")) or []
    return validate_field_states(decls, body.field_states)
