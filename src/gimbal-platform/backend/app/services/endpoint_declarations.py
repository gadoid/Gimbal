"""契约声明面取数(spec v3.1 §3)— dispatch 悬空判定用。

语义:某端点 ``request.declarations`` 的 path 全集(树内全部条目,
模板形态;后端 ``catalog_paths`` 既有实现)。

纪律(与 carry 同款:增强不是前置条件):
* **fail-soft** — 任何故障(plate 不可达 / 非 200 / 信封缺 item / 形状异常)
  返回 ``None``,调用方降级为「只认 body 面」(从严),绝不阻塞执行;
* **不入缓存** — 失败不写缓存,下次调用可重试;
* **进程缓存 + TTL** — 成功入缓存,``DECLARED_PATHS_TTL_SEC`` 到期重取;
* **在飞收敛** — 冷缓存下同一 endpoint 的并发调用复用同一在飞请求,
  不重复打 plate(与前端 ``useEndpointFull`` 的 ``inFlight`` 同款);
* **告警一次** — 同一端点在当前**失败链**内至多一条 warning:失败期间
  只告警第一条,成功一次后重置(后续再失败会重新告警),不刷屏。
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from ..core.config import settings
from .field_state_resolution import catalog_paths
from .plate_client import get_client

_CACHE: dict[str, tuple[float, frozenset[str]]] = {}
_INFLIGHT: dict[str, asyncio.Task[frozenset[str] | None]] = {}
_WARNED: set[str] = set()


def _reset_declared_paths_cache() -> None:
    """测试钩子:清空缓存、在飞表与告警去重集。"""
    _CACHE.clear()
    _INFLIGHT.clear()
    _WARNED.clear()


async def _fetch_declared_paths(endpoint_id: str) -> frozenset[str] | None:
    """真正打一次 plate;fail-soft 绝不抛,成功才入缓存。"""
    now = time.monotonic()
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


async def declared_paths_of(endpoint_id: str) -> frozenset[str] | None:
    """端点声明的 request body path 全集;取不到 → None(调用方从严降级)。"""
    now = time.monotonic()
    hit = _CACHE.get(endpoint_id)
    if hit is not None and now - hit[0] < settings.DECLARED_PATHS_TTL_SEC:
        return hit[1]
    inflight = _INFLIGHT.get(endpoint_id)
    if inflight is not None:
        return await inflight          # 冷缓存并发收敛:复用同一在飞请求
    task = asyncio.ensure_future(_fetch_declared_paths(endpoint_id))
    _INFLIGHT[endpoint_id] = task
    try:
        return await task
    finally:
        # 成功与失败都要移除 —— 否则一次失败会永久卡死该端点的后续调用。
        _INFLIGHT.pop(endpoint_id, None)
