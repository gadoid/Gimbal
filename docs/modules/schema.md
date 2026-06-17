# Schema 模块

> 数据模型模块：定义所有 Pydantic v2 数据模型（`Scenario`、`Step`、`Api`、`Strategy`、`AuthSession` 等），为 Gimbal 框架提供静态描述层。

## 目录结构

```
gimbal/schema/
├── __init__.py          # 统一 re-export：所有对外可用的模型/枚举
├── README.md
├── states.py            # StepState
├── ref.py               # RefBase, Ref
├── resource.py          # Resource, Mock, File, MockRef, FileRef, ResourceUnion
├── api.py               # Api, ApiRef, ApiUnion
├── request.py           # Request, RequestRef, RequestUnion
├── step.py              # Step, StepRef, StepUnion
├── strategy.py          # StrategyBase, Extract, Assign, Assertion, StrategyRef, StrategyUnion, Scope, AssertOperator, StrategyPhase, FailurePolicy
├── timepolicy.py        # TimePolicy, TimeoutPolicy, RecordPolicy, TimePolicyUnion
├── retrypolicy.py       # RetryPolicy
├── scenario.py          # Scenario, Meta, Config
├── setup.py             # Setup, SetupRef, SetupUnion
├── teardown.py          # Teardown, TeardownRef, TeardownUnion
└── auth.py              # AuthSession（含读写一体 token 状态、_aware_utc 工具函数）
```

`gimbal.schema.__init__` 把所有 Pydantic 模型和枚举聚合到模块顶层，对外暴露统一命名空间。`AuthSession` 与认证相关数据结构位于 `auth.py`，并通过 `from .auth import AuthSession` 在 `__init__.py` 导出。

## 概览

`schema` 是 Gimbal 框架的"静态描述层"——只承载数据形状与字段约束，**不**承载运行期状态。运行期 token 等可变状态由 `gimbal.auth` 子包（特别是 `AuthRegistry`）独立管理。

模型按职责分四类：

1. **场景层**：`Scenario`、`Meta`、`Config`。
2. **资源/接口/请求层**：`Resource`、`Api`、`Request`。
3. **执行/策略层**：`Step`、`Strategy`（`Extract` / `Assign` / `Assertion`）、`TimePolicy`、`RetryPolicy`、`Setup` / `Teardown`。
4. **认证层**：`AuthSession`（位于 `auth.py`，详见 `auth.md`）。

## 公共导出（`gimbal.schema.__init__`）

```python
from .states import StepState
from .ref import RefBase, Ref
from .resource import Resource, Mock, File, MockRef, FileRef, ResourceUnion
from .api import Api, ApiRef, ApiUnion
from .request import Request, RequestRef, RequestUnion
from .step import Step, StepRef, StepUnion
from .strategy import (
    StrategyBase, Extract, Assign, Assertion, StrategyRef, StrategyUnion,
    Scope, AssertOperator, StrategyPhase, FailurePolicy,
)
from .timepolicy import TimePolicy, TimeoutPolicy, RecordPolicy, TimePolicyUnion
from .retrypolicy import RetryPolicy
from .scenario import Scenario, Meta, Config
from .setup import Setup, SetupRef, SetupUnion
from .teardown import Teardown, TeardownRef, TeardownUnion
from .auth import AuthSession
```

> 旧版本中存在的 `Suite` 模型已不在 `__init__` 导出列表中（如需请直接 `from gimbal.schema.scenario import Suite`）。

## 核心模型

### Scenario

用例/场景模型：

```python
class Scenario(BaseModel):
    kind: Literal["scenario"] = "scenario"
    scenarioId: str
    meta: Meta                    # 用例元信息
    config: Config                # 执行配置
    resource: dict[str, ResourceUnion]  # 资源
    steps: list[StepUnion]        # 执行步骤
```

### Meta

用例元信息：

```python
class Meta(BaseModel):
    name: str
    description: str
    module: str                   # 业务模块
    priority: int
    author: str
    owner: str                    # 维护人
    tags: list[str]
    version: str
    createTime: datetime
    expire: bool                  # 过期标志
    requirementRef: list[RefBase] # 需求关联
```

