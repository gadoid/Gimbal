# Framework 模块详解

本文档详细说明 `framework.py` 中所有类的设计、功能和协作关系。

---

## 目录

1. [状态机层](#1-状态机层)
2. [Schema 层（Pydantic 模型）](#2-schema-层pydantic-模型)
3. [上下文层](#3-上下文层)
4. [事件层](#4-事件层)
5. [变量插值](#5-变量插值)
6. [路径操作](#6-路径操作)
7. [处理器层](#7-处理器层)
8. [分发器](#8-分发器)
9. [HTTP 客户端](#9-http-客户端)
10. [状态机执行器](#10-状态机执行器)
11. [插件层](#11-插件层)
12. [顶层 Runner](#12-顶层-runner)

---

## 1. 状态机层

### `StepState` 枚举 ([line 41-46](framework.py#L41-L46))

定义步骤执行的 5 个阶段状态：

| 状态 | 说明 | 可执行动作 |
|------|------|-----------|
| `BEFORE_REQUEST` | 请求前准备 | sql, extract, assign |
| `REQUESTING` | 发送 HTTP 请求 | - |
| `AFTER_REQUEST` | 请求后处理 | sql, extract |
| `VERIFYING` | 响应验证 | assert |
| `TEARDOWN` | 清理资源 | sql |

**约束定义：** `ALLOWED_ACTIONS_BY_STATE` ([line 146-151](framework.py#L146-L151))

```python
ALLOWED_ACTIONS_BY_STATE = {
    "before_request": {"sql", "extract", "assign"},
    "after_request": {"sql", "extract"},
    "verify": {"assert"},
    "teardown": {"sql"},
}
```

---

## 2. Schema 层（Pydantic 模型）

### `BaseAction` ([line 53-57](framework.py#L53-L57))

所有动作的基类：

```python
class BaseAction(BaseModel):
    type: str                          # 动作类型标识
    name: str | None = None            # 动作名称（可选）
    on_failure: Literal["abort", "continue", "ignore", "accumulate"] | None = None  # 失败处理策略
```

**失败处理策略：**
- `abort` - 立即终止执行
- `continue` - 继续执行下一步
- `ignore` - 忽略失败
- `accumulate` - 累积失败继续执行（默认）

---

### `SqlAction` ([line 59-74](framework.py#L59-L74))

SQL 执行动作：

```python
class SqlAction(BaseAction):
    type: Literal["sql"]
    from_: str | None = Field(None, alias="from")      # SQL 模板来源
    inline: str | None = None                          # 内联 SQL 字符串
    inline_list: list[str] | None = None              # SQL 列表
    datasource: str = "default"                        # 数据源名称
    params: dict = {}                                  # 查询参数
    in_transaction: bool = False                      # 是否在事务中执行
    on_failure: Literal["abort", "continue", "ignore"] = "abort"
```

**约束：** `from_`、`inline`、`inline_list` 三者必须且仅能设置一个。

---

### `ExtractAction` ([line 77-90](framework.py#L77-L90))

数据提取动作：

```python
class ExtractAction(BaseAction):
    type: Literal["extract"]
    key: str                                      # 提取后存入的变量名
    from_: Literal["response", "database", "variable"] = Field(alias="from")  # 数据来源
    path: str | None = None                       # JSONPath 路径
    sql: str | None = None                        # SQL 查询（from=database 时）
    expression: str | None = None                 # 表达式（from=variable 时）
    params: dict = {}
    transform: str | None = None                  # 值转换（to_int, to_str, lower）
    default: Any = None                           # 提取失败默认值
    required: bool = True                         # 是否必须提取到值
    on_failure: Literal["abort", "continue", "ignore"] = "abort"
```

---

### `AssignAction` ([line 92-99](framework.py#L92-L99))

变量赋值动作：

```python
class AssignAction(BaseAction):
    type: Literal["assign"]
    target: Literal["body", "headers", "query", "path_params"]  # 赋值目标位置
    path: str | None = None                       # 目标路径
    value: Any = None                             # 直接值
    expression: str | None = None                 # 表达式
    fields: dict | None = None                    # 批量字段赋值
    on_failure: Literal["abort", "continue", "ignore"] = "abort"
```

---

### `AssertRule` ([line 102-107](framework.py#L102-L107))

断言规则：

```python
class AssertRule(BaseModel):
    path: str | None = None                       # 验证路径
    op: str = "eq"                               # 操作符
    expected: Any = None                          # 期望值
    message: str | None = None                   # 失败消息
```

---

### `AssertAction` ([line 109-121](framework.py#L109-L121))

断言验证动作：

```python
class AssertAction(BaseAction):
    type: Literal["assert"]
    target: Literal["response", "database", "variable", "request_outcome"]  # 断言目标
    from_: str | None = Field(None, alias="from")
    rules: list[AssertRule] | None = None        # 断言规则列表
    path: str | None = None                       # 简化路径
    op: str | None = None                        # 简化操作符
    expected: Any = None                         # 简化期望值
    sql: str | None = None                       # SQL（target=database 时）
    status_code: int | dict | None = None        # 状态码断言
    time_ms: dict | None = None                  # 响应时间断言
    on_failure: Literal["abort", "continue", "ignore", "accumulate"] = "accumulate"
```

---

### `Action` 联合类型 ([line 123-126](framework.py#L123-L126))

```python
Action = Annotated[
    Union[SqlAction, ExtractAction, AssignAction, AssertAction],
    Field(discriminator="type"),
]
```

使用 Pydantic 的 `discriminator` 实现多态解析，根据 `type` 字段自动识别具体类型。

---

### `ApiSpec` / `RequestSpec` ([line 133-144](framework.py#L133-L144))

API 和请求规格：

```python
class ApiSpec(BaseModel):
    method: str                                  # HTTP 方法
    path: str                                   # 请求路径
    headers: dict = {}                          # 请求头

class RequestSpec(BaseModel):
    body: dict = {}                             # 请求体
    headers: dict = {}                          # 请求头（可覆盖）
    query: dict = {}                            # URL 查询参数
    path_params: dict = {}                      # 路径参数
```

---

### `Step` ([line 154-187](framework.py#L154-L187))

测试步骤模型：

```python
class Step(BaseModel):
    action_name: str                            # 步骤名称
    enabled: bool = True                        # 是否启用
    api: ApiSpec                                # API 规格
    request: RequestSpec = RequestSpec()        # 请求内容
    before_request: list[Action] = []           # 请求前动作
    after_request: list[Action] = []            # 请求后动作
    verify: list[Action] = []                   # 验证动作
    teardown: list[Action] = []                 # 清理动作
```

**关键方法：**
- `actions_at(state)` - 获取指定状态的 action 列表
- `validate_action_states()` - Pydantic 验证器，检查 action 类型是否在允许列表中

---

### `Scenario` ([line 190-193](framework.py#L190-L193))

场景模型：

```python
class Scenario(BaseModel):
    scenario_id: str                            # 场景 ID
    flow: list[Step]                            # 步骤列表
```

---

## 3. 上下文层

### `FailureRecord` ([line 199-207](framework.py#L199-L207))

失败记录：

```python
@dataclass
class FailureRecord:
    state: StepState                            # 发生时的状态
    layer: str                                  # 层级："machine" / "assertion" / "framework"
    severity: str                               # 严重性："fatal" / "error" / "warning"
    source: str                                 # 失败来源
    message: str                                 # 失败消息
    detail: dict = field(default_factory=dict)  # 详细信息
```

---

### `AssertionResult` ([line 209-218](framework.py#L209-L218))

断言结果：

```python
@dataclass
class AssertionResult:
    target: str                                  # 断言目标
    path: str | None                            # 验证路径
    op: str                                      # 操作符
    expected: Any                               # 期望值
    actual: Any                                 # 实际值
    passed: bool                                # 是否通过
    message: str | None = None                   # 消息
```

---

### `ExecutionContext` ([line 220-249](framework.py#L220-L249))

执行上下文，贯穿整个执行过程的数据容器：

```python
@dataclass
class ExecutionContext:
    # 静态身份
    scenario_id: str
    action_name: str
    step_index: int

    # 当前执行状态
    current_state: StepState | None = None

    # 输入数据
    api: ApiSpec | None = None
    request: RequestSpec | None = None

    # 累积数据
    variables: dict = field(default_factory=dict)     # 变量池
    response: dict | None = None                      # HTTP 响应体
    response_status: int | None = None               # HTTP 状态码
    state_timings: dict = field(default_factory=dict) # 各状态耗时
    request_outcome: str = "pending"                   # 请求结果

    # 副作用记录
    sql_executions: list[dict] = field(default_factory=list)
    assignments: list[dict] = field(default_factory=list)
    extracts: dict = field(default_factory=dict)
    assertions: list[AssertionResult] = field(default_factory=list)

    # 失败累积
    failures: list[FailureRecord] = field(default_factory=list)
```

---

## 4. 事件层

### 事件类

| 事件类 | 定义位置 | 触发时机 |
|--------|----------|----------|
| `StateEntered` | [line 255-259](framework.py#L255-L259) | 进入某个状态时 |
| `StateExited` | [line 262-268](framework.py#L262-L268) | 退出某个状态时 |
| `ActionStarted` | [line 270-274](framework.py#L270-L274) | 动作开始执行时 |
| `ActionFinished` | [line 276-283](framework.py#L276-L283) | 动作执行完成时 |
| `StepFinished` | [line 285-289](framework.py#L285-L289) | 步骤执行完成时 |

---

### `EventBus` ([line 291-304](framework.py#L291-L304))

事件总线，实现发布/订阅模式：

```python
class EventBus:
    def __init__(self):
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def on(self, event_type: type, handler: Callable):
        """订阅事件"""
        self._handlers[event_type].append(handler)

    def emit(self, event):
        """发布事件"""
        for handler in self._handlers[type(event)]:
            try:
                handler(event)
            except Exception as e:
                print(f"  [bus] plugin handler {handler.__qualname__} failed: {e}")
```

**特性：** 插件处理异常不会阻断主流程，仅打印警告。

---

## 5. 变量插值

### `interpolate()` ([line 313-327](framework.py#L313-L327))

递归进行 `${var}` 替换：

```python
def interpolate(value: Any, variables: dict) -> Any:
    """递归地对 dict/list/str 做 ${var} 替换"""
    # 完全匹配 ${xxx} → 保留原值类型
    # 部分匹配 → 字符串替换
```

**规则：**
- `${var}` 形式：直接返回变量原始类型值
- 部分包含 `${var}`：替换为字符串

---

## 6. 路径操作

### `get_by_path()` ([line 334-354](framework.py#L334-L354))

简化版 JSONPath 取值：

```python
def get_by_path(data: Any, path: str) -> Any:
    """支持 $.a.b / a.b / a[0].b"""
```

---

### `set_by_path()` ([line 357-365](framework.py#L357-L365))

简化版路径设值：

```python
def set_by_path(data: dict, path: str, value: Any):
    """仅支持 a.b.c 形式"""
```

---

## 7. 处理器层

### `ActionHandler` 抽象基类 ([line 372-374](framework.py#L372-L374))

```python
class ActionHandler(ABC):
    @abstractmethod
    def handle(self, action: Action, ctx: ExecutionContext) -> None: ...
```

---

### `SqlHandler` ([line 377-402](framework.py#L377-L402))

SQL 执行处理器：

```python
class SqlHandler(ActionHandler):
    def __init__(self, mock_db: dict):
        self.mock_db = mock_db

    def handle(self, action: SqlAction, ctx: ExecutionContext):
        sqls = self._resolve(action, ctx)        # 获取 SQL 列表
        for sql in sqls:
            interpolated = interpolate(sql, ctx.variables)
            print(f"      [sql] EXECUTE: {interpolated}")
            ctx.sql_executions.append({...})    # 记录执行
```

---

### `ExtractHandler` ([line 405-457](framework.py#L405-L457))

数据提取处理器：

```python
class ExtractHandler(ActionHandler):
    def handle(self, action: ExtractAction, ctx: ExecutionContext):
        # 根据 from_ 来源获取值
        if action.from_ == "response":
            value = get_by_path(ctx.response, action.path)
        elif action.from_ == "database":
            value = self._mock_query(sql)
        elif action.from_ == "variable":
            value = action.expression

        # 值转换
        if action.transform:
            value = self._transform(value, action.transform)

        # 存入变量池
        ctx.variables[action.key] = value
        ctx.extracts[action.key] = {...}
```

**支持的 transform：** `to_int`, `to_str`, `lower`

---

### `AssignHandler` ([line 460-493](framework.py#L460-L493))

变量赋值处理器：

```python
class AssignHandler(ActionHandler):
    def handle(self, action: AssignAction, ctx: ExecutionContext):
        target = self._get_target(action.target, ctx.request)

        if action.fields:
            # 批量赋值 {path: value, ...}
            for path, raw_val in action.fields.items():
                value = interpolate(raw_val, ctx.variables)
                set_by_path(target, path, value)
        else:
            # 单值赋值
            value = self._compute_value(action, ctx)
            set_by_path(target, action.path, value)

        ctx.assignments.append({...})
```

**target 可选值：** `body`, `headers`, `query`, `path_params`

---

### `AssertHandler` ([line 496-584](framework.py#L496-L584))

断言处理器：

```python
class AssertHandler(ActionHandler):
    OPS = {
        "eq": lambda a, e: a == e,
        "ne": lambda a, e: a != e,
        "gt": lambda a, e: a > e,
        "gte": lambda a, e: a >= e,
        "lt": lambda a, e: a < e,
        "lte": lambda a, e: a <= e,
        "in": lambda a, e: a in e,
        "not_in": lambda a, e: a not in e,
        "contains": lambda a, e: e in a,
        "is_null": lambda a, e: a is None,
        "not_null": lambda a, e: a is not None,
    }

    def handle(self, action: AssertAction, ctx: ExecutionContext):
        rules = self._resolve_rules(action)     # 获取断言规则
        target_data = self._fetch_target(action, ctx)  # 获取目标数据

        for rule in rules:
            actual = self._extract(target_data, rule.path)
            expected = interpolate(rule.expected, ctx.variables)
            passed = self.OPS[rule.op](actual, expected)

            result = AssertionResult(...)
            ctx.assertions.append(result)

        # 状态码快捷断言
        if action.status_code:
            passed = ctx.response_status == action.status_code
            ctx.assertions.append(AssertionResult(...))
```

---

## 8. 分发器

### `ActionDispatcher` ([line 591-623](framework.py#L591-L623))

动作分发器，将动作路由到对应处理器：

```python
class ActionDispatcher:
    def __init__(self):
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, action_type: str, handler: ActionHandler):
        """注册处理器"""
        self._handlers[action_type] = handler

    def dispatch(self, action: Action, ctx: ExecutionContext, bus: EventBus):
        handler = self._handlers.get(action.type)
        if handler is None:
            raise RuntimeError(f"no handler for action type: {action.type}")

        bus.emit(ActionStarted(...))            # 发布开始事件
        try:
            handler.handle(action, ctx)
        except Exception as e:
            ctx.failures.append(FailureRecord(...))
            if action.on_failure == "abort":
                raise
        finally:
            bus.emit(ActionFinished(...))      # 发布结束事件
```

---

## 9. HTTP 客户端

### `HttpClient` ([line 634-643](framework.py#L634-L643))

演示用 HTTP 客户端：

```python
class HttpClient:
    def __init__(self, mock_responses: dict):
        self.mock_responses = mock_responses

    def request(self, api: ApiSpec, request: RequestSpec) -> tuple[int, dict]:
        key = f"{api.method} {api.path}"
        resp = self.mock_responses.get(key, {"code": 0, "data": {}})
        return 200, resp
```

---

## 10. 状态机执行器

### `StepExecutor` ([line 646-749](framework.py#L646-L749))

核心状态机驱动器：

```python
class StepExecutor:
    MAIN_FLOW = [
        StepState.BEFORE_REQUEST,
        StepState.REQUESTING,
        StepState.AFTER_REQUEST,
        StepState.VERIFYING,
    ]

    def run(self) -> bool:
        # 设置 api/request 到 ctx
        self.ctx.api = self.step.api
        self.ctx.request = RequestSpec(**self.step.request.model_dump())

        try:
            for state in self.MAIN_FLOW:
                self._enter(state)              # 执行每个状态
        except StepAborted:
            pass
        finally:
            self._enter(StepState.TEARDOWN)    # 确保 teardown 执行
            self._finalize()

        return self._compute_passed()
```

**状态执行流程：**

```
_enter(state)
  ├── ctx.current_state = state
  ├── bus.emit(StateEntered)
  │
  ├── if state == REQUESTING:
  │     └── _do_request()
  └── else:
        └── _run_hooks(state)      # 执行该状态的所有 actions
            └── dispatcher.dispatch(action, ctx, bus)
  │
  └── bus.emit(StateExited)
```

**失败处理：**
- `BEFORE_REQUEST` 阶段失败 → 跳到 `TEARDOWN`
- 其他阶段失败 → 累积到 `ctx.failures`，继续执行

---

## 11. 插件层

### `ResponseTimePlugin` ([line 756-770](framework.py#L756-L770))

响应时间监控插件：

```python
class ResponseTimePlugin:
    def subscribe(self, bus: EventBus):
        bus.on(StateExited, self._on_exit)      # 订阅状态退出事件

    def _on_exit(self, event: StateExited):
        if event.state == StepState.REQUESTING:
            self.records.append({
                "action_name": event.context.action_name,
                "response_time_ms": event.duration_ms,
            })
```

---

## 12. 顶层 Runner

### `TestRunner` ([line 803-849](framework.py#L803-L849))

测试运行器顶层入口：

```python
class TestRunner:
    def __init__(self, mock_db: dict, mock_responses: dict):
        self.bus = EventBus()
        self.dispatcher = ActionDispatcher()
        # 注册处理器
        self.dispatcher.register("sql", SqlHandler(mock_db))
        self.dispatcher.register("extract", ExtractHandler(mock_db))
        self.dispatcher.register("assign", AssignHandler())
        self.dispatcher.register("assert", AssertHandler(mock_db))
        self.http = HttpClient(mock_responses)
        # 注册插件
        self.response_time_plugin = ResponseTimePlugin()
        self.response_time_plugin.subscribe(self.bus)

    def run(self, scenario: Scenario):
        for idx, step in enumerate(scenario.flow):
            if not step.enabled:
                continue
            ctx = ExecutionContext(...)
            executor = StepExecutor(step, ctx, self.dispatcher, self.bus, self.http)
            passed = executor.run()
            results.append((step.action_name, passed, ctx))
        # 输出总结
```

---

## 执行流程图

```
load_scenario(yaml)
        │
        ▼
TestRunner.run(scenario)
        │
        ▼
┌─────────────────────────────────────────┐
│  for each Step in scenario.flow:       │
│                                         │
│  ExecutionContext(scenario_id, ...)    │
│           │                             │
│           ▼                             │
│  StepExecutor.run()                     │
│           │                             │
│           ▼                             │
│  for state in MAIN_FLOW:                │
│    _enter(state)                        │
│      │                                  │
│      ├── BEFORE_REQUEST ──────────────  │
│      │   _run_hooks()                   │
│      │     dispatch(sql/extract/assign) │
│      │                                  │
│      ├── REQUESTING ──────────────────  │
│      │   _do_request()                  │
│      │                                  │
│      ├── AFTER_REQUEST ───────────────  │
│      │   _run_hooks()                   │
│      │     dispatch(sql/extract)        │
│      │                                  │
│      └── VERIFYING ───────────────────  │
│          _run_hooks()                   │
│            dispatch(assert)             │
│                                         │
│  _enter(TEARDOWN)                       │
│    _run_hooks()                         │
│      dispatch(sql)                      │
│                                         │
└─────────────────────────────────────────┘
        │
        ▼
  output summary
```

---

## 文件位置

- 完整代码：[framework.py](framework.py)
- 总线事件定义：[line 291-304](framework.py#L291-L304)
- 状态约束定义：[line 146-151](framework.py#L146-L151)
- 处理器注册：[line 808-811](framework.py#L808-L811)
