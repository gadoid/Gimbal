"""旧 ``from Plate import registry`` 桥接(对应 PR-2.4 §2.3 + D23)。

策略:本模块**不**替换 ``Plate.registry`` 的导出,也不修改其行为。
旧 API 继续走 ``registry._index`` 直读(零网络、零缓存),行为完全不变。
DeprecationWarning 在用户首次通过 ``PlateFacade`` 显式选择 mode 时发一次
(给用户一个明确的"建议迁移"信号,而非污染静默调用)。
"""
from __future__ import annotations

import warnings

__all__ = ["warn_legacy_once", "reset_warn_flag", "LEGACY_MIGRATION_HINT"]


LEGACY_MIGRATION_HINT = (
    "[Plate] ``from Plate import registry`` 是遗留路径。"
    "请迁移到 ``from Plate.facade import PlateFacade`` "
    "(默认 mode = LOCAL_ONLY,行为与旧 API 一致;新代码用 PlateFacade.from_url(...) 走 SDK)。"
    "本 PR(2.4)周期内仍可用,Phase 3 收尾前保留。"
)

_warned = False


def warn_legacy_once() -> None:
    """发一次 DeprecationWarning(整个进程期内)。"""
    global _warned
    if not _warned:
        warnings.warn(LEGACY_MIGRATION_HINT, DeprecationWarning, stacklevel=3)
        _warned = True


def reset_warn_flag() -> None:
    """测试用:重置 _warned 标志(单测隔离)。"""
    global _warned
    _warned = False