### Config

用例执行配置：

```python
class Config(BaseModel):
    setup: list[SetupUnion]                 # 前置动作
    teardown: list[TeardownUnion]           # 后置动作
    services: dict[str, str]                # 服务名 → URL 映射
    users: dict[str, dict[str, AuthSession]] # 认证信息（运行期 token 由 AuthRegistry 接管）
    timePolicy: TimePolicyUnion
    retry: RetryPolicy | None
    vars: dict[str, Any]                    # 变量声明（字面量或生成式 spec dict）；详见 generator.md
```

> `Config.users` 在 Bootstrap 阶段被解析后，token 状态迁移到 `Configuration.auth_registry`，**`BootstrapConfig` 保持 frozen**（详见 `auth.md` 中的"为什么需要 AuthRegistry"）。

### Step

单步骤模型：

```python
class Step(BaseModel):
    kind: Literal["step"] = "step"
    api: ApiUnion
    request: RequestUnion
    strategy: list[StrategyUnion]
```

### Api

HTTP API 定义：

```python
class Api(BaseModel):
    kind: Literal["api"] = "api"
    service: str
    method: str
    path: str
    headers: dict | None
    timeout: float = 30.0
```

### Resource

资源（Mock / File 资源等），按 `kind` 字段做 discriminated union 区分：

```python
class Resource(BaseModel): ...        # 抽象基类，kind 字段用于派发
class Mock(Resource): kind: Literal["mock"] = "mock"
class File(Resource): kind: Literal["file"] = "file"
```

配套引用类型：`MockRef`、`FileRef`，通过 `ResourceUnion` 在场景里以 `dict[str, ResourceUnion]` 索引。

### Request

请求体定义（包含 `Request` 与 `RequestRef`），通过 `RequestUnion` 在 `Step` 里使用。

### Strategy 策略

所有策略继承 `StrategyBase`（含 `phase: StrategyPhase` 等元信息），按 `kind` 字段 discriminated union 区分。

#### Extract

```python
class Extract(StrategyBase):
    kind: Literal["extract"] = "extract"
    source: ExtractSource         # 提取源
    expression: str               # JSONPath 表达式
    target: str
    scope: Scope = Scope.SCENARIO
    default: Any | None
    required: bool = True
```

#### Assign

```python
class Assign(StrategyBase):
    kind: Literal["assign"] = "assign"
    source: Any                   # 字面量或模板
    target: str
    scope: Scope = Scope.SCENARIO
    default: Any | None
    required: bool = True
```

#### Assertion

```python
class Assertion(StrategyBase):
    kind: Literal["assertion"] = "assertion"
    target: str
    operator: AssertOperator
    expected: Any
    message: str | None
    soft: bool = False            # 软断言
```

### Setup / Teardown

场景级的前置与后置动作，分别通过 `Setup` / `SetupRef` 与 `Teardown` / `TeardownRef` 建模，配合 `SetupUnion` / `TeardownUnion` 在 `Config` 中使用。

### TimePolicy

```python
class TimePolicy(BaseModel): ...
class TimeoutPolicy(TimePolicy): ...
class RecordPolicy(TimePolicy): ...
TimePolicyUnion = Union[TimeoutPolicy, RecordPolicy]   # 实际形态见源码
```

### RetryPolicy

```python
class RetryPolicy(BaseModel):
    """用例级重试策略。"""
```

## 枚举类型

### StrategyPhase

策略执行阶段：

```python
class StrategyPhase(str, Enum):
    BEFORE_REQUEST = "before_request"
    AFTER_REQUEST = "after_request"
    VERIFYING = "verifying"
    TEARDOWN = "teardown"
```

### AssertOperator

断言操作符：

```python
class AssertOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    EXISTS = "exists"
    EMPTY = "empty"
    LENGTH_EQ = "length_eq"
    SCHEMA = "schema"
```

### Scope

变量作用域：

```python
class Scope(str, Enum):
    FRAMEWORK = "framework"
    SESSION = "session"
    SCENARIO = "scenario"
    STEP = "step"
    REQUEST = "request"
```

### FailurePolicy

