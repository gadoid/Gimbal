"""PlateFacade 切换路径单元测试(Phase 2 / PR-2.4)。

覆盖范围:
  - PlateMode 枚举(4 个值)
  - PlateFacade 3 个工厂(from_default / from_local / from_url)
  - mode 决策表(LOCAL_ONLY / HYBRID / REMOTE_FIRST / LOCAL_FALLBACK)
  - 字节级 pin(facade manifest == 本地 PlateManifest)
  - 旧 API 兼容性(`from Plate import registry` 仍可用)
  - DeprecationWarning 一次性触发
  - cache_stats 命中统计
  - offline / cache miss 行为
  - 错误码:value error 缺 base_url / 错 mode
  - 线程安全:CacheStats

按"多测试、小颗粒"原则编写,每个测试只验证一个行为点。
"""
from __future__ import annotations

import os
import threading
import warnings

import pytest

from Plate import registry as _reg
from Plate.facade import (
    DEFAULT_VERSION,
    CacheStats,
    OfflineError,
    PlateClient,
    PlateFacade,
    PlateMode,
)
from Plate.facade.legacy import (
    LEGACY_MIGRATION_HINT,
    reset_warn_flag,
    warn_legacy_once,
)
from Plate.facade.switch import decide_resolve
from Plate.version import PlateVersion


# ════════════════════════════════════════════════════════════════════════════
# 共享 fixture
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _clean_state():
    """每个测试前后清理 registry + DeprecationWarning flag。"""
    _reg.reset()
    reset_warn_flag()
    # 清理环境变量,避免跨测试污染
    for k in ("GIMBAL_PLATE_MODE", "GIMBAL_PLATE_URL", "GIMBAL_PLATE_VERSION"):
        os.environ.pop(k, None)
    yield
    _reg.reset()
    reset_warn_flag()
    for k in ("GIMBAL_PLATE_MODE", "GIMBAL_PLATE_URL", "GIMBAL_PLATE_VERSION"):
        os.environ.pop(k, None)


# ════════════════════════════════════════════════════════════════════════════
# PlateMode 枚举
# ════════════════════════════════════════════════════════════════════════════


class TestPlateMode:
    def test_has_4_modes(self):
        """PlateMode 含 LOCAL_ONLY / HYBRID / REMOTE_FIRST / LOCAL_FALLBACK。"""
        assert PlateMode.LOCAL_ONLY.value == "local-only"
        assert PlateMode.HYBRID.value == "hybrid"
        assert PlateMode.REMOTE_FIRST.value == "remote-first"
        assert PlateMode.LOCAL_FALLBACK.value == "local-fallback"

    def test_is_str_enum(self):
        """PlateMode 是 str 子类,可以直接当字符串用。"""
        assert isinstance(PlateMode.LOCAL_ONLY, str)
        assert PlateMode.LOCAL_ONLY == "local-only"

    def test_from_string(self):
        """PlateMode(字符串) 可逆向取值。"""
        assert PlateMode("local-only") == PlateMode.LOCAL_ONLY
        assert PlateMode("hybrid") == PlateMode.HYBRID

    def test_unknown_value_raises(self):
        """未知 mode 字符串 → ValueError。"""
        with pytest.raises(ValueError):
            PlateMode("unknown-mode")


# ════════════════════════════════════════════════════════════════════════════
# PlateFacade 工厂方法
# ════════════════════════════════════════════════════════════════════════════


