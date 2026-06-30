"""Plate 子系统门面(Phase 2 / PR-2.4)。

设计目标(对应 A4 + A6 + 不变承诺 5):
  - 业务代码统一通过 ``PlateFacade`` 拿 contract
  - 默认 LOCAL_ONLY(行为与旧 ``from Plate import registry`` 一致)
  - HYBRID 模式:SDK 拉远端 → 失败 → 静默 fallback 本地
  - 旧 API ``from Plate import registry`` 继续可用,但 ``PlateFacade`` 是
    推荐入口

用法::

    from Plate.facade import PlateFacade, PlateMode

    # 默认(LOCAL_ONLY,等同旧 API)
    pf = PlateFacade.from_default()

    # 显式本地(开发/单测)
    pf = PlateFacade.from_local()

    # 显式远端
    pf = PlateFacade.from_url("http://plate.internal:8080")

    spec = pf.resolve("fin", "POST", "/api/order/order/orderDetail")
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from Plate import registry as _legacy_registry
from Plate.manifest import PlateManifest
from Plate.version import PlateVersion

from Plate.facade.client import CacheStats, PlateClient
from Plate.facade.errors import DEFAULT_VERSION, OfflineError, PlateMode
from Plate.facade.legacy import warn_legacy_once
from Plate.facade.switch import decide_resolve


__all__ = [
    "PlateMode",
    "PlateClient",
    "PlateFacade",
    "OfflineError",
    "CacheStats",
    "DEFAULT_VERSION",
]


_log = logging.getLogger("plate.facade")


# ════════════════════════════════════════════════════════════════════════════
# PlateFacade
# ════════════════════════════════════════════════════════════════════════════


class PlateFacade:
    """Plate 子系统业务入口(对应 PR-2.4 §2.2 GIMBAL → 重命名为 PlateFacade)。

    3 个工厂:
      - ``from_default()``:从环境变量读 mode + base_url,缺省 LOCAL_ONLY
      - ``from_local()``:永远只走本地 registry
      - ``from_url(url)``:走 SDK,可选 mode(HYBRID/REMOTE_FIRST/LOCAL_FALLBACK)

    业务方法:
      - ``resolve(service, method, path)``:按 mode 路由
      - ``manifest()``:返回 manifest dict
      - ``cache_stats()``:缓存命中统计
    """

    def __init__(
        self,
        *,
        mode: PlateMode,
        version: PlateVersion,
        base_url: Optional[str] = None,
        cache_dir: Optional[str] = None,
        client: Optional[PlateClient] = None,
    ) -> None:
        self._mode = mode
        self._version = version
        self._base_url = base_url
        self._cache_dir = cache_dir
        if client is not None:
            self._client = client
        elif mode in (PlateMode.HYBRID, PlateMode.REMOTE_FIRST, PlateMode.LOCAL_FALLBACK):
            if not base_url:
                raise ValueError(
                    f"[PlateFacade] mode={mode} requires base_url"
                )
            self._client = PlateClient(
                base_url=base_url,
                version=version,
                cache_dir=cache_dir,
            )
        else:
            self._client = None  # LOCAL_ONLY

        # 首次通过 facade 入口访问时,触发一次 legacy 迁移提示
        warn_legacy_once()

    # ── 工厂方法(显式优于隐式)──

    @classmethod
    def from_default(cls) -> "PlateFacade":
        """默认入口:从环境变量读 mode + base_url,缺省走 LOCAL_ONLY。"""
        mode_str = os.environ.get("GIMBAL_PLATE_MODE", "local-only")
        try:
            mode = PlateMode(mode_str)
        except ValueError:
            mode = PlateMode.LOCAL_ONLY
        base_url = os.environ.get("GIMBAL_PLATE_URL")
        version_str = os.environ.get("GIMBAL_PLATE_VERSION", "1.0.0")
        try:
            version = PlateVersion.parse(version_str)
        except ValueError:
            version = DEFAULT_VERSION
        if mode == PlateMode.LOCAL_ONLY or not base_url:
            return cls(mode=PlateMode.LOCAL_ONLY, version=version)
        return cls(mode=mode, version=version, base_url=base_url)

    @classmethod
    def from_local(
        cls, version: PlateVersion = DEFAULT_VERSION
    ) -> "PlateFacade":
        """显式本地模式:不连远端,纯本地 registry。"""
        return cls(mode=PlateMode.LOCAL_ONLY, version=version)

    @classmethod
    def from_url(
        cls,
        base_url: str,
        version: PlateVersion = DEFAULT_VERSION,
        cache_dir: Optional[str] = None,
        mode: PlateMode = PlateMode.HYBRID,
    ) -> "PlateFacade":
        """显式远端模式:可指定 HYBRID / REMOTE_FIRST / LOCAL_FALLBACK。"""
        return cls(
            mode=mode,
            version=version,
            base_url=base_url,
            cache_dir=cache_dir,
        )

    # ── 业务方法 ──

    def resolve(self, service: str, method: str, path: str) -> Any:
        """按 (service, method, path) 拿 EndpointSpec。

        行为依赖 mode(委托 ``gimbal._switch.decide_resolve``):
          - LOCAL_ONLY:直接 ``registry.resolve()``
          - HYBRID:SDK 拉远端 → 失败 fallback 本地
          - REMOTE_FIRST:SDK 拉远端 → 失败 → OfflineError 上抛
          - LOCAL_FALLBACK:SDK 拉远端 → 失败 → 读缓存 → 仍失败 → OfflineError
        """
        return decide_resolve(
            mode=self._mode,
            client=self._client,
            service=service,
            method=method,
            path=path,
            fallback_log=lambda msg: _log.debug("[PlateFacade] %s", msg),
        )

    def manifest(self) -> dict:
        """返回 manifest dict(走 SDK 或本地,取决于 mode)。"""
        if self._mode == PlateMode.LOCAL_ONLY or self._client is None:
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
            return PlateManifest.from_services(self._version, services).to_dict()
        return self._client.manifest()

    def cache_stats(self) -> dict[str, Any]:
        """缓存命中统计。"""
        if self._client is None:
            return {"mode": "local-only", "hit": 0, "miss": 0}
        return self._client.cache_stats()

    @property
    def mode(self) -> PlateMode:
        return self._mode

    @property
    def version(self) -> PlateVersion:
        return self._version

    @property
    def base_url(self) -> Optional[str]:
        return self._base_url
