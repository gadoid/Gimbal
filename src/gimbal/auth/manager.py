"""auth/manager.py

AuthManager - 统一认证入口。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..schema.auth import AuthSession
from .authenticator import get_authenticator
from .exceptions import AuthLoginFailed, AuthSessionNotFound

if TYPE_CHECKING:
    from ..config.models import BootstrapConfig

logger = logging.getLogger(__name__)


class AuthManager:
    """统一认证入口。

    使用流程：
        auth = AuthManager(config).get_auth("admin")
        if auth.is_authenticated:
            headers = {"Authorization": auth.auth_header}
    """

    def __init__(self, config: "BootstrapConfig"):
        """初始化 AuthManager。

        Args:
            config: BootstrapConfig，持有 users
        """
        self._config = config

    def get_auth(self, tag: str) -> AuthSession:
        """获取认证会话，自动处理登录/刷新。

        Args:
            tag: users 中的 key

        Returns:
            AuthSession，已登录状态

        Raises:
            AuthSessionNotFound: tag 不存在
        """
        auth = self._config.users.get(tag)
        if not auth:
            raise AuthSessionNotFound(f"Auth session '{tag}' not found in users")

        # 已认证且无需刷新
        if auth.is_authenticated and not auth.should_refresh:
            return auth

        # 未认证 → 登录
        if not auth.is_authenticated:
            logger.info("[AuthManager] 登录认证: tag=%s", tag)
            self._login(auth, tag)
            return auth

        # 需刷新
        if auth.should_refresh:
            logger.info("[AuthManager] 刷新 token: tag=%s", tag)
            self._refresh(auth, tag)
            return auth

        return auth

    def load_and_auth(self, tag: str, data: dict) -> AuthSession:
        """从字典加载并认证。

        Args:
            tag: 认证标识
            data: 配置字典，如 {"url": "...", "username": "...", "password": "..."}

        Returns:
            已认证的 AuthSession
        """
        # 1. dict → AuthSession
        auth = AuthSession(**data)

        # 2. 存入 config
        self._config.users[tag] = auth

        # 3. 认证
        if not auth.is_authenticated:
            self._login(auth, tag)

        return auth

    def _login(self, auth: AuthSession, tag: str) -> None:
        """执行登录（委托给认证器）。"""
        try:
            authenticator = get_authenticator(auth.url)
            authenticator.authenticate(auth, tag)
            logger.info("[AuthManager] 登录成功: tag=%s", tag)

        except Exception as e:
            logger.error("[AuthManager] 登录失败: tag=%s error=%s", tag, e)
            raise AuthLoginFailed(f"Login failed for '{tag}': {e}") from e

    def _refresh(self, auth: AuthSession, tag: str) -> None:
        """刷新 token。"""
        if not auth.url:
            # 无法刷新，重新登录
            self._login(auth, tag)
            return

        import httpx
        try:
            # 尝试调用 refresh 接口
            refresh_url = auth.url.rstrip("/") + "/refresh"
            response = httpx.post(
                refresh_url,
                json={"refresh_token": auth.token},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            token = data.get("access_token")
            expires_in = data.get("expires_in")
            auth.apply_token(token, expires_in)
            logger.info("[AuthManager] 刷新成功: tag=%s", tag)

        except Exception as e:
            # 刷新失败，尝试重新登录
            logger.warning("[AuthManager] 刷新失败，尝试重新登录: tag=%s error=%s", tag, e)
            self._login(auth, tag)
