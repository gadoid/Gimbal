# Strategy 模块

策略执行器模块，负责执行 Extract / Assign / Assertion 等具体策略。

## 设计理念

### 1. 策略模式

每种策略类型对应一个 `StrategyExecutor` 实现：

```
StrategyBase (schema)
    │
    ├── Extract  → ExtractExecutor
    ├── Assign   → AssignExecutor
    ├── Assertion → AssertionExecutor
    └── ...

StrategyExecutor (抽象基类)
    │
    └── execute(spec, view) → StrategyResult
```

### 2. 分层分发

通过 `StrategyDispatcher` 按 `phase` 分层分发：

```
StrategyPhase.BEFORE_REQUEST  →  Assign, SQL 注入...
StrategyPhase.CALLING         →  HTTP 调用 (内部)
StrategyPhase.AFTER_REQUEST  →  Extract
StrategyPhase.VERIFYING      →  Assertion
StrategyPhase.TEARDOWN      →  SQL 清理, Chaos 恢复...
```

### 3. 结果聚合

```
StrategyResult (单条策略)
    │
    └── PhaseResult (一个阶段)
            │
            └── all_passed / any_failed / hard_failed
```

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `executor_base.py` | `StrategyExecutor` 抽象基类，`StrategyResult` |
| `dispatcher.py` | `StrategyDispatcher` 分发器 |
| `result.py` | 结果定义 |

### builtin/

| 文件 | Executor | 说明 |
|------|----------|------|
| `call.py` | `CallExecutor` | HTTP 调用 |
| `extract.py` | `ExtractExecutor` | 字段提取 |
| `assign.py` | `AssignExecutor` | 变量赋值 |
| `assertion.py` | `AssertionExecutor` | 断言验证 |
| `sleep.py` | `SleepExecutor` | 等待（占位） |
| `sql.py` | `SqlExecutor` | SQL 执行（占位） |
| `poll.py` | `PollExecutor` | 轮询（占位） |
| `chaos.py` | `ChaosExecutor` | 混沌工程（占位） |
| `composite.py` | `CompositeExecutor` | 组合策略（占位） |
| `utils.py` | - | 工具函数 |

---

## StrategyExecutor 抽象基类

```python
class StrategyExecutor(ABC):
    """策略执行器抽象基类。"""

    # 子类声明自己处理哪种 kind
    kind: str = ""

    @abstractmethod
    def execute(
        self,
        spec: "StrategyBase",
        view: "StrategyContextView",
    ) -> StrategyResult:
        """执行策略，返回结果。异常应被包裹进 StrategyResult。"""
        ...
```

**规范**：
- 不允许抛出异常，异常必须包裹进 `StrategyResult`
- 执行耗时写入 `result.duration_ms`
- 通过 `view.promote_variable()` 写入 context

---

## StrategyResult

单条策略的执行结果。

```python
@dataclass
class StrategyResult:
    status: StrategyStatus  # passed / failed / skipped / error
    strategy_id: str = ""   # 策略名称或 id
    message: str = ""        # 人类可读描述
    extracted: dict = {}      # 写入 context 的变量
    error: Optional[str] = None  # 异常信息
    duration_ms: float = 0.0

    @property
    def passed(self) -> bool: ...
    @property
    def failed(self) -> bool: ...
```

### StrategyStatus

```python
class StrategyStatus(str, Enum):
    PASSED = "passed"    # 执行成功
    FAILED = "failed"    # 断言失败等业务失败
    SKIPPED = "skipped"  # 被跳过（disabled）
    ERROR = "error"      # 框架级异常
```

---

## PhaseResult

一个阶段内所有策略的汇总。

```python
@dataclass
class PhaseResult:
    phase: str
    results: list[StrategyResult]

    @property
    def all_passed(self) -> bool:        # 所有都通过
    @property
    def any_failed(self) -> bool:       # 任一失败
    @property
    def hard_failed(self) -> bool:      # 存在非软断言失败
```

---

## StrategyDispatcher

策略分发器，维护 `kind → Executor` 映射。

### 核心方法

| 方法 | 说明 |
|------|------|
| `register(executor)` | 注册 executor |
| `dispatch(spec, view)` | 分发单条策略 |
| `dispatch_phase(phase, strategies, view)` | 按阶段批量分发 |

### dispatch 执行流程

```
1. 检查 spec.enabled，禁用则返回 SKIPPED
2. 根据 spec.kind 查找 executor
3. 未找到则返回 ERROR
4. 执行 executor.execute()
5. 计时，捕获异常包裹进 ERROR
```

### dispatch_phase 执行流程

```
1. 过滤出属于指定 phase 的策略
2. 按 order 排序
3. 顺序执行，遇到 ABORT 失败时中断
```

### 使用示例

