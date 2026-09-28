# Schema 模块

静态描述层，使用 Pydantic 定义测试框架的核心数据模型。

> **调用形态**：`step.call = {protocol, ...协议自有字段}` 是**唯一**调用表达
> （v2.1 批次 F 定稿；历史 `step.api` 语法糖已退役，见文末「api→call 变更过程」）。

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
    │   ├── call (协议中立调用)
    │   ├── request (请求体)
    │   └── strategy (策略列表)
    │       ├── Extract (字段提取)
    │       ├── Assign (变量赋值)
    │       └── Assertion (断言)
```

### 2. Discriminated Union

使用 Pydantic 的 `Annotated[Union[...], Field(discriminator="kind")]` 实现类型安全的联合体：

```python
StrategyUnion = Annotated[
    Union[Extract, Assign, Assertion],
    Field(discriminator="kind")
]
```

序列化/反序列化时，Pydantic 自动根据 `kind` 字段选择正确的类型。

### 3. 扩展性

- 所有模型都支持 `kind` 字段用于类型识别
- 新增模型类型只需继承基类并声明 `kind`
- Union 类型便于未来扩展

> 历史上有过 `*Ref` 引用类型，已随资产引用机制移除（用例的唯一去向是平台数据库，ref 节点零生产者）。

---

## 模块结构总览

| 文件 | 说明 | 导出类 |
|------|------|--------|
| `states.py` | 步骤执行状态枚举 | `StepState` |
| `resource.py` | 资源模型 | `Resource`, `Mock`, `File`, `ResourceUnion` |
| `call.py` | 协议中立调用模型 | `Call` |
| `request.py` | 请求体模型 | `Request`, `RequestUnion` |
| `step.py` | 测试步骤模型 | `Step`, `StepUnion` |
| `strategy.py` | 策略模型 | `Scope`, `AssertOperator`, `StrategyPhase`, `FailurePolicy`, `ExtractSource`, `StrategyBase`, `Extract`, `Assign`, `Assertion`, `StrategyUnion` |
| `timepolicy.py` | 时间策略模型 | `TimePolicy`, `TimeoutPolicy`, `RecordPolicy`, `TimePolicyUnion` |
| `retrypolicy.py` | 重试策略模型 | `RetryPolicy` |
| `scenario.py` | 场景模型 | `Meta`, `Config`, `Scenario`, `Suite`, `RunUnion` |
| `setup.py` | 前置动作模型 | `Setup`, `SetupUnion` |
| `teardown.py` | 后置动作模型 | `Teardown`, `TeardownUnion` |

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

## 2. resource.py

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
| `path` | `str` | 是 | - | 路径 |

### ResourceUnion

资源联合类型，由 `Mock`, `File` 组成，通过 `kind` 字段区分。

---

## 3. call.py

### Call

协议中立调用模型（开放模型：`protocol` 之外的字段由各协议执行器解释校验，
注册新协议不需要改本文件）。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["call"]` | 是 | `"call"` | 类型标识 |
| `protocol` | `str` | 是 | - | 协议名（执行器注册表 ProtocolRegistry 的分派键） |
| http 常用字段 | — | — | - | `service` / `method` / `path` / `headers` / `timeout` 由 http 协议执行器（`protocols/builtin/http.py`）读取与校验 |

http 协议示例：

```python
Call(protocol="http", service="fin", method="POST", path="/api/x")
Call(protocol="grpc", service="user", method="GetUser")   # 自定义协议
```

协议内字段查询统一走 JSONPath（`gimbal/utils/jsonpath.py`），与
Extract/Assertion/Assign 同一套查询语言。

---

## 4. request.py

### Request

