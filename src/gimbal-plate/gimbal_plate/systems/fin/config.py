"""systems.fin.config —— fin 系统的 Config 默认模板工厂。

调用 ``common_config_template``。

- **services**: 从 ``gimbal_plate.systems.fin.system_info.FIN_SERVICES_URLS``
  读取(单一来源 = system_info);调用方可用 kwargs 切换到生产 URL。
- **users / vars**: 含占位符密码 / 业务占位变量,留在本模块本地定义
  (不属于"非敏感跨子模块共享"集合,故不入 ``system_info``)。

调用方可用 kwargs 进一步覆盖任意字段。
"""
from __future__ import annotations

from typing import Any

from gimbal_plate.schema import Config
from gimbal_plate.schema.auth import AuthSession

from gimbal_plate.systems.common.config import common_config_template
from gimbal_plate.systems.fin import system_info


def fin_config_template(**overrides: Any) -> Config:
    """构造 fin 系统的 Config 默认模板。

    - ``services`` 来自 ``system_info.FIN_SERVICES_URLS``(冻结测试 URL)。
    - ``users``     含 ``tester_a`` 占位符密码。
    - ``vars``      含 5 个 fin 业务占位变量。

    调用方可用 kwargs 覆盖任意字段(如切到生产 URL)。
    """
    fin_defaults: dict[str, Any] = {
        "services": dict(system_info.FIN_SERVICES_URLS),
        "users": {
            "tester_a": AuthSession(
                username="tester_a",
                password="${env.TEST_USER_A_PASSWORD}",
                domain="test",
            ),
        },
        "vars": {
            "fin_base_url": "https://test-api.example.com/fin",
            "fin_timeout_ms": 5000,
            "fin_default_currency": "CNY",
            "fin_bl_no_template": "GIMBAL728-XXXXXX",
            "fin_bank_id_count": 2,
        },
    }
    return common_config_template(**{**fin_defaults, **overrides})


__all__ = ["fin_config_template"]