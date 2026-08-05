"""systems.fin.meta —— fin 系统的 Meta 默认模板工厂。

调用 common_meta_template 注入 fin 专属默认:
    - system=["fin"]
    - module="fin"
    - author="fin-team"
    - owner="fin-team"
    - tags=["fin"]
    - name="fin-default-case"
    - description="fin 系统用例默认元信息模板"
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from gimbal_plate.schema import Meta

from gimbal_plate.systems.common.meta import common_meta_template


def fin_meta_template(**overrides: Any) -> Meta:
    """构造 fin 系统的 Meta 默认模板。

    在 common_meta_template 默认之上覆盖:
        - system=["fin"]
        - name="fin-default-case"
        - description="fin 系统用例默认元信息模板"
        - module="fin"
        - priority=1
        - author="fin-team"
        - owner="fin-team"
        - tags=["fin"]
        - createTime=2026-08-04 UTC(冻结锚点,便于测试 round-trip 一致性)

    调用方可用 kwargs 进一步覆盖(如改 author/owner 给特定 team)。
    """
    fin_defaults: dict[str, Any] = {
        "system": ["fin"],
        "name": "fin-default-case",
        "description": "fin 系统用例默认元信息模板",
        "module": "fin",
        "priority": 1,
        "author": "fin-team",
        "owner": "fin-team",
        "tags": ["fin"],
        "createTime": datetime(2026, 8, 4, 0, 0, 0, tzinfo=timezone.utc),
    }
    return common_meta_template(**{**fin_defaults, **overrides})


__all__ = ["fin_meta_template"]