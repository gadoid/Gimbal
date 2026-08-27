"""auth_headers 插件测试。

分层覆盖：
  1. AuthHeadersPlugin 基本行为
     - 默认激活：跳过注入（auth_tag 为空）
     - 配置 auth_tag + 注入 registry 后：payload['headers'] 被就地改写
     - timestamp + md5(token+timestamp) 计算正确
     - 已存在的 header 保留，注入的 header 覆盖或并存
     - registry 不存在 / session 不存在 / token 缺失 → 不抛错，仅计数
  2. AuthRegistry 集成
     - 用真实的 AuthRegistry + AuthSession(token=...) 走通
  3. Hook + PluginContext 端到端
     - 走 PluginContext.register_hook + HookRegistry.trigger 完整链路
  4. 插件清单与导入
     - plugin.yaml 存在且可解析
     - 模块入口可被 PluginLoader 风格的导入链 import 出来
"""
from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

# 让 Python 找到 gimbal 包与本插件包
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "src"))
# 与 plugins/test_report 同样的导入约定：本插件 package 是
# plugins/auth_headers/gimbal_auth_headers/，故把 plugins/auth_headers 加到
# sys.path，使得 `gimbal_auth_headers` 可被 import。
sys.path.insert(0, str(_ROOT / "plugins" / "auth_headers"))

import pytest

from gimbal.auth.registry import AuthRegistry
from gimbal.core.hooks import HookPoint, HookRegistry
from gimbal.core.plugin import PluginContext
from gimbal.events import InMemoryEventBus
from gimbal.schema.auth import AuthSession

from gimbal_auth_headers.plugin import AuthHeadersPlugin


# ────────────────────────────────────────────────────────────────────
# 工具函数
# ────────────────────────────────────────────────────────────────────
def _make_ctx(bus, hook_registry: HookRegistry, config=None) -> PluginContext:
    """构造一个最小可用的 PluginContext 给测试用。"""
    return PluginContext(
        plugin_name="gimbal-auth-headers",
        config=config or {},
        event_bus=bus,
        hook_registry=hook_registry,
    )


def _make_payload(
    *,
    method: str = "GET",
    url: str = "https://api.example.com/users",
    headers: dict | None = None,
    body: dict | None = None,
    timeout: float = 30.0,
    step_id: str = "s1",
    ctx: object = None,
) -> dict:
    """构造 HTTP_BEFORE_SEND 的 payload（与 statemachine/engine.py 一致）。"""
    return {
        "method": method,
        "url": url,
        "headers": dict(headers) if headers is not None else {},
        "body": body if body is not None else {},
        "timeout": timeout,
        "step_id": step_id,
        "ctx": ctx,
    }


def _expected_signature(token: str, timestamp: int) -> str:
    """计算预期的 md5(token+str(timestamp))。"""
    return hashlib.md5(f"{token}{timestamp}".encode("utf-8")).hexdigest()


def _make_session_with_token(token: str | None = "tok-abc-123") -> AuthSession:
    """构造一个已"登录"的 AuthSession（apply_token 写入 token + expires_at）。"""
    s = AuthSession()
    if token:
        s.apply_token(token, expires_in=3600)
    return s


@pytest.fixture(autouse=True)
def _isolate_shared_registry():
    """每个用例前后清理 class-level shared_auth_registry，避免跨例污染。"""
    AuthHeadersPlugin.reset_auth_registry()
    yield
    AuthHeadersPlugin.reset_auth_registry()




