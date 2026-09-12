"""契约声明面取数(spec v3.1 §3)— carry 面 + dispatch 悬空判定共用。

语义:某端点 ``GET /api/endpoint/{id}/full`` → ``data.item.request.declarations``
的**原始声明列表**(目录态)。本模块服务**两个**消费者,共用同一次取数:

* ``declarations_of`` — 原始列表(``carry_injection.build_carry_context``
  的面投影输入);
* ``declared_paths_of`` — path 全集(模板形态;dispatch 悬空判定,T4)。

**合并的理由**:修复前 carry 侧另有一份自带取数(``carry_injection``),
打同一个 URL、解同一个信封、fail-soft 同款,却无缓存 —— 同一份 plate
契约两条获取路径,可各自漂移,且每次 dispatch 都白付一次往返。

**本模块不是唯一的 ``/full`` 取数路径**(勿读作「唯一」):
``adaptation_service._plate_full_endpoint`` 也打同一个端点,其结果被
``routers/carry.py`` / ``carry_store.py`` 当 declarations 读;
``routers/endpoint_catalog.py`` 亦有自己的取数(composer 代理等)。
这几条各自独立、**不共享**本缓存 —— 本模块只收敛上面那两个消费者。

纪律(与 carry 同款:增强不是前置条件):
* **fail-soft** — 任何故障(plate 不可达 / 非 200 / 信封缺 dict item /
  ``declarations`` 为垃圾值)返回 ``None``,调用方降级(carry 空面 /
  悬空判定只认 body 面),绝不阻塞执行;
* **不入缓存** — 失败不写缓存,下次调用可重试;
* **进程缓存 + TTL** — 成功入缓存,``DECLARED_PATHS_TTL_SEC`` 到期重取;
* **在飞收敛 + 取消隔离** — 冷缓存下同一 endpoint 的并发调用复用同一
  在飞请求;各调用方一律 ``await asyncio.shield(...)``,故任何一个调用方
  被取消都**不会**连带取消共享取数。
  **为什么这不是可选优化**(动手"简化"之前请读完):等待方的取消若传导到
  共享任务,创建者也会拿到 ``CancelledError``;而 dispatcher 侧
  ``run_dispatcher`` 的 ``except Exception`` **不捕** ``CancelledError``
  (它派生自 ``BaseException``),于是 fan-out 被判取消、**不写终止 JSONL
  行**,执行卡在 ``running`` 直到下次进程重启(``reconcile_stale_executions``
  只在启动跑)。故两条**不得**:**不得**把 shield 简化成裸 ``await task``;
  **不得**把在飞项摘除改回创建者的 ``finally``(创建者一被取消就提前摘除,
  而任务仍在飞 → 后续调用重复取数);
* **告警一次** — 同一端点在当前**失败链**内至多一条 warning:失败期间
  只告警第一条,成功一次后重置(后续再失败会重新告警),不刷屏;
* **空目录 ≠ 降级** — 真无声明(``[]`` / 封套缺 ``request.declarations``
  / 其为 ``null``)是**成功结果**:carry 侧空面、``declared_paths_of``
  空 frozenset。只有**拿不到**声明面才 ``None``。
"""
from __future__ import annotations

import asyncio
import time
from functools import partial
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


def _forget_inflight(task: asyncio.Task[list | None], endpoint_id: str) -> None:
    """任务完成回调:摘除**自己那个**在飞项。

    由完成回调驱动,而不是某个调用方的 ``finally`` —— 创建者可能被取消、
    等待方也可能先于任务完成退出,只有「任务真的完成了」才是摘除的
    正确时机(否则一次失败/取消会永久锈住该端点)。校验身份:迟到的
    回调不得误删后来者(同 endpoint 的新一轮在飞)。
    """
    if _INFLIGHT.get(endpoint_id) is task:
        _INFLIGHT.pop(endpoint_id, None)


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
        if decls is None:
            decls = []      # 封套合法但无声明 = 真无声明,不是降级
        elif not isinstance(decls, list):
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

    区分(承载「真无声明 vs 降级」):
    * 合法空声明(``[]`` / 缺键 / ``null``)→ ``[]``(**不是** None);
    * 垃圾值(字符串/字典等非 list)→ ``None``;
    * 非 200 / 抛异常 / 信封无 dict item → ``None``。

    返回**浅拷贝**:缓存是进程级共享状态,调用方改自己那份不会污染
    其他消费者(容器内的条目 dict 仍共享 —— 只读契约)。
    """
    now = time.monotonic()
    hit = _CACHE.get(endpoint_id)
    if hit is not None and now - hit[0] < settings.DECLARED_PATHS_TTL_SEC:
        return list(hit[1])
    inflight = _INFLIGHT.get(endpoint_id)
    if inflight is None:
        inflight = asyncio.ensure_future(_fetch_declarations(endpoint_id))
        _INFLIGHT[endpoint_id] = inflight
        inflight.add_done_callback(
            partial(_forget_inflight, endpoint_id=endpoint_id)
        )
    # shield:本调用方被取消只落自己,不连带取消共享取数 —— 裸 await 会把取消
    # 扩散进共享任务(创建者随之收到 CancelledError);dispatcher 的
    # except Exception 不捕 CancelledError → fan-out 被判取消、不写终止 JSONL
    # 行、执行卡在 running。务必保留 shield,摘除务必留在完成回调(见模块 docstring)。
    decls = await asyncio.shield(inflight)
    return list(decls) if decls is not None else None


async def declared_paths_of(endpoint_id: str) -> frozenset[str] | None:
    """端点声明的 request body path 全集;取不到 → None(调用方从严降级)。

    合法空声明 → 空 frozenset(**非 None**):那是「真无声明」,不是「降级」。
    """
    decls = await declarations_of(endpoint_id)
    if decls is None:
        return None
    return frozenset(catalog_paths(decls))