class TestPlateFacadeFactories:
    def test_from_local_default_version(self):
        """from_local() 不传参 → DEFAULT_VERSION=1.0.0,LOCAL_ONLY。"""
        pf = PlateFacade.from_local()
        assert pf.mode == PlateMode.LOCAL_ONLY
        assert pf.version == DEFAULT_VERSION
        assert pf.base_url is None

    def test_from_local_explicit_version(self):
        """from_local(version=...) → 指定版本。"""
        v = PlateVersion.parse("2.3.4")
        pf = PlateFacade.from_local(version=v)
        assert pf.version == v

    def test_from_url_default_mode_is_hybrid(self):
        """from_url(url) 不传 mode → 默认 HYBRID。"""
        pf = PlateFacade.from_url("http://plate.local:8080")
        assert pf.mode == PlateMode.HYBRID
        assert pf.base_url == "http://plate.local:8080"

    def test_from_url_explicit_mode(self):
        """from_url(url, mode=REMOTE_FIRST) → 显式 mode。"""
        pf = PlateFacade.from_url(
            "http://x", mode=PlateMode.REMOTE_FIRST
        )
        assert pf.mode == PlateMode.REMOTE_FIRST

    def test_from_default_no_env(self):
        """from_default() 无环境变量 → LOCAL_ONLY。"""
        pf = PlateFacade.from_default()
        assert pf.mode == PlateMode.LOCAL_ONLY

    def test_from_default_with_env(self):
        """from_default() 读 GIMBAL_PLATE_URL + MODE → HYBRID。"""
        os.environ["GIMBAL_PLATE_URL"] = "http://env.local:9090"
        os.environ["GIMBAL_PLATE_MODE"] = "hybrid"
        pf = PlateFacade.from_default()
        assert pf.mode == PlateMode.HYBRID
        assert pf.base_url == "http://env.local:9090"

    def test_from_default_invalid_mode_falls_back(self):
        """from_default() 非法 mode 字符串 → 退回 LOCAL_ONLY。"""
        os.environ["GIMBAL_PLATE_MODE"] = "garbage"
        pf = PlateFacade.from_default()
        assert pf.mode == PlateMode.LOCAL_ONLY

    def test_from_default_invalid_version_falls_back(self):
        """from_default() 非法 version → 退回 DEFAULT_VERSION。"""
        os.environ["GIMBAL_PLATE_VERSION"] = "not-a-version"
        pf = PlateFacade.from_default()
        assert pf.version == DEFAULT_VERSION

    def test_hybrid_mode_without_url_raises(self):
        """HYBRID 模式 + 无 base_url → ValueError。"""
        with pytest.raises(ValueError, match="requires base_url"):
            PlateFacade(mode=PlateMode.HYBRID, version=DEFAULT_VERSION)


# ════════════════════════════════════════════════════════════════════════════
# PlateFacade.resolve mode 决策
# ════════════════════════════════════════════════════════════════════════════


class TestPlateFacadeResolve:
    def test_local_only_resolves_from_registry(self):
        """LOCAL_ONLY → 直接走 registry.resolve。"""
        pf = PlateFacade.from_local()
        spec = pf.resolve("fin", "POST", "/api/order/order/orderDetail")
        assert spec.method == "POST"
        assert spec.path == "/api/order/order/orderDetail"

    def test_hybrid_resolves_via_client(self):
        """HYBRID → 走 PlateClient.resolve(本会话同进程占位)。"""
        pf = PlateFacade.from_url("http://x")
        spec = pf.resolve("fin", "POST", "/api/order/order/orderDetail")
        assert spec.method == "POST"

    def test_hybrid_fallback_on_offline(self):
        """HYBRID + client offline → 静默 fallback 本地。"""
        client = PlateClient(base_url="http://x", version=DEFAULT_VERSION)
        client.set_offline(True)
        pf = PlateFacade(mode=PlateMode.HYBRID, version=DEFAULT_VERSION, client=client)
        spec = pf.resolve("fin", "POST", "/api/order/order/orderDetail")
        assert spec.method == "POST"  # fallback 成功

    def test_remote_first_offline_raises(self):
        """REMOTE_FIRST + client offline + cache miss → OfflineError。"""
        client = PlateClient(base_url="http://x", version=DEFAULT_VERSION)
        client.set_offline(True)
        pf = PlateFacade(
            mode=PlateMode.REMOTE_FIRST, version=DEFAULT_VERSION, client=client,
        )
        with pytest.raises(OfflineError):
            pf.resolve("fin", "POST", "/api/order/order/orderDetail")

    def test_local_fallback_offline_raises(self):
        """LOCAL_FALLBACK + offline + cache miss → OfflineError。"""
        client = PlateClient(base_url="http://x", version=DEFAULT_VERSION)
        client.set_offline(True)
        pf = PlateFacade(
            mode=PlateMode.LOCAL_FALLBACK, version=DEFAULT_VERSION, client=client,
        )
        with pytest.raises(OfflineError):
            pf.resolve("fin", "POST", "/api/order/order/orderDetail")

    def test_unknown_service_raises_lookup(self):
        """未知 service → LookupError(facade 不静默吞错)。"""
        pf = PlateFacade.from_local()
        with pytest.raises(LookupError):
            pf.resolve("nonexistent", "GET", "/x")


