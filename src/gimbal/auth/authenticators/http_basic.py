"""HTTP/HTTPS 通用认证器"""
import httpx
from gimbal.auth.authenticator import Authenticator, register_authenticator


@register_authenticator("https://")
class HTTPSAuthenticator(Authenticator):
    """HTTPS 通用认证器（OAuth2 / Basic Auth）"""

    def authenticate(self, auth, tag: str) -> None:
        response = httpx.post(
            auth.url,
            json={
                "username": auth.username,
                "password": auth.password,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        token = data.get("access_token") or data.get("token")
        expires_in = data.get("expires_in")
        auth.apply_token(token, expires_in)


@register_authenticator("http://")
class HTTPAuthenticator(Authenticator):
    """HTTP 通用认证器（OAuth2 / Basic Auth）"""

    def authenticate(self, auth, tag: str) -> None:
        response = httpx.post(
            auth.url,
            json={
                "username": auth.username,
                "password": auth.password,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        token = data.get("access_token") or data.get("token")
        expires_in = data.get("expires_in")
        auth.apply_token(token, expires_in)
