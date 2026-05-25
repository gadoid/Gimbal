"""test_resolver.py

验证 SpecResolver 的核心解析逻辑，不依赖完整框架。
用 mock 替代 view 和 config，专注测试解析规则本身。
"""
from __future__ import annotations

import sys
sys.path.insert(0, "/home/claude")

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock


# ── 最小化 mock，不依赖框架 ────────────────────────────────────────────────────

@dataclass
class MockAuthSession:
    """模拟 AuthSession，包含 @property。"""
    token: str = "eyJxx_test_token"
    token_type: str = "Bearer"

    @property
    def auth_header(self) -> str:
        return f"{self.token_type} {self.token}"


@dataclass
class MockConfig:
    users_pool: dict = field(default_factory=dict)
    services_pool: dict = field(default_factory=dict)


class MockView:
    """模拟 StepContextAdapter，持有 channels 变量。"""
    def __init__(self, channels_vars: dict):
        # 模拟 view._ctx.parent.channels.variables_snapshot()
        self._ctx = MagicMock()
        self._ctx.parent.channels.variables_snapshot.return_value = channels_vars


# ── 内联最小化 JSONPath（支持 getattr），不依赖框架文件 ──────────────────────

def _get(data: Any, path: str, default: Any = None) -> Any:
    """简化版 JSONPath get，支持 dict + getattr。"""
    if not path.startswith("$"):
        return default
    parts = path.lstrip("$.").split(".")
    current = data
    for part in parts:
        if current is None:
            return default
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return default
    return current if current is not None else default


def _is_template(value: Any) -> bool:
    import re
    return isinstance(value, str) and bool(re.search(r"\$\{[^}]+\}", value))


def _resolve_template(template: str, root: dict) -> Any:
    import re
    pattern = re.compile(r"\$\{([^}]+)\}")

    # 整体是单个变量 → 保留原始类型
    m = pattern.fullmatch(template.strip())
    if m:
        ref = m.group(1).strip()
        return _get(root, f"$.{ref}")

    # 嵌入式 → 字符串拼接
    def replacer(match):
        ref = match.group(1).strip()
        val = _get(root, f"$.{ref}")
        return str(val) if val is not None else match.group(0)

    return pattern.sub(replacer, template)


# ── 内联 SpecResolver 核心逻辑（验证算法，不依赖 schema import）──────────────

class MiniSpecResolver:
    """提取 SpecResolver 的核心解析算法进行验证。"""

    def __init__(self, view: MockView, config: MockConfig):
        self._root = self._build_root(view, config)

    def _build_root(self, view, config) -> dict:
        root = {}
        channels_vars = view._ctx.parent.channels.variables_snapshot()
        root.update(channels_vars)
        if config.services_pool:
            root["service"] = config.services_pool
        if config.users_pool:
            root["auth"] = config.users_pool
        return root

    def resolve_value(self, value: Any) -> Any:
        if not isinstance(value, str) or not _is_template(value):
            return value
        return _resolve_template(value, self._root)

    def resolve_dict(self, data: dict) -> dict:
        return {k: self._resolve_nested(v) for k, v in data.items()}

    def _resolve_nested(self, value: Any) -> Any:
        if isinstance(value, dict):
            return self.resolve_dict(value)
        if isinstance(value, list):
            return [self._resolve_nested(item) for item in value]
        return self.resolve_value(value)


# ── 测试用例 ──────────────────────────────────────────────────────────────────

def test_channels_simple_var():
    """channels 里的变量，直接读取。"""
    view = MockView({"token": "eyJxx", "user_id": 42})
    config = MockConfig()
    resolver = MiniSpecResolver(view, config)

    assert resolver.resolve_value("${token}") == "eyJxx"
    assert resolver.resolve_value("${user_id}") == 42      # 保留 int 类型
    print("✓ channels 简单变量读取")


def test_channels_embedded_template():
    """嵌入式模板，字符串拼接。"""
    view = MockView({"settlement_id": "S-001"})
    config = MockConfig()
    resolver = MiniSpecResolver(view, config)

    result = resolver.resolve_value("/settlement/${settlement_id}/detail")
    assert result == "/settlement/S-001/detail"
    print("✓ 嵌入式模板字符串拼接")


