"""query_view_cache —— 组合期取数行集缓存(2026-09-07 spec §5.1)。

进程内 TtlLruCache(OrderedDict,~40 行语义):
惰性过期(读时判 TTL,无后台线程)/ LRU 容量逐出 / stale-while-error 回退窗。
纪律:错误永不 put;空列表是合法答案可缓存;键 = view name(§5.1)。
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Callable


class CacheEntry:
    __slots__ = ("rows", "fetched_wall", "fetched_mono")

    def __init__(self, rows: list[dict], fetched_wall: str, fetched_mono: float):
        self.rows = rows
        self.fetched_wall = fetched_wall
        self.fetched_mono = fetched_mono


class TtlLruCache:
    def __init__(self, *, ttl: float, max_entries: int, stale_max_window: float,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl
        self._max = max_entries
        self._stale_window = stale_max_window
        self._clock = clock
        self._data: "OrderedDict[str, CacheEntry]" = OrderedDict()

    def lookup(self, key: str) -> "tuple[CacheEntry | None, bool]":
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

    def put(self, key: str, rows: list[dict], fetched_wall: str) -> None:
        self._data.pop(key, None)
        self._data[key] = CacheEntry(rows, fetched_wall, self._clock())
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def drop(self, key: str) -> None:
        self._data.pop(key, None)
