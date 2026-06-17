"""GitHub OAuth2 认证器"""
import httpx
from gimbal.auth.authenticator import Authenticator, register_authenticator
from gimbal.exceptions import AuthError
from gimbal.log import get_logger

logger = get_logger(__name__)


@register_authenticator("https://api.github.com/")
class GitHubAuthenticator(Authenticator):
    """GitHub OAuth2 认证器

    支持两种模式：
    - GitHub OAuth App（用户名+密码 → 获取 access_token）
    - GitHub App（使用 client_id/client_secret 作为用户名/密码）
    """

    def authenticate(self, auth, tag: str) -> None:
        """以 client_id/client_secret 走 GitHub OAuth access_token 端点，拿到 token 后写入会话（默认 8 小时有效期）。"""
        response = httpx.post(
            f"{auth.url}login/oauth/access_token",
            json={
                "client_id": auth.username,
                "client_secret": auth.password,
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        logger.debug("GitHub OAuth response: {}", data)

        token = data.get("access_token")
        if not token:
            raise AuthError(f"GitHub OAuth 未返回 access_token: {data}")

        # GitHub token 没有明确的过期时间，默认给个合理值
        expires_in = 3600 * 8  # 8 小时
        auth.apply_token(token, expires_in)