策略失败处理策略（`gimbal.schema.strategy` 导出）。

### StepState

步骤状态枚举（`gimbal.schema.states`）：

```python
class StepState(str, Enum):
    """单步骤运行期状态。"""
    ...
```

## 联合类型 (Union)

使用 Pydantic v2 discriminated union（`kind` 字段做派发）：

```python
StepUnion = Annotated[
    Union[Step, StepRef],
    Field(discriminator="kind"),
]

StrategyUnion = Annotated[
    Union[Extract, Assign, Assertion, StrategyRef],
    Field(discriminator="kind"),
]

ApiUnion = Annotated[
    Union[Api, ApiRef],
    Field(discriminator="kind"),
]

RequestUnion = Annotated[
    Union[Request, RequestRef],
    Field(discriminator="kind"),
]

ResourceUnion = Annotated[
    Union[Resource, Mock, File, MockRef, FileRef],
    Field(discriminator="kind"),
]

SetupUnion = Annotated[
    Union[Setup, SetupRef],
    Field(discriminator="kind"),
]

TeardownUnion = Annotated[
    Union[Teardown, TeardownRef],
    Field(discriminator="kind"),
]

TimePolicyUnion = Annotated[
    Union[TimeoutPolicy, RecordPolicy],
    Field(discriminator="kind"),
]
```

## AuthSession（`gimbal.schema.auth`）

`AuthSession` 虽然是 schema 的一部分，但因为承载认证运行期状态，单独成文。详见 `auth.md`。要点速览：

```python
class AuthSession(BaseModel):
    # 认证地址和凭证
    url: str
    username: str
    password: str

    # Token 配置（认证后填充）
    expires_in: int | None
    token: str | None
    token_type: str = "Bearer"
    expires_at: datetime | None
    refresh_token: str | None    # 修复 #10：与 access_token 分开存储

    # 计算属性
    is_authenticated: bool       # 有 token 且未过期
    should_refresh: bool         # 距过期 < 5 分钟
    auth_header: str | None      # "Bearer xxx"；修复 #66 拒绝控制字符
    remaining_seconds: int | None

    # 方法
    def apply_token(self, token: str, expires_in: int | None = None) -> AuthSession
    def clear_token(self) -> AuthSession
    def is_same_credential(self, other: AuthSession) -> bool
    def clear_password(self) -> AuthSession  # 修复 #100
    @classmethod
    def from_dict(cls, data: dict) -> AuthSession
```

模块级私有工具函数：

```python
def _aware_utc(dt: datetime) -> datetime:
    """对带 tz 的 datetime 原样返回；对 naive datetime 补 UTC。

    解决 Pydantic v2 反序列化 ISO datetime 字符串默认得到 naive datetime 的问题，
    保证 `aware now() > naive expires_at` 不会抛 TypeError。
    """
```

`AuthSession` 关键语义（修复 #4）：

- `apply_token(token, expires_in=None)`：>`0` 显式重置 lifetime；`==0` 显式清空 lifetime；`None` 保留 `self.expires_in` 但 re-anchor `expires_at`。
- `apply_token` 早失败验证 token 中不含 ASCII 控制字符（修复 #R1）。
- `clear_token` 同时清空 `expires_in`，与新构造 session 状态一致（修复 #4）。

## 设计原则

1. **Discriminated Union**：使用 `Literal` + `Field(discriminator="kind")` 实现多态。所有 `*Union` 派生类都遵循这一约定。
2. **引用分离**：`*Ref` 类型用于引用未展开的对象（懒加载/外部资产），与具体类型（如 `Step`）并列在 `*Union` 中。
3. **不可变性优先**：除 `AuthSession` 等显式承担运行期状态的模型外，配置类（如 `BootstrapConfig`）使用 `frozen=True`。
4. **分层建模**：从 `Scenario` → `Step` → `Api`/`Request`/`Strategy`，层层细化，资源与认证配置由 `Config` 集中管理。
5. **运行期状态外移**：`Config.users` 中的 `AuthSession` 在 Bootstrap 阶段被解析后，token 状态迁移到 `AuthRegistry`；schema 层只保留静态描述（详见 `auth.md`）。
