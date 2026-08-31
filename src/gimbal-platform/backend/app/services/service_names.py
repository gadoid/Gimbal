"""服务名别名推导(spec §4.2)—— 前端 service-alias.ts deriveBase 的后端移植。

别名 = <目录服务名>-<后缀>;切分点固定在最后一个 "-",base 必须落在目录
集合内才生效(裸声明不猜)。目录集合来自 plate services 列表;plate 不可达
→ 空集 → 全部裸声明(该 step 跳过填充 + 黄警,不阻塞执行)。
"""
from __future__ import annotations

import httpx

from .plate_client import PlateUnavailableError, get_client


def derive_base(key: str, catalog_names: set[str]) -> str | None:
    if not key:
        return None
    if key in catalog_names:
        return key
    i = key.rfind("-")
    if i <= 0:
        return None
    base = key[:i]
    return base if base in catalog_names else None


async def catalog_service_names() -> set[str]:
    """GET /api/service → data.items[].name;失败 → 空集(降级)。"""
    client = get_client()
    try:
        resp = await client.get("/api/service")
    except httpx.HTTPError:
        return set()
    if resp.status_code != 200:
        return set()
    items = (resp.json().get("data") or {}).get("items")
    if not isinstance(items, list):
        return set()
    return {str(it.get("name")) for it in items
            if isinstance(it, dict) and it.get("name")}
