"""fin 系统的 Meta / Config 默认模板。

按 V3 PLATE_V3_DESIGN.md §3 第三条:defaults.py 提供该系统的 Meta / Config
默认模板,供 platform 处理该系统用例时直接取用作为基础默认配置;services /
users 按填充规则给出,不放生产敏感信息。

services / users 直接使用 Config 已有的 services / users 字段(不另起 dict),
保持与 gimbal 运行时一致。
"""
from __future__ import annotations

from datetime import datetime, timezone

from gimbal_plate.schema.base.auth import AuthSession
from gimbal_plate.schema.interface import Config, Meta

# ── Meta 默认模板 ──────────────────────────────────────────────

META_TEMPLATE = Meta(
    system="fin",
    name="fin-default-case",
    description="fin 系统用例默认元信息模板",
    module="fin",
    priority=1,
    author="fin-team",
    owner="fin-team",
    tags=["fin"],
    version="1.0.0",
    createTime=datetime(2026, 8, 4, 0, 0, 0, tzinfo=timezone.utc),
    expire=False,
    requirementRef=[],
)

# ── Config 默认模板 ──────────────────────────────────────────────

CONFIG_TEMPLATE = Config(
    services={
        "settlement": "https://test-api.example.com/fin/settlement",
        "account": "https://test-api.example.com/fin/account",
        # Scenario_Test_14 提取的 4 个新服务,与 endpoint 文件中 service 字段一一对应。
        "order_entrust": "https://test-api.example.com/fin/order-entrust",
        "order": "https://test-api.example.com/fin/order",
        "order_fee": "https://test-api.example.com/fin/order-fee",
        "audit": "https://test-api.example.com/fin/audit",
    },
    users={
        # 测试环境通用账号,密码用占位符引用,不放生产敏感信息。
        "tester_a": AuthSession(
            username="tester_a",
            password="${env.TEST_USER_A_PASSWORD}",
            domain="test",
        ),
    },
    vars={
        "fin_base_url": "https://test-api.example.com/fin",
        "fin_timeout_ms": 5000,
        "fin_default_currency": "CNY",
        # 与 Scenario_Test_14 元数据对齐的额外占位变量。
        "fin_bl_no_template": "GIMBAL728-XXXXXX",
        "fin_bank_id_count": 2,
    },
)

__all__ = ["META_TEMPLATE", "CONFIG_TEMPLATE"]
