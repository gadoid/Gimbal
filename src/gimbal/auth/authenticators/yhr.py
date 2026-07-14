"""YHRAuthenticator - 亿海融系统（21eline）专用认证器"""
import httpx
# API 库
from gimbal.auth.authenticator import Authenticator, register_authenticator
# 导入认证基类 和 装饰器
from .defaults import DEFAULT_EXPIRES_IN
from ...schema.auth import AuthSession
from ...exceptions import AuthError
from ...log import get_logger

logger = get_logger(__name__)

@register_authenticator("https://test.21eline.com/")
class YHRAuthenticator(Authenticator):
    """亿海融系统 认证器
        逻辑：提交携带authorization字段的头信息
        按照标准请求格式进行认证
        -> data%5Busername%5D=yhxjsx&data%5Bpassword%5D=Codfish1234!&data%5Bverify%5D=1111&data%5Bremember%5D=0
        <- headers  PHPSESSID=e6uuvg85sas8o0fcm8o9tdk6n2
    """

    def authenticate(self, auth, tag: str ) -> None:
        """调用物流系统登录接口，从 data.token 取 token 写入会话；未取到则抛 AuthError。"""
        content = f"data[username]={auth.username}&data[password]={auth.password}"
        response = httpx.post(
            f"{auth.url}newshopadmin-tidb/Home/Public/index.html",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Host": "test.21eline.com",
            },
            content= content,
            timeout=30,
        )
        response.raise_for_status()
        
        data = response.headers
        logger.debug("Response data: {}", data)

        # 根据实际响应结构调整 token 提取逻辑
        cookie = data.get("set-cookie")
        if not cookie:
            raise AuthError(f"API 响应中未找到 cookie: {cookie}")

        auth.apply_token(cookie, auth.expires_in if auth.expires_in else DEFAULT_EXPIRES_IN )


if  __name__ == "__main__" :
    auth = AuthSession(
        url="https://test.21eline.com/",
        username="yhxjsx",
        password="Codfish1234!",
        expires_in=7200
    )
    YHRAuthenticator().authenticate(auth=auth,tag="test")
    print(auth)