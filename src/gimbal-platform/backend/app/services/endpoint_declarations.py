"""契约声明面取数(spec v3.1 §3)— dispatch 悬空判定 + carry 面共用。

语义:某端点 ``GET /api/endpoint/{id}/full`` → ``data.item.request.declarations``
的**原始声明列表**(目录态;进程内唯一取数路径)。两个公开访问器都从
这一份缓存派生:

* ``declarations_of`` — 原始列表(carry 面投影 ``carry_face`` 的输入);
* ``declared_paths_of`` — path 全集(模板形态;悬空判定用)。

**合并的理由**:修复前 carry 侧另有一份自带取数(``carry_injection``),
打同一个 URL、解同一个信封、fail-soft 同款,却无缓存 —— 同一份 plate
契约两条获取路径,可各自漂移,且每次 dispatch 都白付一次往返。

纪律(与 carry 同款:增强不是前置条件):
* **fail-soft** — 任何故障(plate 不可达 / 非 200 / 信封缺 dict item /
  ``declarations`` 非 list)返回 ``None``,调用方降级(carry 空面 /
  悬空判定只认 body 面),绝不阻塞执行;
* **不入缓存** — 失败不写缓存,下次调用可重试;
* **进程缓存 + TTL** — 成功入缓存,``DECLARED_PATHS_TTL_SEC`` 到期重取;
* **在飞收敛** — 冷缓存下同一 endpoint 的并发调用复用同一在飞请求,
  不重复打 plate(与前端 ``useEndpointFull`` 的 ``inFlight`` 同款);
* **告警一次** — 同一端点在当前**失败链**内至多一条 warning:失败期间
  只告警第一条,成功一次后重置(后续再失败会重新告警),不刷屏;
* **空目录 ≠ 降级** — 合法空目录 ``[]`` 是成功结果(carry 侧为空面、
  ``declared_paths_of`` 为空 frozenset),``None`` 才是降级信号,二者
  类型上分开,留降级遥测的口子。
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from ..core.config import settings
from .field_state_resolution import catalog_paths
from .plate_client import get_client

_CACHE: dict[str, tuple[float, list]] = {}
_INFLIGHT: dict[str, asyncio.Task[list | None]] = {}
_WARNED: set[str] = set()


def _reset_declared_paths_cache() -> None:
    """测试钩子:清空缓存、在飞表与告警去重集。"""
    _CACHE.clear()
    _INFLIGHT.clear()
    _WARNED.clear()


async def _fetch_declarations(endpoint_id: str) -> list | None:
    """真正打一次 plate;fail-soft 绝不抛,成功才入缓存。"""
    now = time.monotonic()
    try:
        resp = await get_client().get(f"/api/endpoint/{endpoint_id}/full")
        if resp.status_code != 200:
            raise RuntimeError(f"plate status {resp.status_code}")
        item: Any = (resp.json().get("data") or {}).get("item")
        if not isinstance(item, dict):
            raise RuntimeError("no item in plate envelope")
        decls = (item.get("request") or {}).get("declarations")
        if not isinstance(decls, list):
            raise RuntimeError("declarations is not a list")
    except Exception as e:  # noqa: BLE001 — 声明面不可得绝不阻塞判定
        if endpoint_id not in _WARNED:
            _WARNED.add(endpoint_id)
            logger.warning(
                "endpoint_declarations: {} 声明面不可得({}) — 调用侧降级"
                "(carry 空面 / 悬空判定只认 body 面)",
                endpoint_id, e,
            )
        _CACHE.pop(endpoint_id, None)
        return None
    _CACHE[endpoint_id] = (now, decls)
    _WARNED.discard(endpoint_id)
    return decls


async def declarations_of(endpoint_id: str) -> list | None:
    """端点 ``request.declarations`` 原始列表;取不到 → None(调用侧降级)。

    进程缓存 + TTL + 在飞收敛:与 ``declared_paths_of`` 共用同一次取数、
    同一份缓存,不会各拉一次 plate。
    """
    now = time.monotonic()
    hit = _CACHE.get(endpoint_id)
    if hit is not None and now - hit[0] < settings.DECLARED_PATHS_TTL_SEC:
        return hit[1]
    inflight = _INFLIGHT.get(endpoint_id)
    if inflight is not None:
        return await inflight          # 冷缓存并发收敛:复用同一在飞请求
    task = asyncio.ensure_future(_fetch_declarations(endpoint_id))
    _INFLIGHT[endpoint_id] = task
    try:
        return await task
    finally:
        # 成功与失败都要移除 —— 否则一次失败会永久卡死该端点的后续调用。
        _INFLIGHT.pop(endpoint_id, None)


async def declared_paths_of(endpoint_id: str) -> frozenset[str] | None:
    """端点声明的 request body path 全集;取不到 → None(调用方从严降级)。

    合法空目录 ``[]`` → 空 frozenset(**非 None**):那是「真无声明」,
    不是「降级」。
    """
    decls = await declarations_of(endpoint_id)
    if decls is None:
        return None
    return frozenset(catalog_paths(decls))
