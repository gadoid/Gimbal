"""Auth-session connectivity probe (自 auth_sessions 路由收敛)。

POST {url} with {username, password} and report reachability + a
best-effort token extraction.  Spec-2 keeps the parser simple:
``access_token``, ``token``, or ``data.token`` in the JSON body.
"""
from __future__ import annotations

import httpx

_TIMEOUT_SEC = 10.0


async def probe(url: str, username: str, password: str) -> tuple[bool, int | None, str]:
    """Dial the auth endpoint → ``(ok, status_code, message)``."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SEC) as client:
            resp = await client.post(
                url,
                json={"username": username, "password": password},
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as e:
        return False, None, f"网络错误: {e}"

    if resp.status_code >= 400:
        return False, resp.status_code, f"目标返回 {resp.status_code}"

    try:
        body = resp.json()
    except Exception:  # noqa: BLE001  non-JSON but reachable is still ok
        return True, resp.status_code, "连通成功（响应非 JSON，未提取 token）"

    token = (
        body.get("access_token")
        or body.get("token")
        or (body.get("data") or {}).get("token")
    )
    if token:
        return (
            True,
            resp.status_code,
            f"连通成功，已提取 token（前 12 字符：{str(token)[:12]}…）",
        )
    return True, resp.status_code, "连通成功（响应 JSON 中未发现 token 字段）"
