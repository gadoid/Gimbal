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
* **失败不写缓存 + 旧快照回退**(2026-09-13 架构收敛 §3.1,D)—— 失败不写
  缓存,下次调用可重试;TTL 过期后**刷新失败时旧快照继续服务**,直到回退窗
  ``DECLARED_PATHS_STALE_WINDOW_SEC`` 走完才真过期。旧实现是「刷新失败
  ``_CACHE.pop``」⇒ 一次 plate 抖动就把声明面从「有面」降级成「空面」;
* **LRU 容量上界**(S)—— ``DECLARED_PATHS_MAX_ENTRIES`` 逐出最旧。旧实现是
  自持 dict,「永不淘汰」;
* **时间戳取在成功之后**(U)—— 入缓存统一由 ``_refresh`` 在**成功那刻**做,
  由 ``TtlLruCache.put`` 自己打点。旧实现把 ``time.monotonic()`` 取在**请求
  发起时** ⇒ 慢 plate(取数耗时 > TTL)上条目一入缓存即已过期,缓存退化;
* **投影随取数缓存**(R)—— 条目载荷 = ``(decls, frozenset(catalog_paths(decls)))``,
  TTL 命中路径直接取投影,不再遍历声明树(``declared_paths_of`` 每次
  dispatch 都会被问);
* **告警按时间窗老化**(S)—— 同一端点在 ``_WARN_COOLDOWN_SEC`` 内至多一条
  warning。旧 ``_WARNED`` 集合只在「同 id 后来成功」时清 ⇒ 长期失败的端点
  在恢复前彻底失声(而它的告警正是降级的唯一遥测);
* **缓存实例随 settings 惰性重建** —— ``TtlLruCache`` 的 ttl/容量/回退窗
  **构造即冻结**,而这三个值来自 settings(测试 monkeypatch、运维热改都要求
  即刻生效)⇒ ``_cache()`` 比对当前 cfg 与建例时的 cfg,不一致就换实例
  (生产 cfg 恒定 ⇒ 等价于模块级单例);
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
* **返回浅拷贝** — 缓存是进程级共享面,两条返回路径(取数/命中)都给拷贝,
  调用方改自己那份不污染他人;
* **空目录 ≠ 降级** — 真无声明(``[]`` / 封套缺 ``request.declarations``
  / 其为 ``null``)是**成功结果**:carry 侧空面、``declared_paths_of``
  空 frozenset。只有**拿不到**声明面才 ``None``。
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from functools import partial
from typing import Any

from loguru import logger

from ..core.config import settings
from .field_state_resolution import catalog_paths
from .plate_client import get_client
from .query_view_cache import TtlLruCache


def _cache_cfg() -> tuple[float, int, float]:
    """本缓存实例的三个构造参数(settings 现值)。"""
    return (settings.DECLARED_PATHS_TTL_SEC,
            settings.DECLARED_PATHS_MAX_ENTRIES,
            settings.DECLARED_PATHS_STALE_WINDOW_SEC)


def _build_cache() -> TtlLruCache:
    return TtlLruCache(ttl=settings.DECLARED_PATHS_TTL_SEC,
                       max_entries=settings.DECLARED_PATHS_MAX_ENTRIES,
                       stale_max_window=settings.DECLARED_PATHS_STALE_WINDOW_SEC)


_CACHE: TtlLruCache = _build_cache()
_CACHE_CFG: tuple[float, int, float] = _cache_cfg()
_INFLIGHT: dict[str, asyncio.Task[list | None]] = {}
_WARNED_AT: dict[str, float] = {}          # eid → 最近一次告警时刻(时间老化,不再只在成功时清)
_WARN_COOLDOWN_SEC = 300.0


def _cache() -> TtlLruCache:
    """当前缓存实例;settings 的三个参数变了就换实例(见模块 docstring)。"""
    global _CACHE, _CACHE_CFG
    cfg = _cache_cfg()
    if cfg != _CACHE_CFG:
        _CACHE = _build_cache()
        _CACHE_CFG = cfg
    return _CACHE


