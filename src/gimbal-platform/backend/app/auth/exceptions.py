"""auth/exceptions.py —— 认证相关异常定义。

物理迁移自 gimbal/auth/exceptions.py,与 gimbal 侧一致,
便于未来对比两套实现 / 抽取 gimbal-core。
"""
from __future__ import annotations


class AuthError(Exception):
    """认证相关错误的基类。"""


class AuthLoginFailed(AuthError):
    """登录失败(认证接口返回非 2xx / 响应不包含 token / 凭据错误)。"""


class AuthTokenExpired(AuthError):
    """Token 已过期且无法刷新。"""


class AuthSessionNotFound(AuthError):
    """按 tag 在 AuthRegistry 中找不到对应的 AuthSession。"""


__all__ = [
    "AuthError",
    "AuthLoginFailed",
    "AuthTokenExpired",
    "AuthSessionNotFound",
]