def test_plugin_uses_auth_registry_from_context():
    reg = AuthRegistry()
    token = "ctx-token-123"
    reg.set("admin", _make_session_with_token(token))

    bus = InMemoryEventBus()
    hook_reg = HookRegistry()
    plugin = AuthHeadersPlugin()
    plugin.load()
    plugin.activate(_make_ctx(bus, hook_reg, config={"auth_tag": "admin"}))
    plugin.ctx.auth_registry = reg
    plugin._auth_registry = reg
    plugin._timestamp_fn = lambda: 1700000000

    payload = _make_payload()
    plugin._handle_http_before_send(payload)

    assert payload["headers"]["token"] == _expected_signature(token, 1700000000)
    assert payload["headers"]["timestamp"] == "1700000000"
    plugin.deactivate()


    def test_no_auth_tag_means_skip(self):
        """未配置 auth_tag 时：handler 不改写 headers，仅递增 skipped 计数。"""
        # 准备一个看起来就绪的 registry，但 auth_tag 为空 → 仍应跳过
        reg = AuthRegistry()
        reg.set("admin", _make_session_with_token("secret-token"))
        AuthHeadersPlugin.set_auth_registry(reg)

        bus = InMemoryEventBus()
        hook_reg = HookRegistry()
        plugin = AuthHeadersPlugin()
        plugin.load()
        plugin.activate(_make_ctx(bus, hook_reg, config={"auth_tag": ""}))

        payload = _make_payload(headers={"X-Existing": "v"})
        result = plugin._handle_http_before_send(payload)

        # 未改写
        assert result is None
        assert payload["headers"] == {"X-Existing": "v"}
        # 计数
        assert plugin.stats["skipped_no_auth_tag"] == 1
        assert plugin.stats["injected"] == 0

        plugin.deactivate()


# ────────────────────────────────────────────────────────────────────
# 2) 注入与 mutation
# ────────────────────────────────────────────────────────────────────
class TestHeaderInjection:
    def test_injects_three_headers_into_existing_dict(self):
        """正常路径：payload['headers'] 已存在 dict 时就地改写，保留其它 header。"""
        reg = AuthRegistry()
        token = "tok-fixed-xyz"
        reg.set("admin", _make_session_with_token(token))
        AuthHeadersPlugin.set_auth_registry(reg)

        bus = InMemoryEventBus()
        hook_reg = HookRegistry()
        plugin = AuthHeadersPlugin()
        plugin.load()
        plugin.activate(_make_ctx(bus, hook_reg, config={"auth_tag": "admin"}))

        payload = _make_payload(
            headers={"Accept": "application/json", "X-Trace": "abc"},
            url="https://api.example.com/users",
            step_id="step-1",
        )
        # 固定时间 → 固定 signature，便于断言
        plugin._timestamp_fn = lambda: 1700000000

        result = plugin._handle_http_before_send(payload)

        assert result is payload, "handler 应返回 payload 以标记 modified"
        h = payload["headers"]
        # 三个新 header
        assert h["token"] == _expected_signature(token, 1700000000)
        assert h["timestamp"] == "1700000000"
        assert "Auth-Token" not in h
        assert "Signature" not in h
        # 既有 header 保留
        assert h["Accept"] == "application/json"
        assert h["X-Trace"] == "abc"
        # 计数
        assert plugin.stats["injected"] == 1
        assert plugin.stats["missing_token"] == 0

        plugin.deactivate()

    def test_injects_when_headers_is_none(self):
        """防御性：payload['headers'] 缺失或不是 dict 时构造一个新 dict。"""
        reg = AuthRegistry()
        token = "tok-None-headers"
        reg.set("admin", _make_session_with_token(token))
        AuthHeadersPlugin.set_auth_registry(reg)

        bus = InMemoryEventBus()
        hook_reg = HookRegistry()
        plugin = AuthHeadersPlugin()
        plugin.load()
        plugin.activate(_make_ctx(bus, hook_reg, config={"auth_tag": "admin"}))
        plugin._timestamp_fn = lambda: 42

        payload = _make_payload()
        # 故意改成 None（engine 实际不会这样，但我们要 plugin 防御住）
        payload["headers"] = None
        plugin._handle_http_before_send(payload)

        assert isinstance(payload["headers"], dict)
        assert payload["headers"]["token"] == _expected_signature(token, 42)
        assert payload["headers"]["timestamp"] == "42"
        assert "Auth-Token" not in payload["headers"]
        assert "Signature" not in payload["headers"]

        plugin.deactivate()

    def test_signature_is_md5_hex_of_token_plus_timestamp_str(self):
        """明确锁定 signature 算法：md5(hex) = md5((token + str(ts)).encode()).hexdigest()。"""
        reg = AuthRegistry()
        token = "T-9"
        reg.set("admin", _make_session_with_token(token))
        AuthHeadersPlugin.set_auth_registry(reg)

        bus = InMemoryEventBus()
        hook_reg = HookRegistry()
        plugin = AuthHeadersPlugin()
        plugin.load()
        plugin.activate(_make_ctx(bus, hook_reg, config={"auth_tag": "admin"}))

        for ts in (1, 1700000000, 2**31):
            plugin._timestamp_fn = lambda v=ts: v
            payload = _make_payload()
            plugin._handle_http_before_send(payload)
            expected = hashlib.md5(f"{token}{ts}".encode("utf-8")).hexdigest()
            assert payload["headers"]["token"] == expected
            assert payload["headers"]["timestamp"] == str(ts)

        plugin.deactivate()

    def test_timestamp_default_uses_int_time_time(self, monkeypatch):
        """默认 timestamp_fn 等价 int(time.time())，且每次请求重新读取。"""
        reg = AuthRegistry()
        reg.set("admin", _make_session_with_token("t"))
        AuthHeadersPlugin.set_auth_registry(reg)

        # 用 monkeypatch 锁住 time.time 的两次返回值
        times = iter([1_700_000_000.4, 1_700_000_001.9])
        monkeypatch.setattr(time, "time", lambda: next(times))

        bus = InMemoryEventBus()
        hook_reg = HookRegistry()
        plugin = AuthHeadersPlugin()
        plugin.load()
        plugin.activate(_make_ctx(bus, hook_reg, config={"auth_tag": "admin"}))
        # 不要覆盖 _timestamp_fn

        p1 = _make_payload(step_id="s1")
        plugin._handle_http_before_send(p1)
        p2 = _make_payload(step_id="s2")
        plugin._handle_http_before_send(p2)

        assert p1["headers"]["timestamp"] == "1700000000"
        assert p2["headers"]["timestamp"] == "1700000001"

        plugin.deactivate()


