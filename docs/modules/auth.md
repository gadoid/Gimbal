# Auth 模块

> 认证管理模块：`AuthManager` 统一入口、`Authenticator` URL 路由式策略、`AuthRegistry` 运行期状态容器、`AuthSession` 读写一体数据类

## 目录结构

```
gimbal/auth/
├── __init__.py             # 公共 API（AuthManager、Authenticator、异常等）
├── manager.py              # AuthManager 统一认证入口
├── authenticator.py        # Authenticator 抽象 + register_authenticator 装饰器 + get_authenticator 路由
├── registry.py             # AuthRegistry 运行期 token 容器
├── exceptions.py           # 异常 re-export（已迁移至 gimbal.exceptions）
└── authenticators/         # 内置认证器实现（import 触发自动注册）
    ├── __init__.py         # 触发所有内置认证器注册
    ├── defaults.py         # DEFAULT_TIMEOUT / DEFAULT_EXPIRES_IN / DEFAULT_REFRESH_THRESHOLD
    ├── pretoken.py         # PreTokenAuthenticator（无 URL 时使用）
    ├── http_basic.py       # HTTPSAuthenticator / HTTPAuthenticator（默认回退）
    ├── github.py           # GitHub OAuth 认证器
    └── wl.py               # 物流系统（WLAuthenticator）专用认证器
```

> 公共 `AuthSession` 数据类位于 `gimbal.schema.auth`，由 `gimbal.schema` 统一导出。

## 概览

认证体系由四部分组成：

1. **`AuthSession`**（Pydantic 模型）—— 认证会话的"读写一体"数据载体。认证前填 `url`/`username`/`password`/`expires_in`；认证成功后由 `apply_token()` 填充 `token`/`expires_at`/`refresh_token`。
2. **`AuthRegistry`** —— `tag → AuthSession` 的可变映射。把运行期 token 状态从 frozen 的 `BootstrapConfig` 抽出来，让配置与状态边界清晰。
3. **`Authenticator`**（抽象） + **`register_authenticator(url_pattern)`** —— URL 路由式认证策略。新增认证器只需用装饰器声明 URL pattern 即可。
4. **`AuthManager`** —— 统一认证入口，对外暴露 `get_auth(tag)`（自动登录/刷新）与 `load_and_auth(tag, data)`（从 dict 加载并认证）。

## 为什么需要 AuthRegistry

原本 `AuthSession` 存放在 `BootstrapConfig.users` 字典里，但 `BootstrapConfig` 是 `frozen=True`。代码通过 dict 的内部可变性绕过 frozen 约束——读 `cfg.users.get(tag)` 正常，但 `cfg.users` 本身被设计为"配置输入"，运行期写入 token 抹掉了配置与状态的边界。

把 `AuthSession` 拿出来放进独立的 `AuthRegistry`：
- `BootstrapConfig` 保持 frozen，承载纯配置输入
- `AuthRegistry` 显式可写，承载运行期认证状态
- 调用方拿到的不是 dict（接口不收敛），而是带语义的方法

## 核心类

### AuthManager

`AuthManager` 是认证体系的统一入口。构造时**必须**接受一个 `AuthRegistry` 实例（不接受 duck-typed 替代对象，避免静默错误）。

```python
class AuthManager:
    """统一认证入口。

    使用流程：
        auth = AuthManager(registry).get_auth("admin")
        if auth.is_authenticated:
            headers = {"Authorization": auth.auth_header}
    """

    def __init__(self, registry: AuthRegistry) -> None:
        """初始化 AuthManager。

        Args:
            registry: AuthRegistry 实例（运行期 token 状态容器）

        Raises:
            TypeError: registry 不是 AuthRegistry 实例
        """

    def get_auth(self, tag: str) -> AuthSession: ...
    def load_and_auth(self, tag: str, data: dict) -> AuthSession: ...
```

#### `get_auth(tag: str) -> AuthSession`

获取已认证的 `AuthSession`，必要时自动登录或刷新 token。

处理流程：
1. 从 registry 取出 session；若不存在则抛 `AuthSessionNotFound`。
2. 已认证且未到刷新时机（`is_authenticated and not should_refresh`）→ 直接返回。
3. 未认证 → 走登录路径（`_login`）。
4. 需刷新 → 走刷新路径（`_refresh`），失败降级为重新登录。

