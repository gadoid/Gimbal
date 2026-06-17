"""预置 Token 认证器"""
from gimbal.auth.authenticator import Authenticator, register_authenticator


@register_authenticator("")
class PreTokenAuthenticator(Authenticator):
    """预置 Token 模式（无 URL 时使用 password 作为 token）"""

    def authenticate(self, auth, tag: str) -> None:
        """将 password 字段原样作为 token 写入会话；无 password 时不修改状态。"""
        if auth.password:
            auth.apply_token(auth.password)
