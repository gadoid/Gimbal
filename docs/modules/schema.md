# Schema 模块

> 数据模型模块，定义所有 Pydantic 数据模型（Scenario、Step、Api、Strategy 等）

## 目录结构

```
gimbal/schema/
├── __init__.py
├── scenario.py    # Scenario, Suite, Meta, Config
├── step.py       # Step, StepRef
├── api.py        # Api, ApiRef
├── request.py    # Request, RequestRef
├── strategy.py   # Extract, Assign, Assertion, StrategyRef
├── resource.py   # Resource, Mock, File, MockRef, FileRef
├── auth.py       # AuthSession
├── ref.py        # RefBase
├── setup.py     # Setup, SetupRef
├── teardown.py   # Teardown, TeardownRef
├── timepolicy.py # TimePolicy, TimeoutPolicy, RecordPolicy
└── retrypolicy.py # RetryPolicy
```

## 核心模型

### Scenario

场景/用例模型：

```python
class Scenario(BaseModel):
    kind: Literal["scenario"] = "scenario"
    scenarioId: str
    meta: Meta                    # 用例元信息
    config: Config                # 执行配置
    resource: dict[str, ResourceUnion]  # 资源
    steps: list[StepUnion]       # 执行步骤
```

### Suite

测试套件：

```python
class Suite(BaseModel):
    kind: Literal["suite"] = "suite"
    suite: list[Scenario]        # scenario 集合
```

### Meta

用例元信息：

```python
class Meta(BaseModel):
    name: str                    # 用例名
    description: str              # 用例描述
    module: str                   # 业务模块
    priority: int                # 用例优先级
    author: str                  # 用例作者
    owner: str                   # 维护人
    tags: list[str]              # 用例标签
    version: str                 # 用例版本
    createTime: datetime         # 创建时间
    expire: bool                 # 过期标志
    requirementRef: list[RefBase]  # 需求关联
```

### Config

用例执行配置：

```python
class Config(BaseModel):
    setup: list[SetupUnion]           # 前置动作
    teardown: list[TeardownUnion]     # 后置动作
    serviceDict: dict[str, str]       # 服务与URL映射
    authDict: dict[str, dict[str, AuthSession]]  # 认证信息
    timePolicy: TimePolicyUnion       # 时间策略
    retry: RetryPolicy | None         # 重试策略
```

### Step

单步骤模型：

```python
class Step(BaseModel):
    kind: Literal["step"] = "step"
    api: ApiUnion                  # 接口信息
    request: RequestUnion          # 请求体
    strategy: list[StrategyUnion] # 策略集
```

### Api

HTTP API 定义：

```python
class Api(BaseModel):
    kind: Literal["api"] = "api"
    service: str                  # 服务名
    method: str                   # HTTP 方法
    path: str                     # 路径
    headers: dict | None          # 请求头
    timeout: float = 30.0         # 超时时间
```

### Strategy 策略

#### Extract

提取策略：

```python
class Extract(StrategyBase):
    kind: Literal["extract"] = "extract"
    source: ExtractSource         # 提取源
    expression: str               # JSONPath 表达式
    target: str                  # 目标 key
    scope: Scope = Scope.SCENARIO
    default: Any | None          # 默认值
    required: bool = True        # 是否必需
```

#### Assign

赋值策略：

```python
class Assign(StrategyBase):
    kind: Literal["assign"] = "assign"
    source: Any                  # 字面量或模板
    target: str                  # 目标路径
    scope: Scope = Scope.SCENARIO
    default: Any | None          # 默认值
    required: bool = True
```

#### Assertion

断言策略：

```python
class Assertion(StrategyBase):
    kind: Literal["assertion"] = "assertion"
    target: str                  # 断言目标
    operator: AssertOperator      # 比较操作符
    expected: Any                # 期望值
    message: str | None          # 失败信息
    soft: bool = False           # 软断言
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

### ExtractSource

提取源：

```python
class ExtractSource(str, Enum):
    RESPONSE_BODY = "response_body"
    RESPONSE_HEADER = "response_header"
    REQUEST_BODY = "request_body"
    REQUEST_HEADER = "request_header"
```

## 联合类型 (Union)

使用 Pydantic discriminated union：

```python
StepUnion = Annotated[
    Union[Step, StepRef],
    Field(discriminator="kind")
]

StrategyUnion = Annotated[
    Union[Extract, Assign, Assertion, StrategyRef],
    Field(discriminator="kind")
]

ApiUnion = Annotated[
    Union[Api, ApiRef],
    Field(discriminator="kind")
]
```

## 设计原则

1. **Discriminated Union**: 使用 `Literal` + `Field(discriminator="kind")` 实现多态
2. **引用分离**: `*Ref` 类型用于引用未展开的对象
3. **不可变性**: 大部分模型是不可变的（除 AuthSession 等运行时状态）
4. **分层建模**: 从 Scenario 到 Step 到 Api/Strategy，层层递进