"""gimbal_auth_headers/plugin.py

为每个 step 的 HTTP 请求自动注入轨迹查询接口认证头：

    token:     <md5(secret + timestamp)>
    timestamp: <unix-seconds>

"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Callable, Optional

from gimbal.core.hooks import HookPoint
from gimbal.core.plugin import Plugin, PluginContext, PluginManifest

logger = logging.getLogger(__name__)


# ── 默认配置常量 ──────────────────────────────────────────────

_DEFAULT_TIMESTAMP_FN: Callable[[], int] = lambda: int(time.time())


_HEADER_TOKEN = "token"
_HEADER_TIMESTAMP = "timestamp"


# ── 插件主类 ─────────────────────────────────────────────────

class AuthHeadersPlugin(Plugin):
    """为每个 step 的 HTTP 请求自动注入 Auth-Token / Timestamp / Signature。"""

    manifest = PluginManifest(
        name="gimbal-auth-headers",
        version="0.1.0",
        entry_point="gimbal_auth_headers.plugin:AuthHeadersPlugin",
        description=(
            "Auto-inject Auth-Token / Timestamp / Signature headers into "
            "every outgoing HTTP request using a token from AuthRegistry."
        ),
        capabilities=["generic"],
        default_config={
            "auth_tag": "",
        },
    )

    # 类级别 registry 引用 —— 兼容当前 framework 没有把 auth_registry
    # 放进 PluginContext 的现实：通过 set_auth_registry() 由外部
    # （bootstrap / 测试 / ScenarioRunner）显式注入。
    # 注意：这是 mutable class attribute，进程内全插件实例共享。
    # 设计取舍：
    #   - 用 class attribute 而不是 instance attribute：框架侧
    #     activate_all() 在调用 plugin.activate(ctx) 之前已经创建好
    #     AuthRegistry；用类属性可以让"框架侧在创建 plugin 后、
    #     activate 前"那一窗口期也能写入。
    #   - 如果同一进程跑多个 Gimbal run，每个 run 在 bootstrap 时
    #     都会重新生成 AuthRegistry；务必在 run 启动前写入。
    _shared_auth_registry: Optional[Any] = None

    def __init__(self) -> None:
        super().__init__()
        # 运行时配置（在 on_activate 里从 ctx.config 读取）
        self._auth_tag: str = ""
        self._timestamp_fn: Callable[[], int] = _DEFAULT_TIMESTAMP_FN
        self._auth_registry: Optional[Any] = None

        # 简单统计
        self._stats = {
            "injected": 0,
            "missing_token": 0,
            "missing_registry": 0,
            "missing_session": 0,
            "skipped_no_auth_tag": 0,
        }

    # ── 类方法：注入 auth_registry ──────────────────────

    @classmethod
    def set_auth_registry(cls, registry: Any) -> None:
        """在插件 activate 之前由外部（bootstrap / 测试 / ScenarioRunner）
        显式注入 AuthRegistry。

        用法：
            AuthHeadersPlugin.set_auth_registry(cfg.auth_registry)
            # 然后激活插件
        """
        cls._shared_auth_registry = registry
        logger.debug(
            "[AuthHeadersPlugin] auth_registry injected: id=%s",
            id(registry) if registry is not None else "None",
        )

    @classmethod
    def get_auth_registry(cls) -> Optional[Any]:
        """读取当前注入的 AuthRegistry（用于测试断言与诊断）。"""
        return cls._shared_auth_registry

    @classmethod
    def reset_auth_registry(cls) -> None:
        """清空注入的 AuthRegistry（用于测试隔离 / shutdown）。"""
        cls._shared_auth_registry = None

    # ── 生命周期 ──────────────────────────────────────────

    def on_activate(self, ctx: PluginContext) -> None:
        """读取配置 + 订阅 HTTP_BEFORE_SEND 钩子。"""
        cfg = ctx.config or {}

        # 1. auth_tag：必填（default_config 里给空字符串以表示"未配置"）
        auth_tag = cfg.get("auth_tag", "")
        if not isinstance(auth_tag, str):
            logger.warning(
                "[AuthHeadersPlugin] auth_tag must be str, got %r; fallback to ''",
                type(auth_tag).__name__,
            )
            auth_tag = ""
        auth_tag = str(auth_tag).strip()
        self._auth_tag = auth_tag

        # 2. timestamp_fn（可选；测试 / 调试场景用）
        ts_fn = cfg.get("timestamp_fn")
        if callable(ts_fn):
            self._timestamp_fn = ts_fn
        else:
            self._timestamp_fn = _DEFAULT_TIMESTAMP_FN

        self._auth_registry = getattr(ctx, "auth_registry", None)

        # 3. 订阅 HTTP_BEFORE_SEND：在每次 HTTP 调用发出前触发
        ctx.register_hook(
            HookPoint.HTTP_BEFORE_SEND,
            self._handle_http_before_send,
            description=(
                "Inject Auth-Token / Timestamp / Signature headers into "
                "the outgoing HTTP request using the configured auth_tag."
            ),
        )

        # 4. 订阅 framework.init：尝试从 payload 捕获 auth_registry
        #    （兼容未来 framework 把 auth_registry 放进 init payload 的场景；
        #    当前 framework.init payload 不含此字段，handler 仅在字段存在时生效。）
        ctx.register_event("framework.init", self._handle_framework_init)

        logger.info(
            "[AuthHeadersPlugin] activated: auth_tag=%r registry=%s",
            self._auth_tag,
            "set" if self._shared_auth_registry is not None else "unset",
        )

    def on_deactivate(self) -> None:
        """卸载时打印一次统计；不主动清空 _shared_auth_registry
        （清空由 framework shutdown 统一处理）。"""
        logger.info(
            "[AuthHeadersPlugin] deactivated: stats=%s", self._stats,
        )

    # ── 事件 / 钩子 ──────────────────────────────────────

    def _handle_framework_init(self, event: Any) -> None:
        """兼容路径：如果 framework.init 事件 payload 里出现 auth_registry，
        就把它当作 shared registry（优先级高于 set_auth_registry 注入的）。

        现实意义：未来若 framework 演进把 auth_registry 加入 init payload，
        本插件可零修改兼容。
        """
        try:
            registry = getattr(event, "auth_registry", None)
        except Exception:  # noqa: BLE001
            registry = None
        if registry is not None:
            type(self)._shared_auth_registry = registry
            logger.debug(
                "[AuthHeadersPlugin] captured auth_registry from framework.init payload",
            )

    def _handle_http_before_send(self, payload: Any) -> Any:
        """HTTP_BEFORE_SEND 钩子：从 AuthRegistry 取 token，注入三个 header。

        payload 字段（由 statemachine/engine.py 传入）：
            method, url, headers, body, timeout, step_id, ctx

        行为：
          1. 若 auth_tag 未配置 → 跳过（不抛错，让其它插件/手工 header 生效）
          2. 若 shared_auth_registry 缺失 → 计数 missing_registry，不抛错
          3. 若 auth_tag 在 registry 中不存在 → 计数 missing_session，不抛错
          4. 若 token 缺失（未登录 / 已过期）→ 计数 missing_token，不抛错
          5. 正常情况：mutate payload['headers'] in place，返回 payload
             以标记 modified（与 hooks.py 修复 #15 的约定一致）。
        """
        if not isinstance(payload, dict):
            return None

        if not self._auth_tag:
            self._stats["skipped_no_auth_tag"] += 1
            logger.debug(
                "[AuthHeadersPlugin] auth_tag 未配置，跳过 header 注入: step_id=%s",
                payload.get("step_id", "?"),
            )
            return None

        registry = self._auth_registry or type(self)._shared_auth_registry
        if registry is None:
            self._stats["missing_registry"] += 1
            logger.warning(
                "[AuthHeadersPlugin] auth_registry 未注入，请先调用 "
                "AuthHeadersPlugin.set_auth_registry(cfg.auth_registry): "
                "step_id=%s auth_tag=%r",
                payload.get("step_id", "?"), self._auth_tag,
            )
            return None

        # 1. 取 AuthSession；缺失则计数并跳过
        session = registry.get(self._auth_tag)
        if session is None:
            self._stats["missing_session"] += 1
            logger.warning(
                "[AuthHeadersPlugin] AuthSession[%r] 不在 registry 中: "
                "step_id=%s available_tags=%s",
                self._auth_tag,
                payload.get("step_id", "?"),
                list(registry.tags()) if hasattr(registry, "tags") else "?",
            )
            return None

        # 2. 通过 AuthManager 触发 lazy login/refresh —— 与框架现有代码兼容
        try:
            from gimbal.auth import AuthManager  # 局部 import 避免循环
            AuthManager(registry).get_auth(self._auth_tag)
        except Exception as exc:  # noqa: BLE001
            # AuthManager 失败 → 计数并跳过，不阻断主流程
            self._stats["missing_token"] += 1
            logger.warning(
                "[AuthHeadersPlugin] AuthManager.get_auth(%r) 失败: %s",
                self._auth_tag, exc,
            )
            return None

        # 3. 读取 token（apply_token 校验过控制字符，此处不再二次校验）
        token = getattr(session, "token", None)
        if not token:
            self._stats["missing_token"] += 1
            logger.warning(
                "[AuthHeadersPlugin] AuthSession[%r].token 为空（未登录?）: step_id=%s",
                self._auth_tag, payload.get("step_id", "?"),
            )
            return None

        # 4. 计算 timestamp + token 签名
        timestamp = int(self._timestamp_fn())
        signed_token = hashlib.md5(
            f"{token}{timestamp}".encode("utf-8"),
        ).hexdigest()

        # 5. 就地改写目标接口要求的 headers。
        headers = payload.get("headers")
        if not isinstance(headers, dict):
            headers = {}
            payload["headers"] = headers
        headers[_HEADER_TOKEN] = signed_token
        headers[_HEADER_TIMESTAMP] = str(timestamp)

        self._stats["injected"] += 1
        logger.debug(
            "[AuthHeadersPlugin] 注入认证头: step_id=%s url=%s ts=%s token=%s",
            payload.get("step_id", "?"),
            payload.get("url", "?"),
            timestamp,
            signed_token,
        )

        # 返回 payload 以标记 modified（与 hooks.py 修复 #15 约定一致）
        return payload

    # ── 调试用 ────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        """暴露当前统计，便于测试断言。"""
        return dict(self._stats)