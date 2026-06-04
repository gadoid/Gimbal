# Strategy 模块

> 策略模块，定义 Extract/Assign/Assertion 等策略及其执行器，支持软失败（soft）

## 目录结构

```
gimbal/strategy/
├── __init__.py
├── executor_base.py   # StrategyExecutor 基类 + StrategyResult + PhaseResult
├── dispatcher.py      # StrategyDispatcher
├── result.py          # 执行结果定义
└── builtin/          # 内置策略执行器
    ├── __init__.py
    ├── extract.py     # ExtractExecutor
    ├── assign.py      # AssignExecutor
    ├── assertion.py   # AssertionExecutor
    ├── call.py        # CallExecutor (HTTP 调用)
    ├── sleep.py       # SleepExecutor
    ├── sql.py         # SQLExecutor
    ├── poll.py        # PollExecutor
    ├── chaos.py       # ChaosExecutor
    ├── composite.py   # CompositeExecutor
    └── utils.py       # 工具函数
```

## 核心概念

### StrategyPhase

策略执行阶段：

```python
class StrategyPhase(str, Enum):
    BEFORE_REQUEST = "before_request"   # SQL 注入数据、Assign 准备入参
    AFTER_REQUEST = "after_request"     # Extract 提取字段
    VERIFYING = "verifying"             # Assertion、DBChecker
    TEARDOWN = "teardown"               # SQL 清理、Chaos 恢复
```

### StrategyExecutor

```python
class StrategyExecutor(ABC):
    """策略执行器抽象基类。

    子类只需实现 execute()，框架负责计时、异常捕获、日志。
    """

    kind: str = ""  # 子类声明自己处理哪种 kind

    @abstractmethod
    def execute(self, spec: StrategyBase, view: StrategyContextView) -> StrategyResult:
        """执行策略，返回结果。不允许抛出异常——异常应被包裹进 StrategyResult。"""
        ...
```

### StrategyDispatcher

```python
class StrategyDispatcher:
    """策略分发器"""

    def register(self, executor: StrategyExecutor) -> None
    def dispatch(self, spec, view) -> StrategyResult
    def dispatch_phase(self, phase, strategies, view) -> list[StrategyResult]
```

## 内置执行器

### ExtractExecutor

```python
class ExtractExecutor(StrategyExecutor):
    kind = "extract"

    # Schema
    class Extract(StrategyBase):
        source: ExtractSource    # RESPONSE_BODY / RESPONSE_HEADER / ...
        expression: str          # JSONPath 表达式
        target: str               # 写入 context 的 key
        scope: Scope             # FRAMEWORK / SESSION / SCENARIO / STEP
        default: Any              # 提取失败的默认值
        required: bool            # 提取失败是否抛出异常
```

### AssignExecutor

```python
class AssignExecutor(StrategyExecutor):
    kind = "assign"

    class Assign(StrategyBase):
        source: Any              # 字面量或 ${template}
        target: str              # 模板路径
        scope: Scope             # 注入到哪个作用域
        default: Any
        required: bool
```

### AssertionExecutor

```python
class AssertionExecutor(StrategyExecutor):
    kind = "assertion"

    class Assertion(StrategyBase):
        target: str              # 断言的目标字段
        operator: AssertOperator  # EQ / NE / GT / ...
        expected: Any             # 断言的比较值
        message: str | None
        soft: bool                # 软断言（失败不中断）
```

### CallExecutor

```python
class CallExecutor(StrategyExecutor):
    """执行 HTTP 调用（由状态机在 CALLING 阶段直接调用）"""
    kind = "_call"  # 内部 kind，不对应 schema
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
    SCHEMA = "schema"
```

## Scope 枚举

```python
class Scope(str, Enum):
    FRAMEWORK = "framework"   # 框架级
    SESSION = "session"       # 会话级
    SCENARIO = "scenario"    # Scenario 级
    STEP = "step"            # Step 级
    REQUEST = "request"      # 请求级
```

## StrategyResult（Issue 8 新增 soft 字段）

```python
class StrategyStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"    # executor 内部抛出未预期异常


@dataclass
class StrategyResult:
    """单条策略的执行结果。

    Attributes:
        status:      执行结论。
        strategy_id: 对应策略的 name 或自动生成的 id。
        message:     人类可读的描述。
        extracted:   本次提取/赋值写入 context 的键值。
        error:       非预期异常信息。
        duration_ms: 本条策略耗时。
        soft:        是否为软失败（spec.onFailure != ABORT 时由 dispatcher 置 True），
                     用于 PhaseResult.hard_failed 区分 hard/abort 失败。
                     注意：ERROR（系统异常）永远不是 soft。
    """

    status: StrategyStatus
    strategy_id: str = ""
    message: str = ""
    extracted: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    soft: bool = False

    @property
    def passed(self) -> bool: ...
    @property
    def failed(self) -> bool: ...
    @property
    def hard_failed(self) -> bool:
        """硬失败：失败且非软。"""
        return self.failed and not self.soft
```

## PhaseResult

```python
@dataclass
class PhaseResult:
    phase: str
    results: list[StrategyResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool: ...
    @property
    def any_failed(self) -> bool: ...
    @property
    def hard_failed(self) -> bool:
        """存在非软断言失败 → 必须中止。

        与 any_failed 的区别：CONTINUE/WARN 策略即使失败也不会触发 hard_failed。
        """
        return any(r.hard_failed for r in self.results)
```

`hard_failed` 已被 `StepStateMachine` 用于决定是否进入 TEARDOWN 状态——比 `any_failed` 更精确（不把软失败当成需要中止的失败）。

## 使用示例

```python
from gimbal.strategy.dispatcher import build_default_dispatcher
from gimbal.strategy.builtin import ExtractExecutor, AssignExecutor, AssertionExecutor

# 构建默认分发器
dispatcher = build_default_dispatcher()

# 执行单个策略
result = dispatcher.dispatch(extract_spec, view)

# 执行整个阶段
results = dispatcher.dispatch_phase("before_request", strategies, view)
```

## 设计原则

1. **Executor 单一职责**：每种策略对应一个 Executor。
2. **Dispatcher 统一分发**：所有策略都通过 Dispatcher 分发。
3. **Phase 有序执行**：同一阶段的策略按 order 排序执行。
4. **失败策略可控**：通过 `onFailure` 控制失败行为；软失败（CONTINUE/WARN）走 `soft=True`。
5. **不抛异常**：executor 异常被包裹为 `StrategyResult(status=ERROR)`，避免主流程崩溃。
6. **软失败语义**：`StrategyResult.soft` 由 dispatcher 根据 `spec.onFailure` 注入；ERROR 永远不是 soft。
