"""YHRAuthenticator —— 亿海融系统(21eline)专用认证器。

物理迁移自 gimbal/auth/authenticators/yhr.py。
"""
import httpx
from loguru import logger

from ..authenticator import Authenticator, register_authenticator
from ..exceptions import AuthError
from .defaults import DEFAULT_EXPIRES_IN


@register_authenticator("https://test.21eline.com/")
class YHRAuthenticator(Authenticator):
    """亿海融系统认证器。

    流程:form-encoded POST,登录后从 set-cookie 取 PHPSESSID 作为 token。
    """

    def authenticate(self, auth, tag: str) -> None:
        """调用亿海融登录接口,从 set-cookie 取 token;未取到则抛 AuthError。"""
        content = f"data[username]={auth.username}&data[password]={auth.password}"
        response = httpx.post(
            f"{auth.url}newshopadmin-tidb/Home/Public/index.html",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Host": "test.21eline.com",
            },
            content=content,
            timeout=30,
        )
        response.raise_for_status()

        headers = response.headers
        logger.debug("Response headers: {}", headers)

        # 从 set-cookie 取 token
        cookie = headers.get("set-cookie")
        if not cookie:
            raise AuthError(f"API 响应中未找到 cookie: {cookie}")

        auth.apply_token(
            cookie,
            auth.expires_in if auth.expires_in else DEFAULT_EXPIRES_IN,
        )