#### `load_and_auth(tag: str, data: dict) -> AuthSession`

从配置字典构造 `AuthSession`、写入 registry，并在未认证时自动登录。三步合一：`AuthSession(**data)` → `registry.set(tag, ...)` → 必要时 `_login`。

#### `_login(auth, tag)`（内部）

根据 `auth.url` 选择已注册的 `Authenticator` 并调用其 `authenticate` 完成登录；任何异常统一包装为 `AuthLoginFailed`。

#### `_refresh(auth, tag)`（内部）

使用 `refresh_token` 调远程 refresh 端点（`{url}/refresh`）续期。语义：

- **PreToken 模式（无 `url`）**：直接 `return`（token 即 password，重新登录无意义）。
- **无 `refresh_token`**：跳过 refresh，全量重登录（修复 #10：不要把 `access_token` 当 `refresh_token` 发，OAuth2 严格服务商如 Auth0/Okta 会拒收）。
- **调用失败**：降级为全量重登录。
- **成功**：从响应中读取 `access_token`、`expires_in`、新的 `refresh_token`（可能轮换），调 `auth.apply_token(...)` 写入。

### AuthRegistry

`AuthRegistry` 是 `tag → AuthSession` 的可变映射。设计上不继承 `dict`，避免破坏封装并避免暴露 `.keys()`/`.items()` 等"配置感"接口。

```python
class AuthRegistry:
    """tag → AuthSession 的可变映射。

    使用：
        reg = AuthRegistry()
        reg.set("admin", auth_session)
        sess = reg.get("admin")

    设计要点：
      - 不继承 dict（避免破坏封装、避免暴露 .keys()/.items() 等"配置感"接口）
      - 提供 snapshot() 用于"只读"导出（例如送入模板解析 root）
      - 写入是显式的 set()，不是 __setitem__——降低误用
    """

    __slots__ = ("_sessions",)

    def __init__(self) -> None: ...
    def set(self, tag: str, session: AuthSession) -> None: ...
    def remove(self, tag: str) -> bool: ...
    def clear(self) -> None: ...
    def get(self, tag: str) -> Optional[AuthSession]: ...
    def has(self, tag: str) -> bool: ...
    def tags(self) -> list[str]: ...
    def snapshot(self) -> dict[str, AuthSession]: ...   # 浅拷贝
```

#### 方法说明

| 方法 | 行为 |
| --- | --- |
| `set(tag, session)` | 注册或覆盖一个 `AuthSession`。tag 重复时直接覆盖，不做唯一性校验。 |
| `remove(tag) -> bool` | 移除指定 tag 的 `AuthSession`；返回是否原本存在。 |
| `clear()` | 清空所有 `AuthSession`，常用于测试或场景隔离。 |
| `get(tag) -> Optional[AuthSession]` | 按 tag 取出 `AuthSession`；不存在则返回 `None`（不抛异常）。 |
| `has(tag) -> bool` | 判断指定 tag 是否已注册 `AuthSession`。 |
| `tags() -> list[str]` | 返回当前已注册的所有 tag 列表（浅拷贝，外部修改不影响内部状态）。 |
| `snapshot() -> dict` | 返回当前所有 session 的浅拷贝字典，用于"模板解析根"等只读场景。 |

#### 容器协议

- `__contains__(tag) -> bool`
- `__len__() -> int`
- `__iter__() -> Iterator[str]`（迭代 tag）
- `__repr__() -> str`（形如 `AuthRegistry(tags=['admin', 'github_user'])`）

`Configuration` 内持有 `auth_registry` 字段，注入到 `ScenarioPreprocessor` 与 `AuthManager`。

### Authenticator 抽象

`Authenticator` 是认证策略的抽象基类（`ABC`）。

```python
class Authenticator(ABC):
    """认证策略抽象接口"""

    @abstractmethod
    def authenticate(self, auth: AuthSession, tag: str) -> None:
        """执行该认证器对应的认证流程。

        成功时必须调用 auth.apply_token() 将新 token 写入会话。

        Args:
            auth: AuthSession 对象
            tag: 认证标识（用于日志）

        Raises:
            AuthLoginFailed: 认证失败时抛出
        """
        raise NotImplementedError
```

