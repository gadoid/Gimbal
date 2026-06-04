# Auth 模块

> 认证管理模块：AuthManager 统一入口、Authenticator 路由式策略、AuthRegistry 状态容器

## 目录结构

```
gimbal/auth/
├── __init__.py            # 公共 API
├── manager.py             # AuthManager 统一认证入口
├── authenticator.py       # Authenticator 抽象 + register_authenticator 装饰器
├── registry.py            # AuthRegistry  运行期 token 容器
├── exceptions.py          # 异常（已迁移至 gimbal.exceptions；此处保留 re-export）
└── authenticators/        # 内置认证器实现（import 触发自动注册）
    ├── __init__.py
    ├── pretoken.py        # PreTokenAuthenticator（无 URL 时默认）
    ├── http_basic.py      # HTTPSAuthenticator（默认回退）
    ├── github.py          # GitHub OAuth
    └── wl.py              # wl 认证
```

> 旧的 `template.py` 已删除。

## 为什么需要 AuthRegistry

原本 `AuthSession` 存放在 `BootstrapConfig.users` 字典里，但 `BootstrapConfig` 是 `frozen=True`。代码通过 dict 的内部可变性绕过 frozen 约束——读 `cfg.users.get(tag)` 正常，但 `cfg.users` 本身被设计为"配置输入"，运行期写入 token 抹掉了配置与状态的边界。

把 `AuthSession` 拿出来放进独立的 `AuthRegistry`：
- `BootstrapConfig` 保持 frozen，承载纯配置输入
- `AuthRegistry` 显式可写，承载运行期认证状态
- 调用方拿到的不是 dict（接口不收敛），而是带语义的方法

## 核心组件

### AuthManager

```python
class AuthManager:
    """统一认证入口。

    使用流程：
        auth = AuthManager(registry).get_auth("admin")
        if auth.is_authenticated:
            headers = {"Authorization": auth.auth_header}
    """

    def __init__(self, registry: "AuthRegistry | Configuration"): ...
        # 兼容老调用：AuthManager(configuration) → 自动取 .auth_registry

    def get_auth(self, tag: str) -> AuthSession:
        """获取认证会话，自动处理登录/刷新。
        - 已认证且无需刷新 → 直接返回
        - 未认证 → 触发登录
        - 需刷新 → 刷新 token（失败则降级为重新登录）
        """

    def load_and_auth(self, tag: str, data: dict) -> AuthSession:
        """从字典加载 + 认证 + 写入 registry（一次完成）。"""
```

### AuthRegistry

```python
class AuthRegistry:
    """tag → AuthSession 的可变映射。

    - 不继承 dict（避免破坏封装）
    - 写入走显式 set()，不暴露 __setitem__
    - snapshot() 用于"模板解析根"等只读场景
    """

    __slots__ = ("_sessions",)

    def __init__(self) -> None: ...
    def set(self, tag: str, session: AuthSession) -> None
    def remove(self, tag: str) -> bool
    def clear(self) -> None
    def get(self, tag: str) -> Optional[AuthSession]
    def has(self, tag: str) -> bool
    def tags(self) -> list[str]
    def snapshot(self) -> dict[str, AuthSession]    # 浅拷贝

    # 容器协议
    def __contains__(self, tag: str) -> bool
    def __len__(self) -> int
    def __iter__(self) -> Iterator[str]
    def __repr__(self) -> str
```

`Configuration` 内持有 `auth_registry` 字段，注入到 `ScenarioPreprocessor` / `AuthManager`。

### Authenticator 抽象

```python
class Authenticator(ABC):
    """认证策略抽象接口。"""

    @abstractmethod
    def authenticate(self, auth: AuthSession, tag: str) -> None:
        """执行认证；成功时调用 auth.apply_token() 填充 token。
        失败时抛 AuthLoginFailed。"""
        raise NotImplementedError
```

### URL 路由式注册

```python
def register_authenticator(url_pattern: str):
    """装饰器：注册 URL pattern -> 认证器类。"""
    def deco(cls): _AUTHENTICATOR_REGISTRY[url_pattern] = cls; return cls
    return deco


def get_authenticator(url: str) -> Authenticator:
    """匹配顺序：
        1. 精确匹配
        2. URL 前缀匹配
        3. 默认 HTTPSAuthenticator

    无 URL 时使用 PreTokenAuthenticator。
    """
```

## 内置认证器

| 认证器 | URL pattern | 说明 |
|---|---|---|
| `PreTokenAuthenticator` | （无 URL） | 预置 Token 认证 |
| `HTTPSAuthenticator` | （默认回退） | HTTP Basic Auth |
| `GitHubAuthenticator` | `https://api.github.com/` | GitHub OAuth |
| `WLAuthenticator` | 自定义 | wl 认证 |

`template.py` 已被删除。

## AuthSession 数据类（位于 `gimbal.schema.auth`）

```python
class AuthSession(BaseModel):
    """读写一体设计。

    认证前填写：url / username / password / expires_in
    认证后填充：token / expires_at
    """

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
    is_authenticated: bool    # 有 token 且未过期
    should_refresh: bool      # 距过期 < 5 分钟
    auth_header: str | None   # "Bearer xxx"
    remaining_seconds: int | None

    # 方法
    def apply_token(token, expires_in=None) -> AuthSession
    def clear_token() -> AuthSession
    def is_same_credential(other) -> bool
    @classmethod
    def from_dict(data: dict) -> AuthSession
```

> tag（唯一标识）由 registry 的 key 决定，**不再**存储在 `AuthSession` 内。

## 异常类

定义在 `gimbal.exceptions`，`gimbal.auth.exceptions` 仅做 re-export 保持向后兼容：

```python
class AuthError(Exception): pass
class AuthSessionNotFound(AuthError): pass     # tag 不存在
class AuthLoginFailed(AuthError): pass         # 认证失败
class AuthTokenExpired(AuthError): pass        # token 过期
```

## 使用示例

```python
from gimbal.auth import AuthManager, AuthSession

# 1. 通过 Configuration 创建（bootstrap 时已注入 auth_registry）
from gimbal.core.boostrap import bootstrap
config = bootstrap(cli_ctx)
auth = AuthManager(config.auth_registry).get_auth("admin")

# 2. 动态加载（用 dict 注册一个认证 + 立即执行）
auth_mgr = AuthManager(config.auth_registry)
session = auth_mgr.load_and_auth("github_user", {
    "url":      "https://api.github.com/login",
    "username": "octocat",
    "password": "***",
    "expires_in": 3600,
})

# 3. 直接使用 auth
if session.is_authenticated:
    headers = {"Authorization": session.auth_header}
```

## 设计原则

1. **配置/状态分离**：`AuthSession` 仍可读写（认证后写入 token），但承载它的 `AuthRegistry` 是独立可变容器，**`BootstrapConfig` 不再承载运行期状态**。
2. **URL 路由式**：通过 URL 自动匹配认证器，新认证器只需 `@register_authenticator(pattern)` 装饰。
3. **Token 自动刷新**：`get_auth()` 在 `should_refresh` 为真时自动调 `_refresh()`，失败降级为重新登录。
4. **异常隔离**：单个认证器异常被吞掉记入日志；`AuthManager._login` 将任何 `Exception` 包装为 `AuthLoginFailed`。
5. **registry 兼容老调用**：`AuthManager(configuration)` 仍能工作——自动取 `configuration.auth_registry`。
