"""内置认证器 —— 导入以触发 @register_authenticator 装饰器执行。

物理迁移自 gimbal/auth/authenticators/__init__.py。
"""
from .pretoken import PreTokenAuthenticator  # noqa: F401
from .http_basic import HTTPSAuthenticator, HTTPAuthenticator  # noqa: F401
from .wl import WLAuthenticator  # noqa: F401 - 导入即触发注册
from .yhr import YHRAuthenticator  # noqa: F401
from .yz import YZAuthenticator  # noqa: F401