### URL 路由式注册

通过装饰器按 URL pattern 注册认证器类：

```python
def register_authenticator(url_pattern: str):
    """装饰器工厂：把认证器类按 url_pattern 注册到全局表。"""
    def deco(cls: type[Authenticator]) -> type[Authenticator]:
        _AUTHENTICATOR_REGISTRY[url_pattern] = cls
        return cls
    return deco


def get_authenticator(url: str) -> Authenticator:
    """按 URL 解析应使用的认证器实例。

    匹配顺序：
        1. 精确匹配注册表中的 pattern
        2. URL 前缀匹配（注册时使用 URL 前缀）
        3. 兜底：HTTPSAuthenticator

    url 为空时直接返回 PreTokenAuthenticator（无远程端点的预置 Token 模式）。

    Returns:
        匹配的认证器实例
    """
```

匹配优先级：**精确匹配 > 前缀匹配 > HTTPS 兜底**。无 URL（`url == ""`）走 `PreTokenAuthenticator`。

## 内置认证器

| 认证器 | URL pattern | 说明 |
| --- | --- | --- |
| `PreTokenAuthenticator` | `""`（无 URL） | 预置 Token 模式：直接把 `password` 当 `token` 用 |
| `HTTPSAuthenticator` | `https://`（默认回退） | HTTPS 通用 OAuth2 / Basic Auth，POST `{username, password}`，读 `access_token`/`token` + `expires_in` |
| `HTTPAuthenticator` | `http://` | HTTP 通用认证器（明文版本） |
| `GitHubAuthenticator` | `https://api.github.com/` | GitHub OAuth App / GitHub App（client_id/client_secret 充当 username/password） |
| `WLAuthenticator` | `https://fin-tidb.21eflag.com/` | 物流系统（fin-tidb）专用认证器 |

`authenticators/__init__.py` 集中 import 所有内置认证器，触发 `@register_authenticator(...)` 自动注册。`gimbal.auth.__init__` 也会 import `authenticators` 子包，确保 `import gimbal.auth` 即可让所有内置认证器生效。

### `defaults.py`

`authenticators/defaults.py` 提供认证器复用的默认常量：

```python
DEFAULT_TIMEOUT: int = 30           # HTTP 调用默认超时（秒）
DEFAULT_EXPIRES_IN: int = 7200      # 默认 Token 有效期（1 小时）
DEFAULT_REFRESH_THRESHOLD: int = 300  # 提前 5 分钟开始刷新
```

## AuthSession 数据类（位于 `gimbal.schema.auth`）

`AuthSession` 是 Pydantic v2 `BaseModel`，采用读写一体设计：认证前填写凭证字段，认证后写入 token 字段。

```python
class AuthSession(BaseModel):
    # ── 认证地址和凭证 ──
    url: str
    username: str
    password: str

    # ── Token 配置（认证后填充）──
    expires_in: int | None         # 认证前可配；refresh 路径会重新锚定
    token: str | None
    token_type: str = "Bearer"
    expires_at: datetime | None
    refresh_token: str | None      # 独立于 access_token，OAuth2 标准
```

### 字段语义

- `url`：认证接口地址。空字符串代表 PreToken 模式。
- `username`/`password`：凭证。PreToken 模式下 `password` 兼作 `token`。
- `expires_in`：Token 生命周期（秒）。`apply_token(token, expires_in=...)` 时会按语义更新。
- `token`：访问令牌（access_token）。
- `token_type`：默认 `"Bearer"`。
- `expires_at`：过期时间（UTC aware datetime）。`is_authenticated` / `should_refresh` 比较时使用。
- `refresh_token`：**与 `access_token` 分开存储**（修复 #10）。OAuth2 标准要求两者独立；用 `access_token` 当 `refresh_token` 发会被多数严格服务商拒收。

> `tag`（唯一标识）由 registry 的 key 决定，**不再**存储在 `AuthSession` 内。

