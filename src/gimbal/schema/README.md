# Schema 模块

静态描述层，使用 Pydantic 定义测试框架的核心数据模型。

## 设计理念

### 1. 层次化设计

Schema 层采用**自顶向下**的层次结构：

```
Scenario (场景)
├── Meta (元信息)
├── Config (配置)
│   ├── setup/teardown (前置/后置动作)
│   ├── timePolicy (时间策略)
│   └── retry (重试策略)
├── resource (资源)
│   ├── Mock (Mock 服务)
│   └── File (文件)
└── steps (步骤列表)
    ├── Step
    │   ├── api (API 定义)
    │   ├── request (请求体)
    │   └── strategy (策略列表)
    │       ├── Extract (字段提取)
    │       ├── Assign (变量赋值)
    │       └── Assertion (断言)
```

### 2. Discriminated Union

使用 Pydantic 的 `Annotated[Union[...], Field(discriminator="kind")]` 实现类型安全的联合体：

```python
StepUnion = Annotated[
    Union[Step, StepRef],
    Field(discriminator="kind")
]
```

序列化/反序列化时，Pydantic 自动根据 `kind` 字段选择正确的类型。

### 3. 引用机制

通过 `RefBase` 实现资产引用，支持：
- 懒加载：先引用，后解析
- 复用：同一资产可被多处引用
- 追踪：通过 `ref` 字段追踪资产来源

### 4. 扩展性

- 所有模型都支持 `kind` 字段用于类型识别
- 新增资产类型只需继承基类并声明 `kind`
- Union 类型便于未来扩展

---

## 模块结构总览

| 文件 | 说明 | 导出类 |
|------|------|--------|
| `states.py` | 步骤执行状态枚举 | `StepState` |
| `ref.py` | 引用基类 | `RefBase` |
| `resource.py` | 资源模型 | `Resource`, `Mock`, `File`, `MockRef`, `FileRef`, `ResourceUnion` |
| `api.py` | API 定义模型 | `Api`, `ApiRef`, `ApiUnion` |
| `request.py` | 请求体模型 | `Request`, `RequestRef`, `RequestUnion` |
| `step.py` | 测试步骤模型 | `Step`, `StepRef`, `StepUnion` |
| `strategy.py` | 策略模型 | `Scope`, `AssertOperator`, `StrategyPhase`, `FailurePolicy`, `ExtractSource`, `StrategyBase`, `Extract`, `Assign`, `Assertion`, `StrategyRef`, `StrategyUnion` |
| `timepolicy.py` | 时间策略模型 | `TimePolicy`, `TimeoutPolicy`, `RecordPolicy`, `TimePolicyUnion` |
| `retrypolicy.py` | 重试策略模型 | `RetryPolicy` |
| `scenario.py` | 场景模型 | `Meta`, `Config`, `Scenario` |
| `setup.py` | 前置动作模型 | `Setup`, `SetupRef`, `SetupUnion` |
| `teardown.py` | 后置动作模型 | `Teardown`, `TeardownRef`, `TeardownUnion` |

---

## 1. states.py

### StepState

步骤执行状态枚举类，继承自 `str, Enum`。

| 枚举值 | 字符串值 | 说明 |
|--------|----------|------|
| `PENDING` | `"pending"` | 等待执行 |
| `RUNNING` | `"running"` | 执行中 |
| `PASSED` | `"passed"` | 执行成功 |
| `FAILED` | `"failed"` | 执行失败 |
| `SKIPPED` | `"skipped"` | 已跳过 |

---

## 2. ref.py

### RefBase

引用基类，用于实现对象引用功能。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ref` | `str` | 是 | 引用标识 |

---

## 3. resource.py

### Resource

资源基类。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | 是 | 资源名称 |

### Mock

Mock 服务资源，继承自 `Resource`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | `str` | 是 | - | 资源名称（继承自 Resource） |
| `kind` | `Literal["mock"]` | 是 | `"mock"` | 类型标识 |
| `image` | `str` | 是 | - | 容器镜像 |
| `config` | `dict[str, Any]` | 是 | - | 服务配置 |
| `portMapping` | `dict[int, int]` | 是 | - | 端口映射 |

### File

文件资源，继承自 `Resource`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | `str` | 是 | - | 资源名称（继承自 Resource） |
| `kind` | `Literal["file"]` | 是 | `"file"` | 类型标识 |
| `path` | `str` | 是 | - | 路径或 ref |

### MockRef

Mock 资源引用，继承自 `RefBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `ref` | `str` | 是 | - | 引用标识（继承自 RefBase） |
| `kind` | `Literal["mock_ref"]` | 是 | `"mock_ref"` | 类型标识 |

