"""GitHub OAuth2 认证器"""
import httpx
# API 库
from gimbal.auth.authenticator import Authenticator, register_authenticator
# 导入认证基类 和 装饰器
from .defaults import DEFAULT_EXPIRES_IN
from ...schema.auth import AuthSession

@register_authenticator("https://fin-tidb.21eflag.com/")
class WLAuthenticator(Authenticator):
    """物流系统 认证器
        逻辑：提交携带authorization字段的头信息
        按照标准请求格式进行认证
        -> {
            "username": username ,
            "password": password ,
            "code": code,
        }
        <- {
            "code": "状态码" ,
            "msg": "响应信息" ,
            "data": {
                "token": "token_info"
            },
            "request_id": "request_id"
        }
    """

    def authenticate(self, auth, tag: str ) -> None:
        response = httpx.post(
            f"{auth.url}api/home/login/userLogin",
            json={
                "username": auth.username,
                "password": auth.password,
                "code": 0000
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
        print(f"Response data: {data}")

        # 根据实际响应结构调整 token 提取逻辑
        resp_data = data.get("data")
        if isinstance(resp_data, dict):
            token = resp_data.get("token")
        else:
            token = None

        if not token:
            raise ValueError(f"API 响应中未找到 token: {data}")

        auth.apply_token(token, auth.expires_in if auth.expires_in else DEFAULT_EXPIRES_IN )


if  __name__ == "__main__" :
    auth = AuthSession(
        url="https://fin-tidb.21eflag.com/",
        username="18180789650",
        password="yhd123456!",
        expires_in=7200
    )
    WLAuthenticator().authenticate(auth=auth,tag="test")
    print(auth)