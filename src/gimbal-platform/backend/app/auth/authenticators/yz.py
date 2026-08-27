"""YZAuthenticator —— track-test.21eline.com 专用认证器。

物理迁移自 gimbal/auth/authenticators/yz.py。
"""
from ..authenticator import Authenticator, register_authenticator
from .defaults import DEFAULT_EXPIRES_IN


@register_authenticator("https://track-test.21eline.com")
class YZAuthenticator(Authenticator):
    """track-test.21eline.com 认证器。"""

    def authenticate(self, auth, tag: str) -> None:
        """将 username 作为 token 写入会话(此认证器为简化实现)。"""
        content = f"data[username]={auth.token}"

        auth.apply_token(
            content,
            auth.expires_in if auth.expires_in else DEFAULT_EXPIRES_IN,
        )