请求体模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["request"]` | 是 | `"request"` | 类型标识 |
| `body` | `Union[str, dict[str, Any], list[Any]]` | 否 | `{}` | 请求体内容（见下方"body 形态与策略可用性"） |

#### body 形态与策略可用性（阶段 1）

`body` 支持三种形态，框架按运行时类型自动分发到 httpx 的不同通道：

| body 形态 | 通道 | 隐式 Content-Type | 适用场景 |
|---|---|---|---|
| `dict` / `list` | `json=` | `application/json` | 常规 JSON API |
| `str` | `content=`（UTF-8 bytes） | 由 `call.headers.Content-Type` 控制 | text/xml、application/xml、text/plain 等原始文本 |

**str body 的注意事项**：

- **Content-Type**：str body 不带默认 Content-Type；httpx 会兜底为 `text/plain`。**建议在 `call.headers` 显式声明**（如 `Content-Type: application/xml`），否则 call.py 会输出 warning。
- **模板变量**：str body 里的 `${var.x}` 会被 `SpecResolver._resolve_nested` 正常替换（[_resolve_value](src/gimbal/context/resolver.py#L163) 天然支持 str）。
- **策略可用性**：str 没有可索引字段，下列策略在 str body 下行为降级：
  - `Extract("$.call.request.body.xxx")` → 返回 `None`（路径不存在）
  - `Extract("$.call.request.body")` → 返回完整 str（**唯一可用形式**）
  - `Assign("$.call.request.body.xxx", ...)` → 写无效
  - `Assign` 替换整个 body → **合法**，可以 str 替换 dict（反之亦然）
  - `Assertion("$.call.request.body.xxx", ...)` → `None` 比较

  阶段 1 不在 schema 层强制限制，由文档告知用户；阶段 2 拆 `RawRequest`/`JsonRequest`/`FormRequest` 子类后可通过 Pydantic validator 收紧。

### RequestUnion

请求体类型别名，现为单成员别名 `RequestUnion = Request`。

---

## 5. step.py

### Step

单步骤数据模型。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `kind` | `Literal["step"]` | 是 | 类型标识 |
| `call` | `Call` | 是 | 协议中立调用（唯一调用形态） |
| `request` | `Optional[RequestUnion]` | 否 | 当前步骤的请求体信息；非调用型协议步骤允许省略 |
| `strategy` | `list[StrategyUnion]` | 是 | 当前步骤需要执行的策略集 |
| `description` | `Optional[str]` | 否 | 步骤说明 |

### StepUnion

步骤类型别名，现为单成员别名 `StepUnion = Step`。

---

## 6. strategy.py

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

策略阶段枚举类，继承自 `str, Enum`（协议中立化后的中立名，value 沿用历史值；
历史同值别名 `BEFORE_REQUEST`/`AFTER_REQUEST` 已删除）。

| 枚举值 | 字符串值 | 说明 |
|--------|----------|------|
| `PREPARE` | `"before_request"` | 请求前阶段（SQL 注入数据、Assign 准备入参） |
| `EXTRACTING` | `"after_request"` | 请求后阶段（Extract 提取字段） |
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
| `kind` | `Literal["extract"]` | 是 | `"extract"` | 类型标识 |
| `source` | `ExtractSource` | 是 | - | 提取源 |
| `expression` | `str` | 是 | - | 提取路径（JSONPath，以 `$.call.*` 信封域为根） |
| `target` | `str` | 是 | - | 写入上下文中的字段名 |
| `scope` | `Scope` | 否 | `Scope.SCENARIO` | 提取后注入到的作用域 |
| `default` | `Optional[Any]` | 否 | `None` | 提取失败时的默认值 |
| `required` | `bool` | 否 | `True` | 提取失败是否抛出异常 |

### Assign

变量赋值策略，继承自 `StrategyBase`。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
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
| `kind` | `Literal["assertion"]` | 是 | `"assertion"` | 类型标识 |
| `target` | `str` | 是 | - | 断言的目标字段（JSONPath，如 `$.call.response.body.code`） |
| `operator` | `AssertOperator` | 是 | - | 断言比较操作符 |
| `expected` | `Any` | 否 | `None` | 期望值 |
| `message` | `Optional[str]` | 否 | `None` | 断言失败时的信息 |
| `soft` | `bool` | 否 | `False` | 是否为软断言 |

### StrategyUnion

策略联合类型，由 `Extract`, `Assign`, `Assertion` 组成，通过 `kind` 字段区分。

---

## 7. timepolicy.py

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

## 8. retrypolicy.py

### RetryPolicy

重试策略配置模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["retry_policy"]` | 是 | `"retry_policy"` | 类型标识 |
| `maxAttempts` | `int` | 否 | `1` | 最大尝试次数 |
| `backoffSeconds` | `float` | 否 | `20` | 退避基础时长（秒） |
| `retryOn` | `list[str]` | 否 | `[]` | 触发重试的条件标签列表（如 error code） |

---

## 9. scenario.py

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
| `requirementRef` | `list[str]` | 否 | 需求关联链接列表 |

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

## 10. setup.py

### Setup

前置动作模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["setup"]` | 是 | `"setup"` | 类型标识 |

### SetupUnion

前置动作类型别名，现为单成员别名 `SetupUnion = Setup`。

---

## 11. teardown.py

### Teardown

后置动作模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kind` | `Literal["teardown"]` | 是 | `"teardown"` | 类型标识 |

### TeardownUnion