### FileRef

文件资源引用，继承自 `RefBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `ref` | `str` | 是 | - | 引用标识（继承自 RefBase） |
| `kind` | `Literal["file_ref"]` | 是 | `"file_ref"` | 类型标识 |

### ResourceUnion

资源联合类型，由 `Mock`, `MockRef`, `File`, `FileRef` 组成，通过 `kind` 字段区分。

---

## 4. api.py

### Api

API 定义模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["api"]` | 是 | `"api"` | 类型标识 |
| `service` | `str` | 是 | - | 服务名称 |
| `method` | `Literal["GET", "POST", "PUT", "DELETE", "PATCH"]` | 是 | - | HTTP 方法 |
| `path` | `str` | 是 | - | 请求路径 |
| `headers` | `dict[str, str]` | 否 | `{}` | 请求头字典 |
| `timeout` | `float` | 否 | `30` | 超时时间（秒） |

### ApiRef

API 引用，继承自 `RefBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `ref` | `str` | 是 | - | 引用标识（继承自 RefBase） |
| `kind` | `Literal["api_ref"]` | 是 | `"api_ref"` | 类型标识 |

### ApiUnion

API 联合类型，由 `Api`, `ApiRef` 组成，通过 `kind` 字段区分。

---

## 5. request.py

### Request

请求体模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["request"]` | 是 | `"request"` | 类型标识 |
| `body` | `dict[str, Any]` | 否 | `{}` | 请求体内容 |

### RequestRef

请求引用，继承自 `RefBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `ref` | `str` | 是 | - | 引用标识（继承自 RefBase） |
| `kind` | `Literal["request_ref"]` | 是 | `"request_ref"` | 类型标识 |

### RequestUnion

请求联合类型，由 `Request`, `RequestRef` 组成，通过 `kind` 字段区分。

---

## 6. step.py

### Step

单步骤数据模型。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `kind` | `Literal["step"]` | 是 | 类型标识 |
| `api` | `ApiUnion` | 是 | 当前步骤的接口请求信息 |
| `request` | `RequestUnion` | 是 | 当前步骤的请求体信息 |
| `strategy` | `list[StrategyUnion]` | 是 | 当前步骤需要执行的策略集 |

### StepRef

步骤引用，继承自 `RefBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `ref` | `str` | 是 | - | 引用标识（继承自 RefBase） |
| `kind` | `Literal["step_ref"]` | 是 | `"step_ref"` | 类型标识 |

### StepUnion

步骤联合类型，由 `Step`, `StepRef` 组成，通过 `kind` 字段区分。

---

## 7. strategy.py

### Scope

作用域枚举类，继承自 `str, Enum`。

| 枚举值 | 字符串值 | 说明 |
|--------|----------|------|
| `FRAMEWORK` | `"framework"` | 框架级别 |
| `SESSION` | `"session"` | 会话级别 |
| `SCENARIO` | `"scenario"` | 场景级别 |
| `STEP` | `"step"` | 步骤级别 |
| `REQUEST` | `"request"` | 请求级别 |

### AssertOperator

断言操作符枚举类，继承自 `str, Enum`。

| 枚举值 | 字符串值 | 说明 |
|--------|----------|------|
| `EQ` | `"eq"` | 等于 |
| `NE` | `"ne"` | 不等于 |
| `GT` | `"gt"` | 大于 |
| `GTE` | `"gte"` | 大于等于 |
| `LT` | `"lt"` | 小于 |
| `LTE` | `"lte"` | 小于等于 |
| `IN` | `"in"` | 包含（在列表中） |
| `NOT_IN` | `"not_in"` | 不包含 |
| `CONTAINS` | `"contains"` | 包含（字符串） |
| `NOT_CONTAINS` | `"not_contains"` | 不包含 |
| `EXISTS` | `"exists"` | 存在 |
| `EMPTY` | `"empty"` | 为空 |
| `LENGTH_EQ` | `"length_eq"` | 长度等于 |
| `SCHEMA` | `"schema"` | 符合 schema |

### StrategyPhase

策略阶段枚举类，继承自 `str, Enum`。

| 枚举值 | 字符串值 | 说明 |
|--------|----------|------|
| `BEFORE_REQUEST` | `"before_request"` | 请求前阶段（SQL 注入数据、Assign 准备入参） |
| `AFTER_REQUEST` | `"after_request"` | 请求后阶段（Extract 提取字段） |
| `VERIFYING` | `"verifying"` | 验证阶段（Assertion、DBChecker） |
| `TEARDOWN` | `"teardown"` | 清理阶段（SQL 清理、Chaos 恢复） |

