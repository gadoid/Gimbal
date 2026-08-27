"""WLAuthenticator —— 物流系统(fin-tidb)专用认证器。

物理迁移自 gimbal/auth/authenticators/wl.py。
"""
import httpx
from loguru import logger

from ..authenticator import Authenticator, register_authenticator
from ..exceptions import AuthError
from .defaults import DEFAULT_EXPIRES_IN


@register_authenticator("https://fin-tidb.21eflag.com/")
class WLAuthenticator(Authenticator):
    """物流系统认证器。

    流程:POST {url}api/home/login/userLogin 携 authorization=tidb_env 头,
    从 data.token 取 token 写入会话。
    """

    def authenticate(self, auth, tag: str) -> None:
        """调用物流系统登录接口,从 data.token 取 token 写入会话;未取到则抛 AuthError。"""
        response = httpx.post(
            f"{auth.url}api/home/login/userLogin",
            json={
                "username": auth.username,
                "password": auth.password,
                "code": "0000",
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "authorization": "tidb_env",
            },
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        logger.debug("Response data: {}", data)

        # 根据实际响应结构调整 token 提取逻辑
        resp_data = data.get("data")
        if isinstance(resp_data, dict):
            token = resp_data.get("token")
        else:
            token = None

        if not token:
            raise AuthError(f"API 响应中未找到 token: {data}")

        auth.apply_token(
            token,
            auth.expires_in if auth.expires_in else DEFAULT_EXPIRES_IN,
        )