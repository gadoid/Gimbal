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

        # 从 set-cookie 取 token
        cookie = headers.get("set-cookie")
        if not cookie:
            # TOK-06:set-cookie 即凭证,错误消息不带头内容(只报缺键)。
            raise AuthError("API 响应中未找到 set-cookie 凭证头")

        auth.apply_token(
            cookie,
            auth.expires_in if auth.expires_in else DEFAULT_EXPIRES_IN,
        )
        # TOK-06:DEBUG 日志移到 apply_token 之后(cookie 值已进掩码表)。
        # P2(review 2026-11-20):httpx.Headers 非 dict 子族,scrub 不处理
        # → set-cookie 明文照落;dict() 化后才走按值掩码(wl/github 同款)
        logger.debug("Response headers: {}", dict(headers))