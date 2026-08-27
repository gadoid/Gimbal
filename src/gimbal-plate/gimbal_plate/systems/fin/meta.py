"""systems.fin.meta —— fin 系统的 Meta 默认模板工厂。

调用 ``common_meta_template``,从 ``gimbal_plate.systems.fin.system_info``
读取 fin 专属默认(系统身份 / 默认值 / 模板字符串 / createTime 锚点)。

默认值集合等于 ``system_info`` 中 B/C/D 分类的全部常量;
调用方可用 kwargs 进一步覆盖(如改 author/owner 给特定 team)。
"""
from __future__ import annotations

from typing import Any

from gimbal_plate.schema import Meta

from gimbal_plate.systems.common.meta import common_meta_template
from gimbal_plate.systems.fin import system_info


def fin_meta_template(**overrides: Any) -> Meta:
    """构造 fin 系统的 Meta 默认模板。

    默认值全部来自 ``system_info``:

    - ``system``     = [FIN_SYSTEM]
    - ``name``       = FIN_META_NAME_TEMPLATE.format(system=FIN_SYSTEM)
    - ``description``= FIN_META_DESCRIPTION_TEMPLATE.format(system=FIN_SYSTEM)
    - ``module``     = FIN_DEFAULT_MODULE
    - ``priority``   = FIN_DEFAULT_PRIORITY
    - ``author``     = FIN_DEFAULT_AUTHOR
    - ``owner``      = FIN_DEFAULT_OWNER
    - ``tags``       = list(FIN_DEFAULT_TAGS)
    - ``createTime`` = FIN_CREATE_TIME_ANCHOR(冻结 UTC 锚点,便于 round-trip 测试)

    调用方可用 kwargs 进一步覆盖。
    """
    fin_defaults: dict[str, Any] = {
        "system":      [system_info.FIN_SYSTEM],
        "name":        system_info.FIN_META_NAME_TEMPLATE.format(
            system=system_info.FIN_SYSTEM,
        ),
        "description": system_info.FIN_META_DESCRIPTION_TEMPLATE.format(
            system=system_info.FIN_SYSTEM,
        ),
        "module":      system_info.FIN_DEFAULT_MODULE,
        "priority":    system_info.FIN_DEFAULT_PRIORITY,
        "author":      system_info.FIN_DEFAULT_AUTHOR,
        "owner":       system_info.FIN_DEFAULT_OWNER,
        "tags":        list(system_info.FIN_DEFAULT_TAGS),
        "createTime":  system_info.FIN_CREATE_TIME_ANCHOR,
    }
    return common_meta_template(**{**fin_defaults, **overrides})


__all__ = ["fin_meta_template"]