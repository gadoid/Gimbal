"""内置认证器 - 导入以触发 @register_authenticator 装饰器执行"""
from .pretoken import PreTokenAuthenticator
from .http_basic import HTTPSAuthenticator, HTTPAuthenticator
from .wl import WLAuthenticator  # noqa: F401 - 导入即触发注册

# noqa: F401 - 导入即触发注册
