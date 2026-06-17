# Strategy 模块

> 策略模块：定义 Extract / Assign / Assertion / Call 等策略的执行器（`StrategyExecutor`）与统一分发器（`StrategyDispatcher`），支持软失败（soft / hard-fail）。

## 目录结构

```
gimbal/strategy/
├── __init__.py        # """Strategy executor module."""
├── executor_base.py   # StrategyExecutor 基类 + StrategyResult + PhaseResult + StrategyStatus
├── dispatcher.py      # StrategyDispatcher + build_default_dispatcher()
├── result.py          # 占位（"""StrategyResult definition."""）
└── builtin/
    ├── __init__.py        # """Builtin executor implementations."""
    ├── extract.py         # ExtractExecutor (kind="extract")
    ├── assign.py          # AssignExecutor (kind="assign")
    ├── assertion.py       # AssertionExecutor (kind="assertion")
    ├── call.py            # CallExecutor (kind="_call", HTTP)
    ├── sleep.py           # SleepExecutor (kind="sleep", 已实现)
    ├── sql.py             # SqlExecutor (kind="sql", 占位)
    ├── poll.py            # PollExecutor (kind="poll", 占位)
    ├── chaos.py           # ChaosExecutor (kind="chaos", 占位)
    ├── composite.py       # CompositeExecutor (kind="composite", 占位)
    └── utils.py           # _scope_to_layer / _resolve_source_value / _evaluate / _jsonpath_simple
```

## 核心概念

### StrategyStatus

```python
class StrategyStatus(str, Enum):
    PASSED  = "passed"
    FAILED  = "failed"
    SKIPPED = "skipped"
    ERROR   = "error"   # executor 内部抛出未预期异常（永远不是 soft）
```

### StrategyExecutor

```python
class StrategyExecutor(ABC):
    """策略执行器抽象基类。

    子类只需实现 execute()，框架负责计时、异常捕获、日志。
    子类通过 `kind` 类属性声明自己处理哪种 kind。
    """

    kind: str = ""

    @abstractmethod
    def execute(
        self,
        spec: "StrategyBase",
        view: "StrategyContextView",
    ) -> StrategyResult:
        """执行策略，返回结果。不允许抛出异常——异常应被包裹进 StrategyResult。"""
        ...
```

### StrategyResult

```python
@dataclass
class StrategyResult:
    """单条策略的执行结果。"""

    status: StrategyStatus
    strategy_id: str = ""
    message: str = ""
    extracted: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    soft: bool = False

    @property
    def passed(self) -> bool:
        return self.status == StrategyStatus.PASSED

    @property
    def failed(self) -> bool:
        return self.status in (StrategyStatus.FAILED, StrategyStatus.ERROR)

    @property
    def hard_failed(self) -> bool:
        """硬失败：失败且非软。"""
        return self.failed and not self.soft
```

`StrategyResult.soft` 由 `StrategyDispatcher` 根据 `spec.onFailure` 注入：

- `spec.onFailure == ABORT` 时失败 → `soft=False`（hard fail）
- `spec.onFailure in (CONTINUE, WARN)` 时失败 → `soft=True`（软失败）
- `ERROR`（系统异常）**永远不是** soft

### PhaseResult

```python
@dataclass
class PhaseResult:
    """一个阶段（phase）内所有策略执行结果的汇总。"""

    phase: str
    results: list[StrategyResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def any_failed(self) -> bool:
        return any(r.failed for r in self.results)

    @property
    def hard_failed(self) -> bool:
        """存在非软断言失败 → 必须中止。

        与 any_failed 的区别：CONTINUE/WARN 策略即使失败也不会触发 hard_failed。
        """
        return any(r.hard_failed for r in self.results)
```

`hard_failed` 已被 `StepStateMachine` 用于决定是否进入 TEARDOWN 状态——比 `any_failed` 更精确（不把软失败当成需要中止的失败）。

## StrategyDispatcher