# ════════════════════════════════════════════════════════════════════════════
# PlateFacade.manifest 字节级 pin
# ════════════════════════════════════════════════════════════════════════════


class TestPlateFacadeManifest:
    def test_manifest_local_only(self):
        """LOCAL_ONLY manifest 含 version + services + checksum。"""
        pf = PlateFacade.from_local()
        m = pf.manifest()
        assert "version" in m
        assert "services" in m
        assert "checksum" in m
        assert "fin" in m["services"]
        assert len(m["services"]["fin"]) > 0  # 31 个 spec

    def test_manifest_byte_equal_to_registry(self):
        """facade manifest checksum == registry 直算 checksum。"""
        from Plate.manifest import PlateManifest
        _reg.collect("fin")
        local_services = {
            svc: [
                s.to_dict() for k, s in _reg._index.items() if k.service == svc
            ]
            for svc in {k.service for k in _reg._index}
        }
        local = PlateManifest.from_services(
            DEFAULT_VERSION, local_services
        ).to_dict()
        pf = PlateFacade.from_local()
        facade_m = pf.manifest()
        assert facade_m["checksum"] == local["checksum"]
        assert facade_m["services"] == local["services"]


# ════════════════════════════════════════════════════════════════════════════
# cache_stats / reset_cache
# ════════════════════════════════════════════════════════════════════════════


class TestPlateFacadeCacheStats:
    def test_local_only_stats(self):
        """LOCAL_ONLY cache_stats 永远 {hit:0, miss:0}。"""
        pf = PlateFacade.from_local()
        assert pf.cache_stats() == {"mode": "local-only", "hit": 0, "miss": 0}

    def test_remote_stats_after_resolve(self):
        """resolve 一次后 cache_stats 增 1(同进程占位 miss)。"""
        pf = PlateFacade.from_url("http://x")
        pf.resolve("fin", "POST", "/api/order/order/orderDetail")
        stats = pf.cache_stats()
        assert stats["miss"] >= 1

    def test_cache_stats_hit_on_second_resolve(self):
        """第二次 resolve 同一 (service, method, path) → hit 1。"""
        pf = PlateFacade.from_url("http://x")
        pf.resolve("fin", "POST", "/api/order/order/orderDetail")
        pf.resolve("fin", "POST", "/api/order/order/orderDetail")
        stats = pf.cache_stats()
        assert stats["hit"] >= 1


# ════════════════════════════════════════════════════════════════════════════
# 旧 API 兼容
# ════════════════════════════════════════════════════════════════════════════


class TestLegacyCompatibility:
    def test_legacy_registry_resolve_works(self):
        """``from Plate import registry`` 仍能 resolve spec。"""
        from Plate import registry
        spec = registry.resolve(
            "fin", "POST", "/api/order/order/orderDetail"
        )
        assert spec is not None

    def test_deprecation_warning_emitted_once(self):
        """warn_legacy_once() 第一次触发 DeprecationWarning,第二次不触发。"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_legacy_once()
            warn_legacy_once()
            deprecations = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
        assert len(deprecations) == 1
        assert LEGACY_MIGRATION_HINT in str(deprecations[0].message)

    def test_facade_construct_emits_warning(self):
        """PlateFacade() 构造时触发 legacy 迁移提示。"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            PlateFacade.from_local()
            deprecations = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
        assert len(deprecations) == 1


