"""auth/manager.py

AuthManager - 统一认证入口。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..schema.auth import AuthSession
from .authenticator import get_authenticator
from .exceptions import AuthLoginFailed, AuthSessionNotFound

if TYPE_CHECKING:
    from .registry import AuthRegistry

from gimbal.log import get_logger
logger = get_logger(__name__)


class AuthManager:
    """统一认证入口。

    使用流程：
        auth = AuthManager(registry).get_auth("admin")
        if auth.is_authenticated:
            headers = {"Authorization": auth.auth_header}
    """

    def __init__(self, registry: "AuthRegistry") -> None:
        """初始化 AuthManager。

        Args:
            registry: AuthRegistry 实例（运行期 token 状态容器）

        Raises:
            TypeError: registry 不是 AuthRegistry 实例
        """
        from gimbal.auth.registry import AuthRegistry  # 局部 import 避免循环
        # 修复 #2：用 isinstance 替代脆弱的 hasattr 双检查：
        # 之前使用 hasattr 探测属性会同时误判 duck-typed 代理对象，
        # 改用 isinstance 后仅接受真正的 AuthRegistry 类型，避免静默错误。
        if not isinstance(registry, AuthRegistry):
            raise TypeError(
                f"AuthManager requires AuthRegistry instance, got {type(registry).__name__}. "
                "If you have a Configuration, pass configuration.auth_registry instead."
            )
        self._registry = registry

    def get_auth(self, tag: str) -> AuthSession:
        """获取已认证的 AuthSession，必要时自动登录或刷新 token。

        处理流程：先从 registry 取出 session；若不存在则抛 AuthSessionNotFound；
        若已认证且未到刷新时机则直接返回；未认证则走登录路径；需刷新则走刷新路径。

        Args:
            tag: registry 中的 key

        Returns:
            AuthSession，已登录状态

        Raises:
            AuthSessionNotFound: tag 不存在
        """
        auth = self._registry.get(tag)
        if not auth:
            raise AuthSessionNotFound(f"Auth session '{tag}' not found in registry")

        # 已认证且无需刷新
        if auth.is_authenticated and not auth.should_refresh:
            return auth

        # 未认证 → 登录
        if not auth.is_authenticated:
            logger.info("[AuthManager] 登录认证: tag={}", tag)
            self._login(auth, tag)
            return auth

        # 需刷新
        if auth.should_refresh:
            logger.info("[AuthManager] 刷新 token: tag={}", tag)
            self._refresh(auth, tag)
            return auth

        return auth

    def load_and_auth(self, tag: str, data: dict) -> AuthSession:
        """从配置字典构造 AuthSession、写入 registry，并在未认证时自动登录。

        Args:
            tag: 认证标识（registry key）
            data: 配置字典，如 {"url": "...", "username": "...", "password": "..."}

        Returns:
            已认证的 AuthSession
        """
        # 1. dict → AuthSession
        auth = AuthSession(**data)

        # 2. 存入 registry
        self._registry.set(tag, auth)

        # 3. 认证
        if not auth.is_authenticated:
            self._login(auth, tag)

        return auth

    def _login(self, auth: AuthSession, tag: str) -> None:
        """根据 auth.url 选择已注册的 Authenticator 并调用其 authenticate 完成登录；失败统一抛出 AuthLoginFailed。"""
        try:
            print(auth.url)
            authenticator = get_authenticator(auth.url)
            print(authenticator)
            authenticator.authenticate(auth, tag)
            logger.info("[AuthManager] 登录成功: tag={}", tag)

        except Exception as e:
            logger.error("[AuthManager] 登录失败: tag={} error={}", tag, e)
            raise AuthLoginFailed(f"Login failed for '{tag}': {e}") from e

    def _refresh(self, auth: AuthSession, tag: str) -> None:
        """使用 refresh_token 调远程 refresh 端点续期；缺 refresh_token 或调用失败时回退到全量重新登录。

        PreToken 模式（无 url）下不做任何事：token 是 password 的镜像，
        重新"登录"只是再 apply_token(password)，无意义且会形成循环。
        """
        if not auth.url:
            # PreToken 模式：token == password，没有可刷新的远程端点
            logger.debug("[AuthManager] PreToken 模式跳过 refresh: tag={}", tag)
            return

        import httpx
        # 修复 #10：refresh_token 缺失时直接全量重登录，
        # 不要把 access_token 塞进 refresh_token 字段。
        # OAuth2 spec 要求两者独立；严格服务商（Auth0/Okta 等）会拒收 access_token。
        if not auth.refresh_token:
            logger.info(
                "[AuthManager] 无 refresh_token，跳过 refresh，全量重登录: tag={}", tag,
            )
            self._login(auth, tag)
            return

        try:
            # 尝试调用 refresh 接口
            refresh_url = auth.url.rstrip("/") + "/refresh"
            response = httpx.post(
                refresh_url,
                json={"refresh_token": auth.refresh_token},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            token = data.get("access_token")
            expires_in = data.get("expires_in")
            # 修复 #10：从 refresh 响应中保存新的 refresh_token（服务商可能轮换）
            new_refresh = data.get("refresh_token")
            if new_refresh:
                auth.refresh_token = new_refresh
            auth.apply_token(token, expires_in)
            logger.info("[AuthManager] 刷新成功: tag={}", tag)

        except Exception as e:
            # 刷新失败，尝试重新登录
            logger.warning("[AuthManager] 刷新失败，尝试重新登录: tag={} error={}", tag, e)
            self._login(auth, tag)