def _reset_declared_paths_cache() -> None:
    """测试钩子:按当前 settings 重建缓存、清在飞表与告警表。

    重建(而非逐键清)是必须的:``TtlLruCache`` 的 ttl/容量/回退窗构造即冻结,
    而调用方(测试)先 monkeypatch settings 再重置 —— 只有换实例才让新值生效。
    """
    global _CACHE, _CACHE_CFG
    _CACHE = _build_cache()
    _CACHE_CFG = _cache_cfg()
    _INFLIGHT.clear()
    _WARNED_AT.clear()


def _now_iso() -> str:
    """缓存条目的墙钟时刻(仅用于可读诊断)。"""
    return datetime.now(timezone.utc).isoformat()


def _warn_once(endpoint_id: str, reason: object) -> None:
    """降级告警(**时间老化**):同一端点在 `_WARN_COOLDOWN_SEC` 内至多一条。

    旧实现只在"同 id 后来成功"时才清 `_WARNED` ⇒ 调用方字符串(错拼/改名)驱动的
    无界增长(spec §1.1 S);改为按时间窗老化,与 `TtlLruCache` 的惰性过期同风格。"""
    now = time.monotonic()
    last = _WARNED_AT.get(endpoint_id)
    if last is not None and now - last < _WARN_COOLDOWN_SEC:
        return
    # 顺手老化解表(同 TtlLruCache.lookup 的惰性过期):只有窗内的条目还需要留档
    # ⇒ 表大小 ~ 冷却窗内失败过的端点数,不再"每端点一条永不回收"。
    for aged in [k for k, t in _WARNED_AT.items() if now - t >= _WARN_COOLDOWN_SEC]:
        _WARNED_AT.pop(aged, None)
    _WARNED_AT[endpoint_id] = now
    logger.warning(
        "endpoint_declarations: {} 声明面不可得({}) — 调用侧降级"
        "(carry 空面 / 悬空判定只认 body 面)",
        endpoint_id, reason,
    )


def _forget_inflight(task: asyncio.Task[list | None], endpoint_id: str) -> None:
    """任务完成回调:摘除**自己那个**在飞项。

    由完成回调驱动,而不是某个调用方的 ``finally`` —— 创建者可能被取消、
    等待方也可能先于任务完成退出,只有「任务真的完成了」才是摘除的
    正确时机(否则一次失败/取消会永久锈住该端点)。校验身份:迟到的
    回调不得误删后来者(同 endpoint 的新一轮在飞)。
    """
    if _INFLIGHT.get(endpoint_id) is task:
        _INFLIGHT.pop(endpoint_id, None)


async def _fetch_declarations(endpoint_id: str, fail_reason: list[str]) -> list | None:
    """真正打一次 plate;**fail-soft 绝不抛,也绝不写缓存**。

    入缓存统一由 ``_refresh`` 在**成功之后**做(U:时间戳由 ``TtlLruCache.put``
    在成功那一刻打点,不是本函数入口)。失败返回 None 且**不动**缓存 ——
    旧快照因此能留到回退窗,由调用侧决定是否回退(D)。

    ``fail_reason[0]`` 回填失败原因(调用方组进告警):告警是降级链路上唯一的
    遥测,「plate status 503 / 信封缺 item / 连接失败」必须透得出来 —— 旧实现
    的 warning 里就带着它。这个 list 由 `_refresh` 随本次取数创建、随任务一起
    回收,不是新的模块级状态。
    """
    try:
        resp = await get_client().get(f"/api/endpoint/{endpoint_id}/full")
        if resp.status_code != 200:
            raise RuntimeError(f"plate status {resp.status_code}")
        # 缺省合并(例外,已核等价性 —— 不是「有意义 falsy 被真值合并」):
        # 信封缺 ``data`` 键 / ``item`` 缺 ``request`` 键 / 其值为 ``{}`` 三种
        # 「未提供」都落到同一缺省 ``{}``,而 ``{}`` 正是缺省值本身;真·垃圾值
        # (字符串/数字等非 dict)仍会在 ``.get`` 上抛错 → 降级 None。
        item: Any = (resp.json().get("data") or {}).get("item")
        if not isinstance(item, dict):
            raise RuntimeError("no item in plate envelope")
        decls = (item.get("request") or {}).get("declarations")
        if decls is None:
            decls = []      # 封套合法但无声明 = 真无声明,不是降级
        elif not isinstance(decls, list):
            raise RuntimeError("declarations is not a list")
        return decls
    except Exception as e:  # noqa: BLE001 — 声明面不可得绝不阻塞判定
        fail_reason[0] = str(e)
        return None