def test_auth_property_navigation():
    """auth.admin.auth_header，导航到 @property。"""
    admin_session = MockAuthSession(token="real_token", token_type="Bearer")
    view = MockView({})
    config = MockConfig(users_pool={"admin": admin_session})
    resolver = MiniSpecResolver(view, config)

    result = resolver.resolve_value("${auth.admin.auth_header}")
    assert result == "Bearer real_token"
    print("✓ auth @property 导航")


def test_auth_in_header():
    """认证头嵌入模板。"""
    admin_session = MockAuthSession(token="real_token")
    view = MockView({})
    config = MockConfig(users_pool={"admin": admin_session})
    resolver = MiniSpecResolver(view, config)

    result = resolver.resolve_value("${auth.admin.auth_header}")
    assert result == "Bearer real_token"
    print("✓ 认证头嵌入模板")


def test_service_pool_navigation():
    """service 命名空间，导航到 services_pool。"""
    view = MockView({})
    config = MockConfig(services_pool={
        "settlement-service": "https://api.example.com"
    })
    resolver = MiniSpecResolver(view, config)

    result = resolver.resolve_value("${service.settlement-service}")
    assert result == "https://api.example.com"
    print("✓ service 命名空间导航")


def test_no_template_passthrough():
    """无模板的值原样透传。"""
    view = MockView({})
    config = MockConfig()
    resolver = MiniSpecResolver(view, config)

    assert resolver.resolve_value("response_status") == "response_status"
    assert resolver.resolve_value(200) == 200
    assert resolver.resolve_value(None) is None
    assert resolver.resolve_value({"key": "val"}) == {"key": "val"}
    print("✓ 无模板值透传")


def test_missing_var_returns_none():
    """变量不存在返回 None。"""
    view = MockView({})
    config = MockConfig()
    resolver = MiniSpecResolver(view, config)

    result = resolver.resolve_value("${nonexistent}")
    assert result is None
    print("✓ 缺失变量返回 None")


def test_missing_embedded_var_keeps_original():
    """嵌入式模板变量不存在时保留原始占位符。"""
    view = MockView({})
    config = MockConfig()
    resolver = MiniSpecResolver(view, config)

    result = resolver.resolve_value("/path/${missing_id}/detail")
    assert result == "/path/${missing_id}/detail"
    print("✓ 嵌入式缺失变量保留原始占位符")


def test_priority_channels_over_nothing():
    """channels 变量优先于未定义。"""
    view = MockView({"token": "from_channels"})
    config = MockConfig()
    resolver = MiniSpecResolver(view, config)

    assert resolver.resolve_value("${token}") == "from_channels"
    print("✓ channels 变量优先级")


def test_dict_recursive_resolve():
    """dict 递归解析。"""
    view = MockView({"user_id": 99, "order_id": "ORD-001"})
    config = MockConfig()
    resolver = MiniSpecResolver(view, config)

    body = {
        "userId": "${user_id}",
        "orderId": "${order_id}",
        "nested": {
            "flag": True,
            "ref": "${user_id}",
        },
        "items": ["${order_id}", "static"],
    }
    result = resolver.resolve_dict(body)
    assert result["userId"] == 99
    assert result["orderId"] == "ORD-001"
    assert result["nested"]["ref"] == 99
    assert result["items"][0] == "ORD-001"
    assert result["items"][1] == "static"
    print("✓ dict 递归解析")


def test_type_preservation():
    """整体变量替换保留原始类型。"""
    view = MockView({
        "count": 5,
        "flag": True,
        "config": {"k": "v"},
    })
    config = MockConfig()
    resolver = MiniSpecResolver(view, config)

    assert resolver.resolve_value("${count}") == 5
    assert isinstance(resolver.resolve_value("${count}"), int)
    assert resolver.resolve_value("${flag}") is True
    assert resolver.resolve_value("${config}") == {"k": "v"}
    print("✓ 原始类型保留")


# ── 运行 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_channels_simple_var,
        test_channels_embedded_template,
        test_auth_property_navigation,
        test_auth_in_header,
        test_service_pool_navigation,
        test_no_template_passthrough,
        test_missing_var_returns_none,
        test_missing_embedded_var_keeps_original,
        test_priority_channels_over_nothing,
        test_dict_recursive_resolve,
        test_type_preservation,
    ]

    print(f"\n{'─' * 50}")
    print("SpecResolver 核心逻辑验证")
    print(f"{'─' * 50}")

    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    print(f"{'─' * 50}")
    print(f"结果：{passed} 通过 / {failed} 失败")
    print(f"{'─' * 50}\n")