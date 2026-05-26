# Strategy 模块

> 策略模块，定义 Extract/Assign/Assertion 等策略及其执行器

## 目录结构

```
gimbal/strategy/
├── __init__.py
├── executor_base.py   # StrategyExecutor 基类和执行结果
├── dispatcher.py      # StrategyDispatcher
├── result.py          # 执行结果定义
└── builtin/          # 内置策略执行器
    ├── __init__.py
    ├── extract.py     # ExtractExecutor
    ├── assign.py      # AssignExecutor
    ├── assertion.py   # AssertionExecutor
    ├── call.py       # CallExecutor (HTTP 调用)
    ├── sleep.py      # SleepExecutor
    ├── sql.py        # SQLExecutor
    ├── poll.py       # PollExecutor
    ├── chaos.py      # ChaosExecutor
    ├── composite.py  # CompositeExecutor
    └── utils.py      # 工具函数
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

策略执行器基类：

```python
class StrategyExecutor(ABC):
    """策略执行器抽象基类"""

    kind: str = ""  # 子类声明自己处理哪种 kind

    @abstractmethod
    def execute(self, spec: StrategyBase, view: StrategyContextView) -> StrategyResult:
        """执行策略，返回结果"""
        raise NotImplementedError
```

### StrategyDispatcher

策略分发器：

```python
class StrategyDispatcher:
    """策略分发器"""

    def register(self, executor: StrategyExecutor) -> None:
        """注册 executor"""
        ...

    def dispatch(self, spec: StrategyBase, view: StrategyContextView) -> StrategyResult:
        """根据 spec.kind 找到对应 executor，执行并返回结果"""
        ...

    def dispatch_phase(
        self,
        phase: str,
        strategies: list[StrategyBase],
        view: StrategyContextView,
    ) -> list[StrategyResult]:
        """执行属于指定 phase 的所有策略，按 order 排序"""
        ...
```

## 内置执行器

### ExtractExecutor

从响应/请求中提取字段：

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

赋值到指定路径：

```python
class AssignExecutor(StrategyExecutor):
    kind = "assign"

    # Schema
    class Assign(StrategyBase):
        source: Any              # 字面量或 ${template}
        target: str              # 模板路径
        scope: Scope             # 注入到哪个作用域
        default: Any              # 注入失败的默认值
        required: bool           # 注入失败是否抛出异常
```

### AssertionExecutor

断言执行：

```python
class AssertionExecutor(StrategyExecutor):
    kind = "assertion"

    # Schema
    class Assertion(StrategyBase):
        target: str              # 断言的目标字段
        operator: AssertOperator  # EQ / NE / GT / GTE / LT / LTE / IN / CONTAINS / ...
        expected: Any             # 断言的比较值
        message: str | None       # 断言失败信息
        soft: bool                # 软断言
```

### CallExecutor

HTTP 调用：

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
    FRAMEWORK = "framework"   # 框架级，所有 Scenario 共享
    SESSION = "session"       # 会话级
    SCENARIO = "scenario"    # Scenario 级
    STEP = "step"            # Step 级
    REQUEST = "request"      # 请求级
```

## StrategyResult

执行结果：

```python
@dataclass
class StrategyResult:
    status: StrategyStatus  # PASSED / FAILED / SKIPPED / ERROR
    strategy_id: str
    message: str
    extracted: dict        # 本次提取/赋值写入的键值
    error: str | None
    duration_ms: float

    @property
    def passed(self) -> bool: ...

    @property
    def failed(self) -> bool: ...
```

## PhaseResult

阶段执行结果汇总：

```python
@dataclass
class PhaseResult:
    phase: str
    results: list[StrategyResult]

    @property
    def all_passed(self) -> bool: ...
    @property
    def any_failed(self) -> bool: ...
    @property
    def hard_failed(self) -> bool: ...  # 存在非软断言失败
```

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

1. **Executor 单一职责**: 每种策略对应一个 Executor
2. **Dispatcher 统一分发**: 所有策略都通过 Dispatcher 分发
3. **Phase 有序执行**: 同一阶段的策略按 order 排序执行
4. **失败策略可控**: 通过 onFailure 控制失败行为