### FailurePolicy

失败处理策略枚举类，继承自 `str, Enum`。

| 枚举值 | 字符串值 | 说明 |
|--------|----------|------|
| `ABORT` | `"abort"` | 中止整个 step |
| `CONTINUE` | `"continue"` | 记录错误但继续 |
| `WARN` | `"warn"` | 仅警告 |
| `RETRY` | `"retry"` | 配合 retry 字段重试 |

### ExtractSource

提取源枚举类，继承自 `str, Enum`。

| 枚举值 | 字符串值 | 说明 |
|--------|----------|------|
| `RESPONSE_BODY` | `"response_body"` | 响应 body |
| `RESPONSE_HEADER` | `"response_header"` | 响应 header |
| `REQUEST_BODY` | `"request_body"` | 请求 body |
| `REQUEST_HEADER` | `"request_header"` | 请求 header |

### StrategyBase

策略基类。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | `Optional[str]` | 否 | `None` | 策略名称 |
| `phase` | `Optional[StrategyPhase]` | 否 | `None` | 处理的阶段 |
| `order` | `int` | 否 | `0` | 执行顺序 |
| `enabled` | `bool` | 否 | `True` | 是否启用 |
| `onFailure` | `FailurePolicy` | 否 | `FailurePolicy.ABORT` | 失败处理策略 |
| `timeout` | `Optional[float]` | 否 | `None` | 策略执行超时时间（秒） |
| `tags` | `List[str]` | 否 | `[]` | 标签列表 |

### Extract

字段提取策略，继承自 `StrategyBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | `Optional[str]` | 否 | `None` | 策略名称（继承自 StrategyBase） |
| `phase` | `Optional[StrategyPhase]` | 否 | `None` | 处理阶段（继承自 StrategyBase） |
| `order` | `int` | 否 | `0` | 执行顺序（继承自 StrategyBase） |
| `enabled` | `bool` | 否 | `True` | 是否启用（继承自 StrategyBase） |
| `onFailure` | `FailurePolicy` | 否 | `FailurePolicy.ABORT` | 失败处理策略（继承自 StrategyBase） |
| `timeout` | `Optional[float]` | 否 | `None` | 超时时间（继承自 StrategyBase） |
| `tags` | `List[str]` | 否 | `[]` | 标签（继承自 StrategyBase） |
| `kind` | `Literal["extract"]` | 是 | `"extract"` | 类型标识 |
| `source` | `ExtractSource` | 是 | - | 提取源 |
| `expression` | `str` | 是 | - | 提取路径（JSONPath 或类似表达式） |
| `target` | `str` | 是 | - | 写入上下文中的字段名 |
| `scope` | `Scope` | 否 | `Scope.SCENARIO` | 提取后注入到的作用域 |
| `default` | `Optional[Any]` | 否 | `None` | 提取失败时的默认值 |
| `required` | `bool` | 否 | `True` | 提取失败是否抛出异常 |

### Assign

变量赋值策略，继承自 `StrategyBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | `Optional[str]` | 否 | `None` | 策略名称（继承自 StrategyBase） |
| `phase` | `Optional[StrategyPhase]` | 否 | `None` | 处理阶段（继承自 StrategyBase） |
| `order` | `int` | 否 | `0` | 执行顺序（继承自 StrategyBase） |
| `enabled` | `bool` | 否 | `True` | 是否启用（继承自 StrategyBase） |
| `onFailure` | `FailurePolicy` | 否 | `FailurePolicy.ABORT` | 失败处理策略（继承自 StrategyBase） |
| `timeout` | `Optional[float]` | 否 | `None` | 超时时间（继承自 StrategyBase） |
| `tags` | `List[str]` | 否 | `[]` | 标签（继承自 StrategyBase） |
| `kind` | `Literal["assign"]` | 是 | `"assign"` | 类型标识 |
| `source` | `Any` | 是 | - | 值或路径 |
| `target` | `str` | 是 | - | 模板路径 |
| `scope` | `Scope` | 否 | `Scope.SCENARIO` | 作用域 |
| `default` | `Optional[Any]` | 否 | `None` | 注入失败时的默认值 |
| `required` | `bool` | 否 | `True` | 注入失败是否抛出异常 |

### Assertion

