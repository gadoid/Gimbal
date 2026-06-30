"""PlateClient — Plate 子系统的轻量客户端(Phase 2 / PR-2.4 同进程实现)。

设计目标(对应 A4 + A6 + 不变承诺 5):
  - ``PlateClient`` 是 ``PlateFacade`` 的数据获取后端
  - 本会话实现是**同进程占位**:直接调 ``Plate.registry`` + 内存缓存,模拟
    "远端权威"语义,便于单测与 E2E
  - Phase 3 替换为真 HTTP(urllib + retries),``PlateClient`` 对外接口不变

对外接口:
  - ``resolve(service, method, path)`` → EndpointSpec
  - ``manifest()`` → dict
  - ``cache_stats()`` → dict
  - ``reset_cache()`` → None
  - ``set_offline(bool)`` → None(测试用,模拟网络抖动)
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional

from Plate import registry as _legacy_registry
from Plate.manifest import PlateManifest
from Plate.version import PlateVersion

from Plate.facade.errors import OfflineError  # noqa: F401  (re-export)


__all__ = ["PlateClient", "CacheStats"]


# ════════════════════════════════════════════════════════════════════════════
# 缓存统计(线程安全)
# ════════════════════════════════════════════════════════════════════════════


class CacheStats:
    """缓存命中统计(可观测性)。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hit = 0
        self._miss = 0
        self._last_sync_at: float = 0.0

    def record_hit(self) -> None:
        with self._lock:
            self._hit += 1
            self._last_sync_at = time.time()

    def record_miss(self) -> None:
        with self._lock:
            self._miss += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "hit": self._hit,
                "miss": self._miss,
                "last_sync_at": self._last_sync_at,
            }

    def reset(self) -> None:
        with self._lock:
            self._hit = 0
            self._miss = 0
            self._last_sync_at = 0.0


# ════════════════════════════════════════════════════════════════════════════
# 同进程 PlateClient
# ════════════════════════════════════════════════════════════════════════════


class PlateClient:
    """Plate SDK(同进程占位实现,Phase 3 替换为真 HTTP)。

    离线检测:本会话用 "显式 offline=True" 模拟(便于单测);
    Phase 3 替换为 URLError / TimeoutError 捕获 + retries。
    """

    def __init__(
        self,
        *,
        base_url: str,
        version: PlateVersion,
        cache_dir: Optional[str] = None,
        offline: bool = False,
    ) -> None:
        self.base_url = base_url
        self.version = version
        self.cache_dir = cache_dir
        self._offline = offline
        self._stats = CacheStats()
        # 本地缓存(同进程内,内存 dict;落盘在 Phase 3 实现)
        self._cache: dict[tuple[str, str, str], Any] = {}
        self._manifest_cache: Optional[dict] = None

    def set_offline(self, offline: bool) -> None:
        """测试用:切换 offline 状态(模拟网络抖动)。"""
        self._offline = offline

    def resolve(self, service: str, method: str, path: str) -> Any:
        """按 (service, method, path) 拿 EndpointSpec。"""
        key = (service, method.upper(), path)
        # 1. 查缓存
        if key in self._cache:
            self._stats.record_hit()
            return self._cache[key]
        # 2. 拉"远端"(本会话:同进程 registry)
        if self._offline:
            self._stats.record_miss()
            raise OfflineError(f"PlateClient offline + cache miss: {key}")
        # 3. 本会话走本地 registry 模拟"远端权威"
        _legacy_registry.collect(service)
        spec = _legacy_registry.resolve(service, method, path)
        self._cache[key] = spec
        self._stats.record_miss()
        return spec

    def manifest(self) -> dict:
        """返回 manifest dict。"""
        if self._manifest_cache is not None:
            self._stats.record_hit()
            return dict(self._manifest_cache)
        if self._offline:
            self._stats.record_miss()
            raise OfflineError("PlateClient offline + no manifest cache")
        # 构造 manifest — 走 SUPPORTED_SERVICES 风格的固定列表(本会话只支持 fin)
        services: dict[str, list[dict]] = {}
        for svc in ("fin",):
            try:
                _legacy_registry.collect(svc)
            except LookupError:
                continue
            services[svc] = [
                s.to_dict() for k, s in _legacy_registry._index.items()
                if k.service == svc
            ]
        m = PlateManifest.from_services(self.version, services)
        self._manifest_cache = m.to_dict()
        self._stats.record_miss()
        return dict(self._manifest_cache)

    def cache_stats(self) -> dict[str, Any]:
        return self._stats.snapshot()

    def reset_cache(self) -> None:
        self._cache.clear()
        self._manifest_cache = None
        self._stats.reset()
