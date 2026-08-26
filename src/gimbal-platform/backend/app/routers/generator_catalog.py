"""Generator catalog proxy — Platform → Plate (generators 语法 dim, 2026-08-26).

常量池管理页需要 plate 内省出的生成器 kind 描述符(哪些 kind、每个
kind 哪些参数)。权威源在 plate(``GET /api/generators`` 与
``GET /api/generators/{kind}/full``,见 gimbal_plate/http/generator_dim.py);
本模块代理这两条,让前端只打 Platform 一个 API 面。

与 strategy_catalog.py 同构(502 plate_unavailable / 404 / 信封透传),
差异: plate 路径、404 code(generator_kind_not_found)、
list 路由解 ``data.items`` 返回数组、full 解 ``data.item``。
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, status

from ..core.deps import CurrentUser
from ..services.plate_client import get_client

router = APIRouter(prefix="/generator-catalog", tags=["generator-catalog"])


def proxy_error(
    resp: httpx.Response,
    *,
    context: str,
    not_found_code: str = "generator_kind_not_found",
    not_found_msg: str = "generator kind not found",
) -> HTTPException:
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
                "code": not_found_code,
                "message": f"{not_found_msg}: {context}",
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


def unavailable(e: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"code": "plate_unavailable", "message": str(e)},
    )


@router.get("")
async def list_generator_kinds(user: CurrentUser) -> list[dict]:
    """Proxy ``GET {plate}/api/generators`` and unwrap ``data.items``."""
    client = get_client()
    try:
        resp = await client.get("/api/generators")
    except httpx.HTTPError as e:
        raise unavailable(e) from e
    if resp.status_code != 200:
        raise proxy_error(resp, context="list")
    items = (resp.json().get("data") or {}).get("items")
    if not isinstance(items, list):
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope", "message": "no items in response"},
        )
    return items


@router.get("/{kind}/full")
async def get_generator_kind_full(user: CurrentUser, kind: str) -> dict:
    """Proxy ``GET {plate}/api/generators/{kind}/full`` and unwrap ``data.item``."""
    client = get_client()
    try:
        resp = await client.get(f"/api/generators/{kind}/full")
    except httpx.HTTPError as e:
        raise unavailable(e) from e
    if resp.status_code != 200:
        raise proxy_error(resp, context=kind)
    item = (resp.json().get("data") or {}).get("item")
    if not item:
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope", "message": "no item in response"},
        )
    return item
