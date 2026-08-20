"""Endpoint catalog proxy — Platform → Plate.

The V3 composer front-end needs the full ``IOFieldBinding`` shape for
each endpoint so it can render the request body form correctly.  The
canonical view lives on Plate (``GET /api/endpoint/{id}/full``); this
module proxies the call so the front-end can hit a single API surface
(Platform) and not have to know the Plate URL.

与 strategy_catalog.py 共用错误映射 helper 与 plate_client 的进程级
AsyncClient 单例(共享连接池,MockTransport 测试替换随之生效)。
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from ..core.deps import CurrentUser
from ..services.plate_client import get_client
from .strategy_catalog import proxy_error, unavailable

router = APIRouter(prefix="/endpoint-catalog", tags=["endpoint-catalog"])


@router.get("/{endpoint_id:path}/full")
async def get_full_endpoint(
    user: CurrentUser,
    endpoint_id: str,
) -> dict:
    """Proxy ``GET {plate}/api/endpoint/{id}/full`` and unwrap the envelope.

    Returns the ``item`` payload (with full ``request.fields`` carrying
    ``IOFieldBinding`` shape and the 200-response ``assertable_fields``).
    Surfaces Plate's status code + error envelope to the client.
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
