"""auth 模块 - 认证管理。

提供统一的认证入口 AuthManager 和可扩展的认证器体系。
"""
from .manager import AuthManager
from .authenticator import (
    Authenticator,
    register_authenticator,
    get_authenticator,
)
from .exceptions import (
    AuthError,
    AuthLoginFailed,
    AuthTokenExpired,
    AuthSessionNotFound,
)

# 导入内置认证器，触发 @register_authenticator 装饰器执行
from . import authenticators  # noqa: F401

__all__ = [
    "AuthManager",
    "Authenticator",
    "register_authenticator",
    "get_authenticator",
    "AuthError",
    "AuthLoginFailed",
    "AuthTokenExpired",
    "AuthSessionNotFound",
]
