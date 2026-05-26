# Auth 模块

> 认证管理模块，支持多种认证策略的统一入口

## 目录结构

```
gimbal/auth/
├── __init__.py
├── authenticator.py       # 认证器基类和注册表
├── exceptions.py         # 认证相关异常
├── manager.py            # AuthManager 统一认证入口
└── authenticators/       # 内置认证器实现
    ├── __init__.py
    ├── defaults.py       # 默认认证器
    ├── github.py         # GitHub OAuth
    ├── http_basic.py     # HTTP Basic Auth
    ├── pretoken.py       # 预置 Token 认证
    ├── template.py       # 模板认证
    └── wl.py             # wl 认证
```

## 核心组件

### AuthManager

统一认证入口，负责管理认证生命周期。

```python
class AuthManager:
    """统一认证入口"""

    def __init__(self, config: BootstrapConfig):
        self._config = config

    def get_auth(self, tag: str) -> AuthSession:
        """获取认证会话，自动处理登录/刷新"""
        # 已认证且无需刷新 → 直接返回
        # 未认证 → 触发登录
        # 需刷新 → 刷新 token
        ...

    def load_and_auth(self, tag: str, data: dict) -> AuthSession:
        """从字典加载并认证"""
        ...
```

### Authenticator 抽象

```python
class Authenticator(ABC):
    """认证策略抽象接口"""

    @abstractmethod
    def authenticate(self, auth: AuthSession, tag: str) -> None:
        """执行认证，成功则调用 auth.apply_token() 填充 token"""
        raise NotImplementedError
```

### URL 路由式注册

使用装饰器注册不同 URL 对应的认证器：

```python
@register_authenticator("https://api.github.com/")
class GitHubAuthenticator(Authenticator):
    def authenticate(self, auth: AuthSession, tag: str) -> None:
        ...
```

匹配顺序：
1. 精确匹配
2. URL 前缀匹配
3. 默认使用 HTTPS 认证器

## 内置认证器

| 认证器 | 说明 |
|--------|------|
| `PreTokenAuthenticator` | 预置 Token 认证（无 URL 时使用） |
| `HTTPSAuthenticator` | HTTP Basic 认证（默认） |
| `GitHubAuthenticator` | GitHub OAuth |
| `TemplateAuthenticator` | 模板认证 |
| `WLAuthenticator` | wl 认证 |

## AuthSession 数据类

认证会话（读写一体设计）：

```python
class AuthSession(BaseModel):
    # 认证地址和凭证
    url: str
    username: str
    password: str

    # Token 配置
    expires_in: int | None
    token: str | None
    token_type: str = "Bearer"
    expires_at: datetime | None

    # 计算属性
    is_authenticated: bool      # 是否已认证
    should_refresh: bool        # 是否应该刷新（提前 5 分钟）
    auth_header: str | None    # Authorization 头值

    # 方法
    def apply_token(self, token: str, expires_in: int | None = None) -> AuthSession
    def clear_token(self) -> AuthSession
```

## 异常类

```python
class AuthError(Exception): pass
class AuthSessionNotFound(AuthError): pass
class AuthLoginFailed(AuthError): pass
class AuthRefreshFailed(AuthError): pass
```

## 使用示例

```python
from gimbal.auth import AuthManager
from gimbal.config.loader import ConfigLoader

# 初始化配置
cfg = ConfigLoader().load(cli_ctx)

# 获取认证会话
auth_manager = AuthManager(cfg)
auth = auth_manager.get_auth("admin")

# 检查认证状态
if auth.is_authenticated:
    headers = {"Authorization": auth.auth_header}
```

## 设计原则

1. **URL 路由式**: 通过 URL 自动匹配认证器
2. **认证器可扩展**: 支持自定义认证器注册
3. **Token 自动刷新**: 提前 5 分钟自动刷新
4. **读写一体**: AuthSession 既存储配置又存储运行时状态