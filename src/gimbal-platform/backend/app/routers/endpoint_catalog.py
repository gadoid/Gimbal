"""Endpoint catalog proxy — Platform → Plate.

The V3 composer front-end needs the full ``IOFieldBinding`` shape for
each endpoint so it can render the request body form correctly.  The
canonical view lives on Plate (``GET /api/endpoint/{id}/full``); this
module proxies the call so the front-end can hit a single API surface
(Platform) and not have to know the Plate URL.
"""
from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from ..core.config import settings
from ..core.deps import CurrentUser


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
    url = f"{settings.PLATE_BASE_URL}/api/endpoint/{endpoint_id}/full"
    try:
        async with httpx.AsyncClient(timeout=settings.PLATE_TIMEOUT_SEC) as client:
            resp = await client.get(url)
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "plate_unavailable", "message": str(e)},
        ) from e

    if resp.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "plate_unavailable", "message": resp.text[:200]},
        )
    if resp.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail={"code": "endpoint_not_found", "message": f"endpoint not found: {endpoint_id}"},
        )
    if resp.status_code >= 400:
        # Surface the envelope message verbatim.
        try:
            env = resp.json()
        except Exception:  # noqa: BLE001
            env = {"ok": False, "error": {"message": resp.text[:200]}}
        raise HTTPException(
            status_code=resp.status_code,
            detail=env.get("error") or {"code": "plate_error", "message": resp.text[:200]},
        )

    envelope = resp.json()
    item = (envelope.get("data") or {}).get("item")
    if not item:
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope", "message": "no item in response"},
        )
    return item