```python
from gimbal.strategy.dispatcher import build_default_dispatcher

# 构建带内置 executor 的 dispatcher
dispatcher = build_default_dispatcher()

# 分发单条策略
result = dispatcher.dispatch(spec, view)

# 按阶段分发
results = dispatcher.dispatch_phase(
    phase=StrategyPhase.AFTER_REQUEST,
    strategies=step.strategy,
    view=view
)
```

---

## 内置 Executor

### CallExecutor

执行 HTTP 调用，将响应写入 context。

```python
class CallExecutor(StrategyExecutor):
    kind = "_call"  # 特殊 kind，内部使用

    def execute(self, spec, view) -> StrategyResult:
        # 执行 HTTP 请求
        # 写入 context:
        #   - response_status
        #   - response_headers
        #   - response_body
```

### ExtractExecutor

从响应/请求中提取字段。

```python
class ExtractExecutor(StrategyExecutor):
    kind = "extract"

    # spec: Extract (schema)
    #   - source: ExtractSource (RESPONSE_BODY, etc.)
    #   - expression: JSONPath 表达式
    #   - target: 写入 context 的 key
    #   - scope: 目标层级
    #   - default: 默认值
    #   - required: 是否必须
```

**表达式支持**：`$.field.subfield` 格式

### AssignExecutor

变量赋值。

```python
class AssignExecutor(StrategyExecutor):
    kind = "assign"

    # spec: Assign (schema)
    #   - source: 字面量或模板 "${varname}"
    #   - target: 目标 key
    #   - scope: 目标层级
```

**source 支持**：
- 字面量：`123`, `"hello"`, `{"key": "value"}`
- 模板：`"${user_id}"` 从 context 读取

### AssertionExecutor

断言验证。

```python
class AssertionExecutor(StrategyExecutor):
    kind = "assertion"

    # spec: Assertion (schema)
    #   - target: 断言目标字段
    #   - operator: AssertOperator (EQ, NE, GT, etc.)
    #   - expected: 期望值
    #   - message: 失败信息
    #   - soft: 是否软断言
```

**AssertOperator**：

| 操作符 | 说明 |
|--------|------|
| `EQ` | 等于 |
| `NE` | 不等于 |
| `GT` | 大于 |
| `GTE` | 大于等于 |
| `LT` | 小于 |
| `LTE` | 小于等于 |
| `IN` | 在列表中 |
| `NOT_IN` | 不在列表中 |
| `CONTAINS` | 包含 |
| `NOT_CONTAINS` | 不包含 |
| `EXISTS` | 存在 |
| `EMPTY` | 为空 |
| `LENGTH_EQ` | 长度等于 |
| `SCHEMA` | 符合 schema |

---

## build_default_dispatcher

```python
def build_default_dispatcher() -> StrategyDispatcher:
    """构造并注册内置所有 executor 的 dispatcher。"""
    from gimbal.strategy.builtin.extract import ExtractExecutor
    from gimbal.strategy.builtin.assign import AssignExecutor
    from gimbal.strategy.builtin.assertion import AssertionExecutor
    from gimbal.strategy.builtin.call import CallExecutor

    d = StrategyDispatcher()
    d.register(ExtractExecutor())
    d.register(AssignExecutor())
    d.register(AssertionExecutor())
    d.register(CallExecutor())
    return d
```

---

## 执行流程

**说明**：策略分发由 `StepStateMachine` 内部通过 `_run_phase()` 调用 `dispatcher.dispatch_phase()` 触发。

```
StepStateMachine.run() 【自驱动】
    │
    ├── BEFORE_REQUEST 阶段
    │   └── _run_phase(BEFORE_REQUEST)
    │           │
    │           └── dispatcher.dispatch_phase(BEFORE_REQUEST, strategies, view)
    │                   │
    │                   └── AssignExecutor.execute() × n
    │
    ├── CALLING 阶段
    │   └── _do_http_call()
    │           └── dispatcher.dispatch(_CallSpec, view)
    │                   │
    │                   └── CallExecutor.execute()
    │                           │
    │                           └── HTTP 请求
    │                           └── 写入 response_status/headers/body
    │
    ├── AFTER_REQUEST 阶段
    │   └── _run_phase(AFTER_REQUEST)
    │           │
    │           └── dispatcher.dispatch_phase(AFTER_REQUEST, strategies, view)
    │                   │
    │                   └── ExtractExecutor.execute() × n
    │
    ├── VERIFYING 阶段
    │   └── _run_phase(VERIFYING)
    │           │
    │           └── dispatcher.dispatch_phase(VERIFYING, strategies, view)
    │                   │
    │                   └── AssertionExecutor.execute() × n
    │
    └── TEARDOWN 阶段 (可选)
        └── _run_phase(TEARDOWN)
                │
                └── dispatcher.dispatch_phase(TEARDOWN, strategies, view)
```

---

## 运行测试

```bash
python -m gimbal.strategy.dispatcher
```