断言策略，继承自 `StrategyBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | `Optional[str]` | 否 | `None` | 策略名称（继承自 StrategyBase） |
| `phase` | `Optional[StrategyPhase]` | 否 | `None` | 处理阶段（继承自 StrategyBase） |
| `order` | `int` | 否 | `0` | 执行顺序（继承自 StrategyBase） |
| `enabled` | `bool` | 否 | `True` | 是否启用（继承自 StrategyBase） |
| `onFailure` | `FailurePolicy` | 否 | `FailurePolicy.ABORT` | 失败处理策略（继承自 StrategyBase） |
| `timeout` | `Optional[float]` | 否 | `None` | 超时时间（继承自 StrategyBase） |
| `tags` | `List[str]` | 否 | `[]` | 标签（继承自 StrategyBase） |
| `kind` | `Literal["assertion"]` | 是 | `"assertion"` | 类型标识 |
| `target` | `str` | 是 | - | 断言的目标字段 |
| `operator` | `AssertOperator` | 是 | - | 断言比较操作符 |
| `expected` | `Any` | 否 | `None` | 期望值 |
| `message` | `Optional[str]` | 否 | `None` | 断言失败时的信息 |
| `soft` | `bool` | 否 | `False` | 是否为软断言 |

### StrategyRef

策略引用，继承自 `RefBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `ref` | `str` | 是 | - | 引用标识（继承自 RefBase） |
| `kind` | `Literal["strategy_ref"]` | 是 | `"strategy_ref"` | 类型标识 |

### StrategyUnion

策略联合类型，由 `Extract`, `Assign`, `Assertion`, `StrategyRef` 组成，通过 `kind` 字段区分。

---

## 8. timepolicy.py

### TimePolicy

时间策略基类。

（无字段）

### TimeoutPolicy

超时模式时间策略，继承自 `TimePolicy`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["timeout"]` | 是 | `"timeout"` | 类型标识 |
| `seconds` | `int` | 是 | - | 超时阈值（秒） |

### RecordPolicy

记录模式时间策略，继承自 `TimePolicy`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["record"]` | 是 | `"record"` | 类型标识 |

### TimePolicyUnion

时间策略联合类型，由 `TimeoutPolicy`, `RecordPolicy` 组成，通过 `kind` 字段区分。

---

## 9. retrypolicy.py

### RetryPolicy

重试策略配置模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["retry_policy"]` | 是 | `"retry_policy"` | 类型标识 |
| `maxAttempts` | `int` | 否 | `1` | 最大尝试次数 |
| `backoffSeconds` | `float` | 否 | `20` | 退避基础时长（秒） |
| `retryOn` | `list[str]` | 否 | `[]` | 触发重试的条件标签列表（如 error code） |

---

## 10. scenario.py

### Meta

用例信息配置模型。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | 是 | 用例名称 |
| `description` | `str` | 是 | 用例信息描述 |
| `module` | `str` | 是 | 用例所属的业务模块 |
| `priority` | `int` | 是 | 用例优先级 |
| `author` | `str` | 是 | 用例作者 |
| `owner` | `str` | 是 | 维护人/执行人 |
| `tags` | `list[str]` | 是 | 用例标签列表 |
| `version` | `str` | 否 | 用例版本号 |
| `createTime` | `datetime` | 否 | 创建时间 |
| `expire` | `bool` | 否 | 过期标志位 |
| `requirementRef` | `list[RefBase]` | 否 | 需求关联链接列表 |

### Config

用例执行配置模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `setup` | `list[SetupUnion]` | 否 | `[]` | 用例前置动作列表 |
| `teardown` | `list[TeardownUnion]` | 否 | `[]` | 用例后置动作列表 |
| `services` | `dict[str, str]` | 否 | - | 服务与 URL 映射关系字典 |
| `users` | `dict[str, Any]` | 否 | - | 认证信息字典 |
| `timePolicy` | `TimePolicyUnion` | 否 | `RecordPolicy()` | 时间处理策略（超时检查或耗时记录） |
| `retry` | `Optional[RetryPolicy]` | 否 | `None` | 重试策略配置 |

### Scenario

完整场景数据模型。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `scenarioId` | `str` | 是 | 场景/用例 ID（建议前缀为 `sc`） |
| `meta` | `Meta` | 是 | 用例的元信息 |
| `config` | `Config` | 是 | 本次执行的配置信息 |
| `resource` | `dict[str, ResourceUnion]` | 否 | 用例需要执行的资源字典 |
| `steps` | `list[StepUnion]` | 是 | 具体执行步骤列表 |

---

## 11. setup.py

### Setup

前置动作模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["setup"]` | 是 | `"setup"` | 类型标识 |

### SetupRef