async def _refresh(endpoint_id: str) -> list | None:
    """在飞收敛(shield + 完成回调摘除)后真正取一次;成功入缓存并**连投影一起**存。"""
    fail_reason: list[str] = [""]      # 仅创建者那个任务持有它(见 _fetch_declarations)
    inflight = _INFLIGHT.get(endpoint_id)
    if inflight is None:
        inflight = asyncio.ensure_future(_fetch_declarations(endpoint_id, fail_reason))
        _INFLIGHT[endpoint_id] = inflight
        inflight.add_done_callback(partial(_forget_inflight, endpoint_id=endpoint_id))
    # shield:本调用方被取消只落自己,不连带取消共享取数 —— 裸 await 会把取消
    # 扩散进共享任务(创建者随之收到 CancelledError);dispatcher 的
    # except Exception 不捕 CancelledError → fan-out 被判取消、不写终止 JSONL
    # 行、执行卡在 running。务必保留 shield,摘除务必留在完成回调(见模块 docstring)。
    decls = await asyncio.shield(inflight)
    if decls is None:
        # 复用他人在飞任务的等待方手上没有 fail_reason(空串 = 「未提供」,
        # 与缺省串等价),落缺省串;真正的原因由创建者那条告警透出。
        raise RuntimeError(fail_reason[0] or "declaration fetch failed")
    # 成功才 put ⇒ 时间戳打在成功那刻(U);投影随取数一起入缓存(R)。
    _cache().put(endpoint_id, (decls, frozenset(catalog_paths(decls))), _now_iso())
    return decls


async def declarations_of(endpoint_id: str) -> list | None:
    """端点 ``request.declarations`` 原始列表;取不到 → None(调用侧降级)。

    区分(承载「真无声明 vs 降级」):
    * 合法空声明(``[]`` / 缺键 / ``null``)→ ``[]``(**不是** None);
    * 垃圾值(字符串/字典等非 list)→ ``None``;
    * 非 200 / 抛异常 / 信封无 dict item → ``None``。

    返回**浅拷贝**:缓存是进程级共享状态,调用方改自己那份不会污染
    其他消费者(容器内的条目 dict 仍共享 —— 只读契约)。**两条路径都给拷贝**
    —— 取数路径若直通缓存对象,调用方一次 ``clear()`` 就能清空公共载荷。
    """
    entry, fresh = _cache().lookup(endpoint_id)
    if entry is not None and fresh:
        return list(entry.payload[0])
    if entry is not None and not fresh:
        # 过期但在回退窗内:尝试刷新;**失败则回退旧快照**(spec §1.1 D)
        try:
            refreshed = await _refresh(endpoint_id)
        except Exception:               # noqa: BLE001
            refreshed = None
        if refreshed is None:           # ← 显式,不用 or:合法空目录 [] 也有意义
            _warn_once(endpoint_id, "刷新失败,回退旧快照")
            return list(entry.payload[0])
        return list(refreshed)
    try:
        refreshed = await _refresh(endpoint_id)
    except Exception as e:              # noqa: BLE001
        _warn_once(endpoint_id, e)
        return None
    if refreshed is None:               # 显式(不用 or):_refresh 靠 raise 报失败,此处兜底
        _warn_once(endpoint_id, "取数失败")
        return None
    return list(refreshed)


async def declared_paths_of(endpoint_id: str) -> frozenset[str] | None:
    """端点声明的 request body path 全集;取不到 → None(调用方从严降级)。

    合法空声明 → 空 frozenset(**非 None**):那是「真无声明」,不是「降级」。

    投影随取数入缓存(R):TTL 命中路径直接返回那次算好的 frozenset ——
    目录树可能很大,而本函数每次 dispatch 的每个锚点都会被问一遍。
    """
    entry, fresh = _cache().lookup(endpoint_id)
    if entry is not None and fresh:
        return entry.payload[1]
    decls = await declarations_of(endpoint_id)
    if decls is None:
        return None
    entry, _ = _cache().lookup(endpoint_id)
    return entry.payload[1] if entry is not None else frozenset(catalog_paths(decls))
