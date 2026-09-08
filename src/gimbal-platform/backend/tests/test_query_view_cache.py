"""TtlLruCache:惰性过期 / LRU 逐出 / stale 窗(spec §5.1)。"""
from app.services.query_view_cache import TtlLruCache


def _cache(ttl=300.0, stale=86400.0, n=64):
    t = {"now": 1000.0}
    c = TtlLruCache(ttl=ttl, max_entries=n, stale_max_window=stale,
                    clock=lambda: t["now"])
    return c, t


def test_fresh_hit():
    c, t = _cache()
    c.put("v", [{"a": 1}], "2026-09-08T00:00:00Z")
    e, fresh = c.lookup("v")
    assert fresh and e.rows == [{"a": 1}] and e.fetched_wall == "2026-09-08T00:00:00Z"


def test_lazy_expiry_then_stale_window():
    c, t = _cache()
    c.put("v", [{}], "w1")
    t["now"] += 301            # 过 TTL,仍在 stale 窗
    e, fresh = c.lookup("v")
    assert not fresh and e is not None and e.rows == [{}]


def test_beyond_stale_window_is_true_miss():
    c, t = _cache()
    c.put("v", [{}], "w")
    t["now"] += 86401
    e, fresh = c.lookup("v")
    assert e is None and not fresh


def test_lru_eviction():
    c, _ = _cache(n=2)
    c.put("a", [{}], "w"); c.put("b", [{}], "w"); c.lookup("a")   # a 变热
    c.put("c", [{}], "w")                                           # 逐出 b
    assert c.lookup("b")[0] is None
    assert c.lookup("a")[0] is not None


def test_drop():
    c, _ = _cache()
    c.put("v", [{}], "w"); c.drop("v")
    assert c.lookup("v")[0] is None