# ────────────────────────────────────────────────────────────────────
# 3) 错误路径：优雅降级
# ────────────────────────────────────────────────────────────────────
class TestGracefulDegradation:
    def test_missing_registry_logs_warning_does_not_raise(self):
        """未注入 auth_registry：handler 静默跳过，仅递增计数。"""
        # 注意：autouse fixture 已经 reset
        bus = InMemoryEventBus()
        hook_reg = HookRegistry()
        plugin = AuthHeadersPlugin()
        plugin.load()
        plugin.activate(_make_ctx(bus, hook_reg, config={"auth_tag": "admin"}))

        payload = _make_payload(headers={"Accept": "application/json"})
        result = plugin._handle_http_before_send(payload)

        assert result is None
        # 原始 headers 未被修改
        assert payload["headers"] == {"Accept": "application/json"}
        assert plugin.stats["missing_registry"] == 1
        assert plugin.stats["injected"] == 0

        plugin.deactivate()

    def test_missing_session_logs_warning_does_not_raise(self):
        """registry 中无该 auth_tag：handler 静默跳过。"""
        reg = AuthRegistry()
        # 注册其它 tag，但 NOT admin
        reg.set("guest", _make_session_with_token("g-tok"))
        AuthHeadersPlugin.set_auth_registry(reg)

        bus = InMemoryEventBus()
        hook_reg = HookRegistry()
        plugin = AuthHeadersPlugin()
        plugin.load()
        plugin.activate(_make_ctx(bus, hook_reg, config={"auth_tag": "admin"}))

        payload = _make_payload()
        result = plugin._handle_http_before_send(payload)

        assert result is None
        assert payload["headers"] == {}
        assert plugin.stats["missing_session"] == 1
        assert plugin.stats["injected"] == 0

        plugin.deactivate()

    def test_missing_token_logs_warning_does_not_raise(self):
        """AuthSession 存在但 token 为空（未登录）：handler 静默跳过。"""
        reg = AuthRegistry()
        reg.set("admin", _make_session_with_token(None))   # token=None
        AuthHeadersPlugin.set_auth_registry(reg)

        bus = InMemoryEventBus()
        hook_reg = HookRegistry()
        plugin = AuthHeadersPlugin()
        plugin.load()
        plugin.activate(_make_ctx(bus, hook_reg, config={"auth_tag": "admin"}))

        payload = _make_payload()
        result = plugin._handle_http_before_send(payload)

        assert result is None
        assert payload["headers"] == {}
        assert plugin.stats["missing_token"] == 1
        assert plugin.stats["injected"] == 0

        plugin.deactivate()

    def test_payload_not_dict_is_ignored(self):
        """防御性：payload 不是 dict 时 handler 直接 return。"""
        reg = AuthRegistry()
        reg.set("admin", _make_session_with_token("t"))
        AuthHeadersPlugin.set_auth_registry(reg)

        bus = InMemoryEventBus()
        hook_reg = HookRegistry()
        plugin = AuthHeadersPlugin()
        plugin.load()
        plugin.activate(_make_ctx(bus, hook_reg, config={"auth_tag": "admin"}))

        # 不应抛错
        assert plugin._handle_http_before_send("not-a-dict") is None
        assert plugin._handle_http_before_send(None) is None
        assert plugin._handle_http_before_send(12345) is None
        # 计数应清零（这三种都不计入任何 bucket）
        assert plugin.stats["injected"] == 0
        assert plugin.stats["missing_registry"] == 0
        assert plugin.stats["missing_token"] == 0
        assert plugin.stats["missing_session"] == 0

        plugin.deactivate()


