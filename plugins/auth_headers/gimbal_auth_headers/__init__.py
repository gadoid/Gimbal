"""gimbal_auth_headers — 自动为每次 HTTP 请求注入认证头。

通过订阅 HTTP_BEFORE_SEND 钩子实现：
    Auth-Token: <token>
    Timestamp:  <ts>
    Signature:  md5(token + str(ts))
"""
from __future__ import annotations

from .plugin import AuthHeadersPlugin

__all__ = ["AuthHeadersPlugin"]