"""契约声明面取数(spec v3.1 §3)— dispatch 悬空判定用。

语义:某端点 ``request.declarations`` 的 path 全集(树内全部条目,
模板形态;后端 ``catalog_paths`` 既有实现)。

纪律(与 carry 同款:增强不是前置条件):
* **fail-soft** — 任何故障(plate 不可达 / 非 200 / 信封缺 item / 形状异常)
  返回 ``None``,调用方降级为「只认 body 面」(从严),绝不阻塞执行;
* **不入缓存** — 失败不写缓存,下次调用可重试;
* **进程缓存 + TTL** — 成功入缓存,``DECLARED_PATHS_TTL_SEC`` 到期重取;
* **告警一次** — 同一端点在当前缓存窗口内至多一条 warning,不刷屏。
"""
from __future__ import annotations

import time
from typing import Any

from loguru import logger

from ..core.config import settings
from .field_state_resolution import catalog_paths
from .plate_client import get_client

_CACHE: dict[str, tuple[float, frozenset[str]]] = {}
_WARNED: set[str] = set()


def _reset_declared_paths_cache() -> None:
    """测试钩子:清空缓存与告警去重集。"""
    _CACHE.clear()
    _WARNED.clear()


async def declared_paths_of(endpoint_id: str) -> frozenset[str] | None:
    """端点声明的 request body path 全集;取不到 → None(调用方从严降级)。"""
    now = time.monotonic()
    hit = _CACHE.get(endpoint_id)
    if hit is not None and now - hit[0] < settings.DECLARED_PATHS_TTL_SEC:
        return hit[1]
    try:
        resp = await get_client().get(f"/api/endpoint/{endpoint_id}/full")
        if resp.status_code != 200:
            raise RuntimeError(f"plate status {resp.status_code}")
        item: Any = (resp.json().get("data") or {}).get("item")
        if not isinstance(item, dict):
            raise RuntimeError("no item in plate envelope")
        paths = frozenset(catalog_paths((item.get("request") or {}).get("declarations")))
    except Exception as e:  # noqa: BLE001 — 声明面不可得绝不阻塞判定
        if endpoint_id not in _WARNED:
            _WARNED.add(endpoint_id)
            logger.warning(
                "endpoint_declarations: {} 声明面不可得({}) — 悬空判定降级为 body 面",
                endpoint_id, e,
            )
        _CACHE.pop(endpoint_id, None)
        return None
    _CACHE[endpoint_id] = (now, paths)
    _WARNED.discard(endpoint_id)
    return paths
