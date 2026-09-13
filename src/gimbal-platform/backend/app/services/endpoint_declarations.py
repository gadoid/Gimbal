"""契约声明面派生(spec v3.1 §3)— carry 面 + dispatch 悬空判定共用。

语义:某端点 ``GET /api/endpoint/{id}/full`` → ``data.item.request.declarations``
的**原始声明列表**(目录态)。本模块服务**两个**消费者:

* ``declarations_of`` — 原始列表(``carry_injection.build_carry_context``
  的面投影输入);
* ``declared_paths_of`` — path 全集(模板形态;dispatch 悬空判定,T4)。

**取数不在这里**:两条路径都问 ``plate_client.get_endpoint_full`` ——
``/full`` 契约、整份 item 的 TTL/LRU/回退窗与在飞收敛都归那一层;本模块
只从 item 派生声明面,并把自己那份 path 投影另存一份(见 ``_proj_cache``)。

**本模块不是唯一的 ``/full`` 取数路径**(勿读作「唯一」):
``adaptation_service._plate_full_endpoint`` 也打同一个端点,其结果被
``routers/carry.py`` / ``carry_store.py`` 当 declarations 读;
``routers/endpoint_catalog.py`` 亦有自己的取数(composer 代理等)。这几条
各自独立、**不共享** ``plate_client`` 的 item 缓存 —— 本模块只收敛上面那
两个消费者。

纪律(与 carry 同款:增强不是前置条件):
* **fail-soft** — 任何故障(plate 不可达 / 非 200 / 信封缺 dict item /
  ``declarations`` 为垃圾值)返回 ``None``,调用方降级(carry 空面 /
  悬空判定只认 body 面),绝不阻塞执行;取数侧那半归 ``plate_client``;
* **告警在本模块** — 「声明面不可得」是**消费者侧**判断:取数层只交
  ``reason`` / ``stale``,由本模块按端点 + 冷却窗去重后发 warning。告警表
  ``_WARNED_AT`` 只随**时间**老化,成功事件不重置它 —— 否则长期失败的端点
  在恢复前彻底失声(而它的告警正是降级的唯一遥测);
* **投影随取数缓存(R)** — TTL 命中路径直接取那次算好的 frozenset,不再遍历
  声明树(``declared_paths_of`` 每次 dispatch 都会被问);
* **返回浅拷贝** — ``declarations_of`` 返回浅拷贝:plate_client 的 item 是
  进程级共享面,调用方改自己那份不污染他人(容器内的条目 dict 仍共享 ——
  只读契约);
* **空目录 ≠ 降级** — 真无声明(``[]`` / 封套缺 ``request.declarations``
  / 其为 ``null``)是**成功结果**:carry 侧空面、``declared_paths_of``
  空 frozenset。只有**拿不到**声明面才 ``None``。
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from ..core.config import settings
from .field_state_resolution import catalog_paths
from .plate_client import _reset_full_cache_for_test, get_endpoint_full
from .query_view_cache import TtlLruCache

_PROJ_CACHE: TtlLruCache | None = None
_PROJ_CFG: tuple[float, int, float] | None = None
_WARNED_AT: dict[str, float] = {}          # eid → 最近一次告警时刻(冷却窗 = _WARN_COOLDOWN_SEC)
_WARN_COOLDOWN_SEC = 300.0


def _proj_cache() -> TtlLruCache:
    """投影缓存:与取数缓存同 ttl/容量/回退窗,载荷 = frozenset(paths)。

    为什么另立一份而不是塞进 plate_client:投影是**平台域概念**
    (``catalog_paths``),plate_client 只该懂 plate 契约。两份缓存的 ttl 同源,
    且投影是 item 的纯函数 ⇒ 二者永不分歧。

    实例随 settings 惰性重建:``TtlLruCache`` 的 ttl/容量/回退窗**构造即冻结**,
    而这三个值来自 settings(测试 monkeypatch、运维热改都要求即刻生效)⇒ 比对
    当前 cfg 与建例时的 cfg,不一致就换实例(生产 cfg 恒定 ⇒ 等价于模块级单例)。
    """
    global _PROJ_CACHE, _PROJ_CFG
    cfg = (settings.DECLARED_PATHS_TTL_SEC,
           settings.DECLARED_PATHS_MAX_ENTRIES,
           settings.DECLARED_PATHS_STALE_WINDOW_SEC)
    if _PROJ_CACHE is None or cfg != _PROJ_CFG:
        _PROJ_CACHE = TtlLruCache(ttl=cfg[0], max_entries=cfg[1], stale_max_window=cfg[2])
        _PROJ_CFG = cfg
    return _PROJ_CACHE


def _reset_declared_paths_cache() -> None:
    """测试钩子:丢弃投影缓存实例、丢弃取数缓存、清告警表。

    三样都是**声明面**的状态:声明面从 ``plate_client`` 缓存的 item 派生,
    只丢投影会让下一例读到上一例留下的 item —— 声明面照旧陈旧,而调用方
    (测试)重置的正是「声明面取数」。故取数缓存一并丢。

    丢弃(而非逐键清)是必须的:``TtlLruCache`` 的 ttl/容量/回退窗构造即冻结,
    而调用方(测试)先 monkeypatch settings 再重置 —— 只有换实例才让新值生效
    (``_proj_cache`` 下次调用时按当前 settings 重建)。
    """
    global _PROJ_CACHE
    _PROJ_CACHE = None
    _reset_full_cache_for_test()
    _WARNED_AT.clear()


def _now_iso() -> str:
    """缓存条目的墙钟时刻(仅用于可读诊断)。"""
    return datetime.now(timezone.utc).isoformat()


def _warn_once(endpoint_id: str, reason: object) -> None:
    """降级告警(**时间老化**):同一端点在 `_WARN_COOLDOWN_SEC` 内至多一条。

    表大小 ~ 冷却窗内失败过的端点数:下表顺手回收窗外的条目,故调用方字符串
    (错拼/改名)驱动的增长有界(spec §1.1 S);回收时机与 `TtlLruCache.lookup`
    的惰性过期同风格。"""
    now = time.monotonic()
    last = _WARNED_AT.get(endpoint_id)
    if last is not None and now - last < _WARN_COOLDOWN_SEC:
        return
    # 顺手老化解表(同 TtlLruCache.lookup 的惰性过期)
    for aged in [k for k, t in _WARNED_AT.items() if now - t >= _WARN_COOLDOWN_SEC]:
        _WARNED_AT.pop(aged, None)
    _WARNED_AT[endpoint_id] = now
    logger.warning(
        "endpoint_declarations: {} 声明面不可得({}) — 调用侧降级"
        "(carry 空面 / 悬空判定只认 body 面)",
        endpoint_id, reason,
    )


def _decls_of_item(item: dict[str, Any]) -> list | None:
    """从 item 取 ``request.declarations``;垃圾形状 → None(降级)。

    缺省合并(例外,已核等价性 —— 不是「有意义 falsy 被真值合并」):``request``
    缺失 / ``None`` / 其它 falsy(``{}`` / ``0`` / ``""`` / ``[]``)都落到缺省 ``{}``,
    与 ``declarations`` 为 ``None``(缺键 / ``null``)同款 —— 两者都得真无声明 ``[]``。

    降级(读不出声明面)只认两种形状:``request`` 为**真值**非 dict(``"oops"`` /
    ``5`` / ``[1]``),或 ``declarations`` 非 list(此处 falsy 也算 —— ``0`` / ``""`` /
    ``{}`` 都降级;与 ``request`` 侧走缺省合并不对称,是既有语义)。

    为什么显式判类型而不包一层 ``except``:取数层 ``get_endpoint_full`` 已保证绝不抛,
    本函数只剩「读两个键」—— 试错式捕获会把无关的编程错误一并吞成降级;而 plate 只
    校验 item 是 dict(``_fetch_full_raw``),点明这两种形状正是本层的判据。
    """
    req = item.get("request") or {}      # §5 例外:缺省合并(未提供 → {})
    if not isinstance(req, dict):
        return None                      # 真值非 dict 的 request = 拿不到契约面
    decls = req.get("declarations")
    if decls is None:
        return []
    if not isinstance(decls, list):
        return None
    return decls


async def declarations_of(endpoint_id: str) -> list | None:
    """端点 ``request.declarations`` 原始列表;取不到 → None(调用侧降级)。

    返回**浅拷贝**:缓存是进程级共享状态,调用方改自己那份不污染他人。
    """
    res = await get_endpoint_full(endpoint_id)
    if res.item is None:
        _warn_once(endpoint_id, res.reason)
        return None
    if res.stale:
        _warn_once(endpoint_id, f"刷新失败({res.reason}),回退旧快照")
    decls = _decls_of_item(res.item)
    if decls is None:
        # 两种垃圾形状都到这里,故原因串把两条都点出来(告警是降级链路唯一的遥测,
        # 写成单侧会让另一种形状的现场指向错误的键)。
        _warn_once(endpoint_id, "声明面形状不可解析(request 非 dict 或 declarations 非 list)")
    return None if decls is None else list(decls)


async def declared_paths_of(endpoint_id: str) -> frozenset[str] | None:
    """端点声明的 request body path 全集;取不到 → None(调用方从严降级)。

    合法空声明 → 空 frozenset(**非 None**):那是「真无声明」,不是「降级」。
    """
    entry, fresh = _proj_cache().lookup(endpoint_id)
    if entry is not None and fresh:
        return entry.payload
    decls = await declarations_of(endpoint_id)
    if decls is None:
        return None
    proj = frozenset(catalog_paths(decls))
    _proj_cache().put(endpoint_id, proj, _now_iso())
    return proj