# ════════════════════════════════════════════════════════════════════════════
# decide_resolve 纯函数(直接测试)
# ════════════════════════════════════════════════════════════════════════════


class TestDecideResolve:
    def test_local_only_with_none_client(self):
        """LOCAL_ONLY + client=None → 直走 registry。"""
        spec = decide_resolve(
            mode=PlateMode.LOCAL_ONLY, client=None,
            service="fin", method="POST", path="/api/order/order/orderDetail",
        )
        assert spec.method == "POST"

    def test_hybrid_fallback_log_called(self):
        """HYBRID + offline → fallback_log 被调一次。"""
        client = PlateClient(base_url="http://x", version=DEFAULT_VERSION)
        client.set_offline(True)
        log_msgs: list[str] = []
        decide_resolve(
            mode=PlateMode.HYBRID, client=client,
            service="fin", method="POST", path="/api/order/order/orderDetail",
            fallback_log=log_msgs.append,
        )
        assert len(log_msgs) == 1
        assert "fallback" in log_msgs[0]

    def test_hybrid_no_fallback_log_on_success(self):
        """HYBRID + 正常 → fallback_log 不被调。"""
        client = PlateClient(base_url="http://x", version=DEFAULT_VERSION)
        log_msgs: list[str] = []
        decide_resolve(
            mode=PlateMode.HYBRID, client=client,
            service="fin", method="POST", path="/api/order/order/orderDetail",
            fallback_log=log_msgs.append,
        )
        assert log_msgs == []


# ════════════════════════════════════════════════════════════════════════════
# PlateClient 行为
# ════════════════════════════════════════════════════════════════════════════


class TestPlateClient:
    def test_resolve_miss_then_hit(self):
        """第一次 resolve = miss,第二次 = hit。"""
        client = PlateClient(base_url="http://x", version=DEFAULT_VERSION)
        client.resolve("fin", "POST", "/api/order/order/orderDetail")
        client.resolve("fin", "POST", "/api/order/order/orderDetail")
        stats = client.cache_stats()
        assert stats["miss"] == 1
        assert stats["hit"] == 1

    def test_resolve_offline_miss_raises(self):
        """offline + cache miss → OfflineError。"""
        client = PlateClient(base_url="http://x", version=DEFAULT_VERSION)
        client.set_offline(True)
        with pytest.raises(OfflineError):
            client.resolve("fin", "POST", "/api/order/order/orderDetail")

    def test_manifest_offline_no_cache_raises(self):
        """offline + 无 manifest cache → OfflineError。"""
        client = PlateClient(base_url="http://x", version=DEFAULT_VERSION)
        client.set_offline(True)
        with pytest.raises(OfflineError):
            client.manifest()

    def test_reset_cache_clears_all(self):
        """reset_cache() 清 spec 缓存 + manifest 缓存 + stats。"""
        client = PlateClient(base_url="http://x", version=DEFAULT_VERSION)
        client.resolve("fin", "POST", "/api/order/order/orderDetail")
        client.manifest()
        client.reset_cache()
        assert client.cache_stats() == {"hit": 0, "miss": 0, "last_sync_at": 0.0}


# ════════════════════════════════════════════════════════════════════════════
# CacheStats 线程安全
# ════════════════════════════════════════════════════════════════════════════


class TestCacheStatsThreadSafety:
    def test_concurrent_hit_miss(self):
        """10 线程并发 record_hit/record_miss,最终计数正确。"""
        stats = CacheStats()
        n_threads = 10
        n_per_thread = 100

        def worker():
            for _ in range(n_per_thread):
                stats.record_hit()
                stats.record_miss()

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snap = stats.snapshot()
        assert snap["hit"] == n_threads * n_per_thread
        assert snap["miss"] == n_threads * n_per_thread
        assert snap["last_sync_at"] > 0  # 至少一个 hit 写过
