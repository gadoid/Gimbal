"""auth/exceptions.py

认证相关异常定义。
"""


class AuthError(Exception):
    """认证异常基类。"""
    pass


class AuthLoginFailed(AuthError):
    """登录失败。"""
    pass


class AuthTokenExpired(AuthError):
    """Token 已过期或无效。"""
    pass


class AuthSessionNotFound(AuthError):
    """AuthSession 未找到。"""
    pass