# ────────────────────────────────────────────────────────────────────
# 4) 端到端：HookRegistry.trigger 走完整链路
# ────────────────────────────────────────────────────────────────────
class TestEndToEndViaHookRegistry:
    def test_trigger_marks_modified_and_injects_headers(self):
        """PluginContext.register_hook → HookRegistry.trigger → payload 被改写。"""
        reg = AuthRegistry()
        token = "end-to-end-token"
        reg.set("admin", _make_session_with_token(token))
        AuthHeadersPlugin.set_auth_registry(reg)

        bus = InMemoryEventBus()
        hook_reg = HookRegistry()
        plugin = AuthHeadersPlugin()
        plugin.load()
        plugin.activate(_make_ctx(bus, hook_reg, config={"auth_tag": "admin"}))
        plugin._timestamp_fn = lambda: 1234567890

        payload = _make_payload(url="https://api.example.com/orders")
        result = hook_reg.trigger(HookPoint.HTTP_BEFORE_SEND, payload)

        # 未中断、未抛错
        assert result.stopped is False
        assert result.errors == []
        # modified=True（因为 handler 返回了 payload）
        assert result.modified is True
        # headers 被改写
        h = payload["headers"]
        assert h["token"] == _expected_signature(token, 1234567890)
        assert h["timestamp"] == "1234567890"

        plugin.deactivate()


# ────────────────────────────────────────────────────────────────────
# 5) Manifest / import
# ────────────────────────────────────────────────────────────────────
class TestManifest:
    def test_plugin_yaml_exists_and_parses(self):
        yaml_path = _ROOT / "plugins" / "auth_headers" / "plugin.yaml"
        assert yaml_path.exists(), f"missing manifest at {yaml_path}"
        # 用 framework 自带的 yaml 解析（pyyaml 已声明为依赖）
        import yaml
        with yaml_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["name"] == "gimbal-auth-headers"
        assert data["entry_point"] == "gimbal_auth_headers.plugin:AuthHeadersPlugin"
        assert "auth_tag" in data["default_config"]
        assert data["default_config"]["auth_tag"] == ""

    def test_class_metadata_matches_manifest(self):
        plugin = AuthHeadersPlugin()
        m = plugin.manifest
        assert m.name == "gimbal-auth-headers"
        assert m.entry_point == "gimbal_auth_headers.plugin:AuthHeadersPlugin"
        assert "generic" in m.capabilities
        assert m.default_config.get("auth_tag") == ""