### 计算属性

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `is_authenticated` | `bool` | 是否已认证：有 `token` 且未过期。`expires_at` 为空时只看是否有 `token`。 |
| `should_refresh` | `bool` | 是否需要刷新：距过期 < 5 分钟（`DEFAULT_REFRESH_THRESHOLD`）。`expires_at` 为空则返回 `False`。 |
| `auth_header` | `str \| None` | 形如 `"Bearer xxx"` 的 Authorization 头值。**修复 #66**：会拒绝 `token_type` 或 `token` 中的 ASCII 控制字符（0x00-0x1F、0x7F；HT 0x09 除外），防止 HTTP header 注入（CWE-93）。`token` 为空时返回 `None`；触发控制字符检查时抛 `ValueError`，错误信息只打印长度，不直接打印原值（避免日志注入）。 |
| `remaining_seconds` | `int \| None` | 距离过期的剩余秒数（最多 0）。`expires_at` 为空则返回 `None`。 |

> `should_refresh` 阈值是写死在代码里的 `5 minutes`（对应 `defaults.DEFAULT_REFRESH_THRESHOLD`）。

### 方法

#### `apply_token(token: str, expires_in: int | None = None) -> AuthSession`

写入 `token` 并按 `expires_in` 语义更新 lifetime（修复 #4）：

| `expires_in` 语义 | 行为 |
| --- | --- |
| `> 0` | 显式设置新 lifetime：`expires_in = N`，`expires_at = now + N` |
| `== 0` | 显式清空 lifetime：`expires_in = 0`，`expires_at = None` |
| `None` | 保持 `self.expires_in` 不变，但若 `self.expires_in > 0` 则重新锚定 `expires_at = now + self.expires_in`；若 `self.expires_in` 为 0/空则 `expires_at` 保持不变 |

设计取舍：
- `None` 表示"调用方不指定"，不重置已配置的 lifetime。
- re-anchor 让"重置 token 值但不重新认证"也能刷新过期时刻（refresh 路径常用）。
- `0` 是显式"清空"信号，比让 `expires_at` 保持不变更明确。

**修复 #R1**：`apply_token` 早失败——写入 token 时验证 `token` 中不含控制字符，**不**等到 `auth_header` 访问时才报错，避免认证流程后段被恶意服务端响应注入。

> `apply_token` 写入 token 后**不会**清空 `password`（清空 password 请显式调 `clear_password`）。

#### `clear_token() -> AuthSession`

清空 `token`、`expires_at`、`expires_in` 三个字段（修复 #4：也清空 `expires_in`，与新构造的 session 状态一致），使 session 回到"未认证且无 lifetime 配置"的初始状态。`password` 与 `refresh_token` 保留。

#### `is_same_credential(other: AuthSession) -> bool`

按 `url` / `username` / `password` 三个字段逐项相等比较，判断两个 `AuthSession` 是否指向同一份凭证。用于"换 token 但凭证未变"的场景。

#### `clear_password() -> AuthSession`（修复 #100）

把 `password` 字段置空（`self.password = ""`），缩短敏感凭据在内存中的驻留时间。`url` / `username` / `token` 保持不变。

调用场景：
- 认证成功后立即调用（密码已不再需要）。
- 进程即将退出前清理敏感数据。

注意：
- PreToken 模式下 `password` 兼作 token。`apply_token(token)` 会把 `token` 复制进来，所以 `clear_password` 后 `token` 仍可用。
- `url` / `username` 不清空（认证配置需要保留）。
- 失败时 `is_authenticated` / `should_refresh` 的依赖可能受影响。

#### `@classmethod from_dict(cls, data: dict) -> AuthSession`

`cls(**data)` 语法糖，从字段字典直接构造。

### 工具函数：`_aware_utc(dt: datetime) -> datetime`

模块级私有函数。对带 tz 的 datetime 原样返回；对 naive datetime 补 UTC 后返回，确保比较时不会抛 `TypeError`。

背景：Pydantic v2 反序列化 ISO datetime 字符串时默认得到 naive datetime。`AuthSession.expires_at` 一旦写入就是 UTC，round-trip 后必须仍是同一个时间点，否则 `aware now() > naive expires_at` 会抛 `TypeError`。业务约束：框架内所有写入 `expires_at` 的路径都使用 `timezone.utc`，所以"naive → UTC"是无损解释。

## 异常类

异常**已迁移至** `gimbal.exceptions`；`gimbal.auth.exceptions` 仅做 re-export 保持向后兼容。完整层次结构见 `exceptions.py` 文档，认证相关部分：

