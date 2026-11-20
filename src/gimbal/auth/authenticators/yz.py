"""YHRAuthenticator - 亿海融系统（21eline）专用认证器"""
import httpx
# API 库
from gimbal.auth.authenticator import Authenticator, register_authenticator
# 导入认证基类 和 装饰器
from .defaults import DEFAULT_EXPIRES_IN
from ..session import AuthSession
from ...exceptions import AuthError
from ...log import get_logger

logger = get_logger(__name__)

@register_authenticator("https://track-test.21eline.com")
class YZAuthenticator(Authenticator):
    """亿海融系统 认证器
        逻辑：提交携带authorization字段的头信息
        按照标准请求格式进行认证
        -> data%5Busername%5D=yhxjsx&data%5Bpassword%5D=Codfish1234!&data%5Bverify%5D=1111&data%5Bremember%5D=0
        <- headers  PHPSESSID=e6uuvg85sas8o0fcm8o9tdk6n2
    """

    def authenticate(self, auth, tag: str ) -> None:
        """预置 token 直通形态:data[username]=<预置 token> 写入会话。

        TOK-08e(2026-11-20 审计):token 未初始化(None)即消费,会把
        字面量 ``data[username]=None`` 写成会话 token —— fail-fast。
        docstring 所述真实登录协议(POST 表单 → PHPSESSID)缺外部
        系统信息未实现,登记 known-issues;如需真实登录另补实现。
        """
        if auth.token is None:
            raise AuthError(
                f"yz 认证器({tag}):auth.token 未初始化 —— 本认证器为"
                "预置 token 直通形态,需在会话上预置 token 后使用"
                "(真实登录协议未实现,见 known-issues)")
        content = f"data[username]={auth.token}"

        auth.apply_token(content, auth.expires_in if auth.expires_in else DEFAULT_EXPIRES_IN )


if  __name__ == "__main__" :
    # A3 凭证轮换(登记册):__main__ 演示块的硬编码真实口令已删,
    # 占位符示形;直通形态演示需预置 token
    auth = AuthSession(
        url="https://test.21eline.com/",
        username="<username>",
        password="<password>",
        token="<预置 token>",
        expires_in=7200
    )
    YZAuthenticator().authenticate(auth=auth,tag="test")
    print(auth)