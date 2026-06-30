"""PlateFacade 内部 mode 决策路由(对应 PR-2.4 §2.4)。

将"按 mode 决定走 SDK 还是本地"的逻辑抽出来,便于单测覆盖每个分支。
纯函数:不持任何状态,不调用 ``PlateFacade`` 类(避免循环依赖)。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from Plate import registry as _legacy_registry

from Plate.facade.client import PlateClient
from Plate.facade.errors import OfflineError, PlateMode


__all__ = ["decide_resolve"]


def decide_resolve(
    *,
    mode: PlateMode,
    client: Optional[PlateClient],
    service: str,
    method: str,
    path: str,
    fallback_log: Optional[Callable[[str], None]] = None,
) -> Any:
    """按 mode 决定 resolve 路径(纯函数,无副作用)。

    参数:
      - mode:PlateMode 枚举
      - client:PlateClient 实例(LOCAL_ONLY 时可为 None)
      - fallback_log:HYBRID fallback 时调用的日志函数(可注入测试 spy)

    返回:EndpointSpec 实例
    抛:OfflineError(REMOTE_FIRST / LOCAL_FALLBACK 模式下,SDK 拉不到)
    """
    if mode == PlateMode.LOCAL_ONLY or client is None:
        return _legacy_registry.resolve(service, method, path)
    if mode == PlateMode.HYBRID:
        try:
            return client.resolve(service, method, path)
        except OfflineError as e:
            if fallback_log is not None:
                fallback_log(f"SDK 不可达,fallback 本地: {e}")
            return _legacy_registry.resolve(service, method, path)
    # REMOTE_FIRST / LOCAL_FALLBACK:不静默 fallback
    return client.resolve(service, method, path)
