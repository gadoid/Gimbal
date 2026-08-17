"""Strategy catalog proxy — Platform → Plate (strategy 语法 dim, 2026-08-17).

前端"添加策略"需要 plate 内省出的 kind 描述符(哪些 kind、每个 kind
哪些字段)。权威源在 plate(``GET /api/strategy`` 与
``GET /api/strategy/{kind}/full``);本模块代理这两条,让前端只打
Platform 一个 API 面。

与 endpoint_catalog.py 同构(502 plate_unavailable / 404 / 信封透传),
差异:
* list 路由解 ``data.items`` 返回数组(前端下拉直接用);
* 复用 ``app.services.plate_client`` 的进程级 AsyncClient 单例
  (endpoint_catalog 自建 client 是历史形态,这里走共享连接池,
  MockTransport 测试替换也随之生效)。
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from ..core.deps import CurrentUser
from ..services.plate_client import _get_client

router = APIRouter(prefix="/strategy-catalog", tags=["strategy-catalog"])


def _proxy_error(resp: httpx.Response, *, context: str) -> HTTPException:
    """Map a plate non-2xx response onto the platform error model."""
    if resp.status_code >= 500:
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "plate_unavailable", "message": resp.text[:200]},
        )
    if resp.status_code == 404:
        return HTTPException(
            status_code=404,
            detail={
                "code": "strategy_kind_not_found",
                "message": f"strategy kind not found: {context}",
            },
        )
    try:
        env = resp.json()
    except Exception:  # noqa: BLE001
        env = {"ok": False, "error": {"message": resp.text[:200]}}
    return HTTPException(
        status_code=resp.status_code,
        detail=env.get("error") or {"code": "plate_error", "message": resp.text[:200]},
    )


def _unavailable(e: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"code": "plate_unavailable", "message": str(e)},
    )


@router.get("")
async def list_strategy_kinds(user: CurrentUser) -> list[dict]:
    """Proxy ``GET {plate}/api/strategy`` and unwrap ``data.items``."""
    client = _get_client()
    try:
        resp = await client.get("/api/strategy")
    except httpx.HTTPError as e:
        raise _unavailable(e) from e
    if resp.status_code != 200:
        raise _proxy_error(resp, context="list")
    items = (resp.json().get("data") or {}).get("items")
    if not isinstance(items, list):
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope", "message": "no items in response"},
        )
    return items


@router.get("/{kind}/full")
async def get_strategy_kind_full(user: CurrentUser, kind: str) -> dict:
    """Proxy ``GET {plate}/api/strategy/{kind}/full`` and unwrap ``data.item``."""
    client = _get_client()
    try:
        resp = await client.get(f"/api/strategy/{kind}/full")
    except httpx.HTTPError as e:
        raise _unavailable(e) from e
    if resp.status_code != 200:
        raise _proxy_error(resp, context=kind)
    item = (resp.json().get("data") or {}).get("item")
    if not item:
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope", "message": "no item in response"},
        )
    return item
