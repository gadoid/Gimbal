"""query_view_cache —— 组合期取数行集缓存(2026-09-07 spec §5.1)。

进程内 TtlLruCache(OrderedDict,~40 行语义):
惰性过期(读时判 TTL,无后台线程)/ LRU 容量逐出 / stale-while-error 回退窗。
纪律:错误永不 put;空列表是合法答案可缓存;键 = (view, 查询凭证)(§5.1
修订 11:同视图异凭证各自缓存,权限视角不在缓存层串台)。

**载荷泛化**(2026-09-13,架构收敛 §3.1):条目载荷是 ``payload`` 而非
``rows`` —— 一套 TTL/LRU/回退语义由两个消费者共用:query-view 行集
(``list[dict]``)与契约声明面的 ``(decls, frozenset(catalog_paths(decls)))``。
字段叫 ``rows`` 会让第二个消费者"名不副实";``truncated`` 仍只对行集有意义
(声明面恒为默认 ``False``)。
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Callable, Hashable


class CacheEntry:
    __slots__ = ("payload", "truncated", "fetched_wall", "fetched_mono")

    def __init__(self, payload: Any, truncated: bool,
                 fetched_wall: str, fetched_mono: float):
        self.payload = payload
        self.truncated = truncated   # §5.1 截断标记随行集入缓存(命中也透出)
        self.fetched_wall = fetched_wall
        self.fetched_mono = fetched_mono


class TtlLruCache:
    def __init__(self, *, ttl: float, max_entries: int, stale_max_window: float,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl
        self._max = max_entries
        self._stale_window = stale_max_window
        self._clock = clock
        self._data: "OrderedDict[Hashable, CacheEntry]" = OrderedDict()

    def lookup(self, key: Hashable) -> "tuple[CacheEntry | None, bool]":
        e = self._data.get(key)
        if e is None:
            return None, False
        self._data.move_to_end(key)
        age = self._clock() - e.fetched_mono
        if age <= self._ttl:
            return e, True
        if age <= self._stale_window:
            return e, False        # 过期但在回退窗内(stale-while-error 候选)
        self._data.pop(key, None)
        return None, False         # 超 STALE_MAX_WINDOW:真过期

    def put(self, key: Hashable, payload: Any, fetched_wall: str,
            truncated: bool = False) -> None:
        self._data.pop(key, None)
        self._data[key] = CacheEntry(payload, truncated, fetched_wall,
                                     self._clock())
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def drop(self, key: Hashable) -> None:
        self._data.pop(key, None)

    def drop_where(self, match: "Callable[[Hashable], bool]") -> None:
        """逐键条件清除(修订 11:drop_credential 按凭证分量清 L1,§5.1)。"""
        for k in [k for k in self._data if match(k)]:
            self._data.pop(k, None)
