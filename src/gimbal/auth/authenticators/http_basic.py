"""HTTP/HTTPS 通用认证器"""
import httpx
from gimbal.auth.authenticator import Authenticator, register_authenticator
from gimbal.log import get_logger

logger = get_logger(__name__)


@register_authenticator("https://")
class HTTPSAuthenticator(Authenticator):
    """HTTPS 通用认证器（OAuth2 / Basic Auth）"""

    def authenticate(self, auth, tag: str) -> None:
        """向 auth.url POST {username, password}，从响应中读取 access_token/token 与 expires_in 并写入会话。"""
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
        """向 auth.url POST {username, password}，从响应中读取 access_token/token 与 expires_in 并写入会话（HTTP 明文版本）。"""
        # TOK-08c(2026-11-20 审计):非 TLS login_url 上口令明文 POST。
        # 内网被测系统走 http 是合法形态 → 只告警不拦截(镜像 TOK-02
        # 「fail-fast + 逃生口」的轻量版:链路嗅探/误配在日志可见)
        logger.warning(
            "auth[{}]: login_url 为 http:// —— 口令将以明文上链"
            "(内网测试形态可忽略;公网地址或误配请改 https)", tag)
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
