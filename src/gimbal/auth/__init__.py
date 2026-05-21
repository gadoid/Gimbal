"""auth 模块 - 认证管理。

提供统一的认证入口 AuthManager。
"""
from .manager import AuthManager
from .exceptions import (
    AuthError,
    AuthLoginFailed,
    AuthTokenExpired,
    AuthSessionNotFound,
)

__all__ = [
    "AuthManager",
    "AuthError",
    "AuthLoginFailed",
    "AuthTokenExpired",
    "AuthSessionNotFound",
]