前置动作引用，继承自 `RefBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `ref` | `str` | 是 | - | 引用标识（继承自 RefBase） |
| `kind` | `Literal["setup_ref"]` | 是 | `"setup_ref"` | 类型标识 |

### SetupUnion

前置动作联合类型，由 `Setup`, `SetupRef` 组成，通过 `kind` 字段区分。

---

## 12. teardown.py

### Teardown

后置动作模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["teardown"]` | 是 | `"teardown"` | 类型标识 |

### TeardownRef

后置动作引用，继承自 `RefBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `ref` | `str` | 是 | - | 引用标识（继承自 RefBase） |
| `kind` | `Literal["teardown_ref"]` | 是 | `"teardown_ref"` | 类型标识 |

### TeardownUnion

后置动作联合类型，由 `Teardown`, `TeardownRef` 组成，通过 `kind` 字段区分。

---

## 模型关系图

```
Scenario
├── meta: Meta
├── config: Config
│   ├── setup: list[SetupUnion]
│   ├── teardown: list[TeardownUnion]
│   ├── timePolicy: TimePolicyUnion
│   └── retry: RetryPolicy
├── resource: dict[str, ResourceUnion]
│   ├── Mock
│   ├── MockRef
│   ├── File
│   └── FileRef
└── steps: list[StepUnion]
    └── Step
        ├── api: ApiUnion
        │   ├── Api
        │   └── ApiRef
        ├── request: RequestUnion
        │   ├── Request
        │   └── RequestRef
        └── strategy: list[StrategyUnion]
            ├── Extract
            ├── Assign
            ├── Assertion
            └── StrategyRef
```

---

## 使用示例

```python
from gimbal import (
    Scenario, Meta, Config,
    Step, Api, Request,
    Extract, Assertion, Assign,
    Scope, ExtractSource, AssertOperator, StrategyPhase,
    TimeoutPolicy, RetryPolicy,
    Mock, Setup, Teardown
)
from datetime import datetime

# 定义 API
api = Api(
    service="user-service",
    method="GET",
    path="/api/users/{id}",
    headers={"Authorization": "Bearer ${token}"},
    timeout=30
)

# 定义请求
request = Request(body={})

# 定义策略 - Extract: 从响应中提取数据
extract_token = Extract(
    name="extract_token",
    phase=StrategyPhase.AFTER_REQUEST,
    source=ExtractSource.RESPONSE_BODY,
    expression="$.data.token",
    target="token",
    scope=Scope.SCENARIO,
    default=None,
    required=False
)

# 定义策略 - Assign: 准备入参
assign_user_id = Assign(
    name="assign_user_id",
    phase=StrategyPhase.BEFORE_REQUEST,
    source="${user_id}",
    target="path.id",
    scope=Scope.STEP
)

# 定义策略 - Assertion: 断言验证
assert_status = Assertion(
    name="assert_status",
    phase=StrategyPhase.VERIFYING,
    target="response.status",
    operator=AssertOperator.EQ,
    expected=200,
    message="响应状态码不正确",
    soft=False
)

# 定义步骤
step = Step(
    api=api,
    request=request,
    strategy=[extract_token, assign_user_id, assert_status]
)

# 定义前置动作
setup = Setup()

# 定义后置动作
teardown = Teardown()

# 定义元信息
meta = Meta(
    name="获取用户信息",
    description="测试获取用户信息接口",
    module="user",
    priority=1,
    author="tester",
    owner="developer",
    tags=["smoke", "regression"],
    version="1.0.0",
    createTime=datetime.now(),
    expire=False,
    requirementRef=[]
)

# 定义配置
config = Config(
    setup=[setup],
    teardown=[teardown],
    services={"user-service": "http://localhost:8080"},
    users={"token": "test_token_123"},
    timePolicy=TimeoutPolicy(seconds=60),
    retry=RetryPolicy(maxAttempts=3, backoffSeconds=30, retryOn=["500", "502"])
)

# 定义资源
resource = {
    "mock1": Mock(
        name="mock1",
        image="nginx:latest",
        config={"port": 80},
        portMapping={80: 8080}
    )
}

# 定义场景
scenario = Scenario(
    scenarioId="sc_001",
    meta=meta,
    config=config,
    resource=resource,
    steps=[step]
)

# 序列化为字典
print(scenario.model_dump())
```

---

## 运行测试

```bash
# 使用 -m 方式运行模块测试
python -m gimbal.schema.states
python -m gimbal.schema.ref
python -m gimbal.schema.resource
python -m gimbal.schema.api
python -m gimbal.schema.request
python -m gimbal.schema.step
python -m gimbal.schema.strategy
python -m gimbal.schema.timepolicy
python -m gimbal.schema.retrypolicy
python -m gimbal.schema.scenario
python -m gimbal.schema.setup
python -m gimbal.schema.teardown
```