```python
class AuthError(GimbalError):
    """认证异常基类。"""
    code = "AUTH_ERROR"

class AuthLoginFailed(AuthError):
    """登录失败（AuthManager._login 把任何 Exception 包装为此）。"""
    code = "AUTH_LOGIN_FAILED"

class AuthTokenExpired(AuthError):
    """Token 已过期或无效。"""
    code = "AUTH_TOKEN_EXPIRED"

class AuthSessionNotFound(AuthError):
    """AuthSession 未找到（registry.get(tag) 返回 None 时由 AuthManager.get_auth 抛出）。"""
    code = "AUTH_SESSION_NOT_FOUND"
```

`AuthManager._login` 的具体语义：把任何底层 `Exception`（网络错误、解析错误、认证器抛出的 `AuthError` 等）包装为 `AuthLoginFailed(f"Login failed for '{tag}': {e}") from e`，统一对外暴露一个登录失败异常类型。`AuthManager._refresh` 不直接抛认证异常；调用失败时只记 warning 并降级为重登录。

## 使用示例

### 基本流程（通过 Configuration）

```python
from gimbal.core.bootstrap import bootstrap
from gimbal.auth import AuthManager

config = bootstrap(cli_ctx)
auth_mgr = AuthManager(config.auth_registry)

# 已认证则直接返回；未认证则自动登录；即将过期则自动刷新
auth = auth_mgr.get_auth("admin")
if auth.is_authenticated:
    headers = {"Authorization": auth.auth_header}
```

### 动态加载并立即认证

```python
session = auth_mgr.load_and_auth("github_user", {
    "url":        "https://api.github.com/",
    "username":   "<client_id>",
    "password":   "<client_secret>",
    "expires_in": 3600,
})
print(session.token, session.expires_at, session.remaining_seconds)
```

### 认证成功后清理密码

```python
auth = auth_mgr.get_auth("admin")
if auth.is_authenticated:
    auth.clear_password()  # 修复 #100：缩短 password 在内存中的驻留时间
```

### PreToken 模式

```python
# 无 url：直接把 password 当 token
session = auth_mgr.load_and_auth("static", {
    "password": "pre-shared-token-xxx",
    "expires_in": 3600,
})
# session.url == "", session.token == "pre-shared-token-xxx"
# clear_password() 仍安全：apply_token 已把 token 复制到 self.token
```

### 编写自定义认证器

```python
from gimbal.auth.authenticator import Authenticator, register_authenticator
from gimbal.exceptions import AuthError

@register_authenticator("https://auth.example.com/")
class ExampleAuthenticator(Authenticator):
    def authenticate(self, auth, tag: str) -> None:
        import httpx
        resp = httpx.post(
            f"{auth.url}api/login",
            json={"username": auth.username, "password": auth.password},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise AuthError(f"login failed: {data}")
        # 显式传 expires_in；不传则保留 self.expires_in 但 re-anchor expires_at
        auth.apply_token(token, data.get("expires_in", 7200))
```

## 设计原则

1. **配置/状态分离**：`AuthSession` 仍可读写（认证后写入 token），但承载它的 `AuthRegistry` 是独立可变容器；`BootstrapConfig` 不再承载运行期状态。
2. **URL 路由式**：通过 URL 自动匹配认证器，新认证器只需 `@register_authenticator(pattern)` 装饰。
3. **Token 自动刷新**：`get_auth()` 在 `should_refresh` 为真时自动调 `_refresh()`，失败降级为重新登录。`_refresh` 在无 `url`（PreToken 模式）或无 `refresh_token` 时直接重登录。
4. **异常隔离**：单个认证器异常会被 `AuthManager._login` 包装为 `AuthLoginFailed` 抛出；`_refresh` 失败则降级为重登录，不向上抛认证异常。
5. **严格的类型契约**：`AuthManager.__init__` 用 `isinstance(registry, AuthRegistry)` 校验，**不**接受 duck-typed 代理对象（修复 #2），避免静默错误。
6. **安全默认**：`auth_header` 拒绝控制字符（修复 #66），`apply_token` 早失败验证 token（修复 #R1），`clear_password` 缩短敏感凭据驻留时间（修复 #100）。