后置动作类型别名，现为单成员别名 `TeardownUnion = Teardown`。

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
│   └── File
└── steps: list[StepUnion]
    └── Step
        ├── call: Call (protocol + 协议自有字段)
        ├── request: RequestUnion (Request)
        └── strategy: list[StrategyUnion]
            ├── Extract
            ├── Assign
            └── Assertion
```

---

## 使用示例

```python
from gimbal import (
    Scenario, Meta, Config,
    Step, Call, Request,
    Extract, Assertion, Assign,
    Scope, ExtractSource, AssertOperator, StrategyPhase,
    TimeoutPolicy, RetryPolicy,
    Mock, Setup, Teardown
)
from datetime import datetime

# 定义调用（http 协议）
call = Call(
    protocol="http",
    service="user-service",
    method="GET",
    path="/api/users/{id}",
    headers={"Authorization": "Bearer ${token}"},
    timeout=30,
)

# 定义请求
request = Request(body={})

# 定义策略 - Extract: 从响应中提取数据（call 信封域）
extract_token = Extract(
    name="extract_token",
    phase=StrategyPhase.EXTRACTING,
    source=ExtractSource.RESPONSE_BODY,
    expression="$.call.response.body.data.token",
    target="token",
    scope=Scope.SCENARIO,
    default=None,
    required=False
)

# 定义策略 - Assign: 准备入参
assign_user_id = Assign(
    name="assign_user_id",
    phase=StrategyPhase.PREPARE,
    source="${user_id}",
    target="path.id",
    scope=Scope.STEP
)

# 定义策略 - Assertion: 断言验证（call 信封域）
assert_status = Assertion(
    name="assert_status",
    phase=StrategyPhase.VERIFYING,
    target="$.call.response.status",
    operator=AssertOperator.EQ,
    expected=200,
    message="响应状态码不正确",
    soft=False
)

# 定义步骤
step = Step(
    call=call,
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
python -m gimbal.schema.resource
python -m gimbal.schema.call
python -m gimbal.schema.request
python -m gimbal.schema.step
python -m gimbal.schema.strategy
python -m gimbal.schema.timepolicy
python -m gimbal.schema.retrypolicy
python -m gimbal.schema.scenario
python -m gimbal.schema.setup
python -m gimbal.schema.teardown
```

---

## api→call 变更过程（历史记录）

本节是 `step.api` → `step.call` 迁移的唯一现行文档入口；历史计划文档
（`docs/superpowers/plans/`）是各阶段的时点存档，不再重复维护。

| 时间 | 事件 |
|------|------|
| v2.1 批次 F 定稿 | `call = {protocol, ...协议自有字段}` 定为所有协议统一的调用表达；执行器进入 api/call 双读期（api 为 HTTP 语法糖，Step 校验期归一化为 call） |
| 2026-09-27 | 协议中立化：`CallExchangeEvent` 统一调用证据信封（`$.call.*` scratch 根）；plate `Call` 镜像模型对齐 |
| 2026-09-28（批次 F 收口） | 引擎删除 `schema/api.py` 与 api 语法糖，`Step` 仅收 call（extra=forbid 拒收 api）；PG 存量 7 场景 65 步一次性迁移（`07831974`，含旧 scratch 路径改写）；平台后端 6 读点保留「call 优先、api 兜底」过渡双读 |
| 2026-09-28（本轮清理） | 过渡面全部退役：plate Step 仅收 call（api 输入显式拒绝）、`view_api`/`Call.from_api`/`_steps_to_call_form`/`_CALL_PATH_REWRITES` 删除；platform 视图渲染 call；前端 `stepCall()` 单读 call；旧 scratch 路径域（`$.response_body` 等）前端直产 `$.call.*`、引擎归一化与 plate 重写表退役 |

**旧 → 新对照**（存量文件迁移映射，机器可执行版本见
`scripts/migrate_legacy_case.py`）：

| 旧（api 形态 / scratch 域） | 新（call 形态 / 信封域） |
|---|---|
| `step.api = {kind:"api", service, method, path, headers, timeout}` | `step.call = {kind:"call", protocol:"http", service, method, path, headers, timeout}` |
| `$.response_body` / `$.response_body.x` | `$.call.response.body` / `$.call.response.body.x` |
| `$.response_status` | `$.call.response.status` |
| `$.response_headers` | `$.call.response.meta.headers` |
| `$.request_body` / `$.request_body.x` | `$.call.request.body` / `$.call.request.body.x` |
| `$.duration_ms` | `$.call.elapsed_ms` |

存量 api 形态用例文件可用 `python scripts/migrate_legacy_case.py <file>`
原地迁移（幂等）；plate `/convert` 对 api 形态步骤返回 400 并在错误信息中
指向本节。
