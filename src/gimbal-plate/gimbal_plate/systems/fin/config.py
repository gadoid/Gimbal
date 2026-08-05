"""systems.fin.config —— fin 系统的 Config 默认模板工厂。

调用 common_config_template 注入 fin 专属默认:
    - services:7 个服务域名映射(settlement / account / order_entrust /
      order / order_fee / audit 等)
    - users:tester_a(密码用占位符引用,不放生产敏感信息)
    - vars:fin 业务占位变量(URL / timeout / 业务单号模板等)
"""
from __future__ import annotations

from typing import Any

from gimbal_plate.schema import Config
from gimbal_plate.schema.auth import AuthSession

from gimbal_plate.systems.common.config import common_config_template


def fin_config_template(**overrides: Any) -> Config:
    """构造 fin 系统的 Config 默认模板。

    在 common_config_template 默认之上覆盖:
        - services: 7 个服务的测试 URL
        - users: tester_a(密码用 ${env.TEST_USER_A_PASSWORD} 占位符)
        - vars: 5 个 fin 业务占位变量

    调用方可用 kwargs 进一步覆盖(如切换到生产 URL)。
    """
    fin_defaults: dict[str, Any] = {
        "services": {
            "settlement": "https://test-api.example.com/fin/settlement",
            "account": "https://test-api.example.com/fin/account",
            "order_entrust": "https://test-api.example.com/fin/order-entrust",
            "order": "https://test-api.example.com/fin/order",
            "order_fee": "https://test-api.example.com/fin/order-fee",
            "audit": "https://test-api.example.com/fin/audit",
        },
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