```python
class StrategyDispatcher:
    """策略分发器。

    用法::

        dispatcher = StrategyDispatcher()
        dispatcher.register(ExtractExecutor())
        dispatcher.register(AssignExecutor())
        dispatcher.register(AssertionExecutor())

        result = dispatcher.dispatch(spec, view)

    可选埋点：
        dispatcher = StrategyDispatcher(hook_registry=registry)
    """

    def __init__(self, hook_registry: Optional[Any] = None) -> None:
        self._registry: dict[str, StrategyExecutor] = {}
        self._hooks = hook_registry

    def register(self, executor: StrategyExecutor) -> None:
        """注册一个 executor，以其 kind 为键。kind 为空时抛 StrategyError。"""

    def dispatch(self, spec, view) -> StrategyResult:
        """根据 spec.kind 找到对应 executor，执行并返回结果。

        框架统一做：
          - 跳过 disabled 的策略（返回 SKIPPED）
          - 查找 executor；找不到返回 ERROR("No executor registered for kind=…")
          - 触发 STRATEGY_BEFORE hook（可短路停止该策略）
          - 计时（写入 result.duration_ms）
          - 兜底异常捕获（异常 → ERROR + traceback）
          - 根据 spec.onFailure 决定 result.soft
          - 触发 STRATEGY_AFTER hook（可改写 result）
        """

    def dispatch_phase(
        self,
        phase: str,
        strategies: list["StrategyBase"],
        view: "StrategyContextView",
    ) -> list[StrategyResult]:
        """执行属于指定 phase 的所有策略，按 order 排序后顺序执行。

        遇到 hard-fail（onFailure=ABORT 且结果为 FAILED/ERROR）时提前终止。
        软失败（onFailure=CONTINUE/WARN）则记录并继续。
        """


def build_default_dispatcher(hook_registry: Optional[Any] = None) -> StrategyDispatcher:
    """构造并注册内置所有 executor 的 dispatcher：Extract / Assign / Assertion / Call。"""
```

## 内置执行器

### ExtractExecutor（`builtin/extract.py`）

```python
class ExtractExecutor(StrategyExecutor):
    kind = "extract"
```

- 用 JSONPath `spec.expression` 从 `view.get_scratch_dict()` 取值
- 值为 `None` 时按 `spec.default` / `spec.required` 处理（required + None → FAILED）
- `scope=STEP` 时 `view.write_scratch(spec.target, value)`
- 其他 scope 时通过 `view.promote_variable(spec.target, value, to=target_layer)` 提升到 framework/session/scenario/request
- 成功返回 `PASSED`，写入 `extracted={target: value}`

### AssignExecutor（`builtin/assign.py`）

```python
class AssignExecutor(StrategyExecutor):
    kind = "assign"
```

- `source` 可以是字面量、模板 `${varname}`、JSONPath `$.jsonpath`、或 `null`
- 通过 `_resolve_source_value` 解析（见 `builtin/utils.py`）
  - `scope=STEP` 时先查 scratch，再降级到 SCENARIO context
  - `scope=SCENARIO` 时直接从 context 用同一 JSONPath 查询
  - `${var}` 模板先查 scratch，再查 context
- 解析为 `None` 时按 `spec.default` / `spec.required` 处理
- 写入 `view.write_scratch(spec.target, value)`（支持 JSONPath 嵌套写入）
- 成功返回 `PASSED`，附带 `extracted={target: value}`

### AssertionExecutor（`builtin/assertion.py`）

```python
class AssertionExecutor(StrategyExecutor):
    kind = "assertion"
```

- `target` 为 JSONPath 时从 `view.get_scratch_dict()` 用 `gimbal.utils.jsonpath.get` 取值
- `target` 为普通 key 时先查 scratch，再回退到 SCENARIO context（`view.read_variable(..., from_layer=ContextLayer.SCENARIO)`）
- 通过 `_evaluate(spec.operator, actual, spec.expected)` 比较（`builtin/utils.py`）
- 成功 / 失败写入 `view.record_assertion(AssertionResult(...))`
- 成功返回 `PASSED`，失败返回 `FAILED`

### CallExecutor（`builtin/call.py`）

```python
class CallExecutor(StrategyExecutor):
    """执行 HTTP 调用，将响应存入 scratch。"""
    kind = "_call"  # 内部 kind，不对应 schema
```

特殊点：它不对应 schema 中某个 `Strategy` 子类，而是由 `ScenarioRunner` 在 `CALLING` 阶段直接调用，传入内部合成的 `_CallSpec`。

实现要点：

- 从 `view.read_scratch("request_body")` 读取实时请求体（可能被 Assign 修改）
- 用 `httpx.Client(timeout=spec.timeout)` 发出请求
- `GET`/`HEAD` 用 `params=body`，其它方法用 `json=body`
- 写入 scratch：`request_method` / `request_url` / `request_headers` / `request_body`
- 写入响应 scratch：`response_status` / `response_headers` / `response_body` / `duration_ms`
- 异常分支：`httpx.TimeoutException` / `httpx.RequestError` / 其它 → 全部返回 `ERROR` + traceback

### SleepExecutor（`builtin/sleep.py`）

