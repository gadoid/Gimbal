"""认证器模块 - URL 路由式认证

使用装饰器注册不同 URL 对应的认证器。

用法:
    @register_authenticator("https://api.github.com/")
    class GitHubAuthenticator(Authenticator):
        def authenticate(self, auth, tag):
            ...

    # 使用
    auth = get_authenticator("https://api.github.com/")
    auth.authenticate(session, "github_user")

内置认证器位于 authenticators/ 目录，导入即可自动注册。
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..schema.auth import AuthSession

# ── 注册表 ────────────────────────────────────────────────
_AUTHENTICATOR_REGISTRY: dict[str, type] = {}

def register_authenticator(url_pattern: str):
    """装饰器：注册 URL pattern -> 认证器类。

    用法:
        @register_authenticator("https://api.github.com/")
        class GitHubAuthenticator(Authenticator):
            ...

    注册表会按 URL pattern 存储，支持精确匹配和前缀匹配。
    """
    def deco(cls: type["Authenticator"]) -> type["Authenticator"]:
        _AUTHENTICATOR_REGISTRY[url_pattern] = cls
        return cls
    return deco


# ── 抽象接口 ────────────────────────────────────────────────
class Authenticator(ABC):
    """认证策略抽象接口"""

    @abstractmethod
    def authenticate(self, auth: "AuthSession", tag: str) -> None:
        """执行认证，成功则调用 auth.apply_token() 填充 token。

        Args:
            auth: AuthSession 对象
            tag: 认证标识（用于日志）

        Raises:
            AuthLoginFailed: 认证失败时抛出
        """
        raise NotImplementedError


# ── 路由函数 ────────────────────────────────────────────────

def get_authenticator(url: str) -> Authenticator:
    """根据 URL 获取对应的认证器。

    匹配顺序：
        1. 精确匹配
        2. URL 前缀匹配（注册时使用 URL 前缀）

    Returns:
        匹配的认证器实例

    Raises:
        AuthError: 未找到匹配的认证器
    """
    if not url:
        # 无 URL 使用预置 Token
        from .authenticators.pretoken import PreTokenAuthenticator
        return PreTokenAuthenticator()

    # 精确匹配
    cls = _AUTHENTICATOR_REGISTRY.get(url)
    if cls:
        return cls()

    # 前缀匹配
    for pattern, authenticator_cls in _AUTHENTICATOR_REGISTRY.items():
        if pattern and url.startswith(pattern):
            return authenticator_cls()

    # 默认使用 HTTPS 认证器
    from .authenticators.http_basic import HTTPSAuthenticator
    return HTTPSAuthenticator()
