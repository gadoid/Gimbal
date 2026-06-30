"""facade 子包共享类型 — 异常、枚举。

按"类型与具体实现分离"惯例,errors.py 不依赖任何 facade 内部模块,
只 import stdlib + ``Plate.version``。其他 facade 模块反向依赖本文件。
"""
from __future__ import annotations

from enum import Enum

from Plate.version import PlateVersion


__all__ = ["PlateMode", "OfflineError", "DEFAULT_VERSION"]


class PlateMode(str, Enum):
    """Plate 数据源模式(对应 A4 本地优先 + A6 向后兼容)。"""

    HYBRID = "hybrid"
    REMOTE_FIRST = "remote-first"
    LOCAL_FALLBACK = "local-fallback"
    LOCAL_ONLY = "local-only"


class OfflineError(RuntimeError):
    """网络不可达 + 本地缓存也不命中时上抛(对应 REMOTE_FIRST / LOCAL_FALLBACK)。"""


DEFAULT_VERSION: PlateVersion = PlateVersion(1, 0, 0)