```python
class SleepExecutor(StrategyExecutor):
    kind = "sleep"
```

**已实现**：`time.sleep(spec.duration)`，成功后返回 `PASSED`。`duration` 默认 1.0 秒。

### SqlExecutor（`builtin/sql.py`）

```python
class SqlExecutor(StrategyExecutor):
    kind = "sql"
```

**占位实现**：仅记录日志并返回 `PASSED`，**未实际连接数据库**（`# TODO: 接入数据库执行`）。

### PollExecutor（`builtin/poll.py`）

```python
class PollExecutor(StrategyExecutor):
    kind = "poll"
```

**占位实现**：读取 `target` / `interval` / `timeout` 字段后直接返回 `PASSED`，**未实现真正的轮询逻辑**（`# TODO: 实现轮询逻辑`）。

### ChaosExecutor（`builtin/chaos.py`）

```python
class ChaosExecutor(StrategyExecutor):
    kind = "chaos"
```

**占位实现**：读取 `action` / `target` 字段后返回 `PASSED`，**未实际注入故障**（`# TODO: 接入混沌工程平台（如 Chaos Mesh）`）。

### CompositeExecutor（`builtin/composite.py`）

```python
class CompositeExecutor(StrategyExecutor):
    kind = "composite"
```

**占位实现**：读取 `name` 字段后返回 `PASSED`，**未实现子策略列表的顺序执行和结果聚合**（`# TODO: 实现子策略列表的顺序执行和结果聚合`）。

### builtin/utils.py 工具函数

- `_scope_to_layer(scope)` —— 将 `schema.Scope` 映射到 `ContextLayer`（`SESSION → SUITE`；`STEP → SCENARIO`）。
- `_jsonpath_simple(data, expression)` —— 极简 JSONPath，支持 `$.a.b.c` 与 `$.a[0].b`，找不到返回 `None`。
- `_resolve_source_value(source, view, scope)` —— 解析 `Assign.source`（字面量 / `${var}` / `$.jsonpath`）。
- `_evaluate(operator, actual, expected) -> (bool, msg)` —— 执行比较并返回结果与描述。

支持的 `AssertOperator`：

```python
EQ, NE, GT, GTE, LT, LTE,        # 等于 / 不等于 / 大于 / 大于等于 / 小于 / 小于等于
IN, NOT_IN,                       # 包含于 / 不包含于
CONTAINS, NOT_CONTAINS,           # 包含 / 不包含
EXISTS, EMPTY,                    # 存在 / 为空
LENGTH_EQ,                        # 长度等于
```

## AssertOperator 枚举

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
```

## Scope 枚举

```python
class Scope(str, Enum):
    FRAMEWORK = "framework"   # 框架级
    SESSION   = "session"     # 会话级
    SCENARIO  = "scenario"    # Scenario 级
    STEP      = "step"        # Step 级
    REQUEST   = "request"     # 请求级
```

## 使用示例

```python
from gimbal.strategy.dispatcher import build_default_dispatcher
from gimbal.strategy.builtin import ExtractExecutor, AssignExecutor, AssertionExecutor

# 构建默认分发器（已注册 Extract / Assign / Assertion / Call）
dispatcher = build_default_dispatcher(hook_registry=my_hook_registry)

# 注册自定义 executor
class MyExecutor(StrategyExecutor):
    kind = "my_kind"
    def execute(self, spec, view) -> StrategyResult:
        ...
dispatcher.register(MyExecutor())

# 执行单个策略
result = dispatcher.dispatch(extract_spec, view)
if result.hard_failed:
    ...

# 执行整个 phase（按 order 排序，遇 hard fail 提前终止）
results = dispatcher.dispatch_phase("before_request", strategies, view)
```

## 设计原则

1. **Executor 单一职责**：每种策略对应一个 Executor。
2. **Dispatcher 统一分发**：所有策略都通过 Dispatcher 分发。
3. **Phase 有序执行**：同一阶段的策略按 `order` 排序执行。
4. **失败策略可控**：通过 `onFailure`（`ABORT` / `CONTINUE` / `WARN`）控制失败行为；软失败走 `soft=True`。
5. **不抛异常**：executor 异常被包裹为 `StrategyResult(status=ERROR)`，避免主流程崩溃。
6. **软失败语义**：`StrategyResult.soft` 由 dispatcher 根据 `spec.onFailure` 注入；`ERROR` 永远不是 soft。
7. **Hook 埋点**：可选传入 `hook_registry`，`dispatch` 会触发 `STRATEGY_BEFORE`（可短路）和 `STRATEGY_AFTER`（可改写 result）。
