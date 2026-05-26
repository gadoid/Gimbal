# Statemachine 模块

> 状态机模块，驱动 Step 的执行流程

## 目录结构

```
gimbal/statemachine/
├── __init__.py
├── states.py       # StepState 枚举和状态转换表
├── engine.py       # StepStateMachine
└── exceptions.py   # 状态机异常
```

## 核心组件

### StepState

Step 生命周期状态枚举：

```python
class StepState(str, Enum):
    # 等待/就绪
    PENDING = "pending"           # 创建但尚未调度

    # 执行阶段（对应 StrategyPhase）
    BEFORE_REQUEST = "before_request"  # Assign / SQL 注入
    CALLING = "calling"                # HTTP 发出、等待响应
    AFTER_REQUEST = "after_request"     # Extract 提取字段
    VERIFYING = "verifying"            # Assertion / DBChecker
    TEARDOWN = "teardown"              # SQL 清理 / Chaos 恢复

    # 终态
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"      # 框架级异常，区别于业务 FAILED
    SKIPPED = "skipped"

    @property
    def is_terminal(self) -> bool: ...

    @property
    def is_running(self) -> bool: ...
```

### VALID_TRANSITIONS

合法状态转换表：

```python
VALID_TRANSITIONS: dict[StepState, frozenset[StepState]] = {
    StepState.PENDING: frozenset({
        StepState.BEFORE_REQUEST,
        StepState.SKIPPED,
    }),
    StepState.BEFORE_REQUEST: frozenset({
        StepState.CALLING,
        StepState.FAILED,
        StepState.TEARDOWN,
        StepState.ERROR,
    }),
    StepState.CALLING: frozenset({
        StepState.AFTER_REQUEST,
        StepState.FAILED,
        StepState.TEARDOWN,
        StepState.ERROR,
    }),
    StepState.AFTER_REQUEST: frozenset({
        StepState.VERIFYING,
        StepState.TEARDOWN,
        StepState.FAILED,
        StepState.ERROR,
    }),
    StepState.VERIFYING: frozenset({
        StepState.TEARDOWN,
        StepState.PASSED,
        StepState.FAILED,
        StepState.ERROR,
    }),
    StepState.TEARDOWN: frozenset({
        StepState.PASSED,
        StepState.FAILED,
        StepState.ERROR,
    }),
    # 终态不允许再跃迁
    StepState.PASSED: frozenset(),
    StepState.FAILED: frozenset(),
    StepState.ERROR: frozenset(),
    StepState.SKIPPED: frozenset(),
}
```

### StepStateMachine

Step 执行状态机：

```python
class StepStateMachine:
    """Step 执行状态机"""

    def __init__(
        self,
        step_id: str,
        step_schema: Step,
        dispatcher: StrategyDispatcher,
        view: StepContextAdapter,
        service_base_url: str = "",
    ):
        self._state = StepState.PENDING
        ...

    def run(self) -> StepRunResult:
        """驱动状态机运行直到终态，返回执行结果"""
        # 内部循环驱动
        ...

    @property
    def state(self) -> StepState: ...
    @property
    def phase_results(self) -> list[PhaseResult]: ...
```

## 状态流转图

```
                    ┌─────────────────────────┐
                    │        PENDING          │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │     BEFORE_REQUEST       │
                    │  (执行 Assign 策略)      │
                    └───────────┬─────────────┘
                      │                 │
            ┌─────────▼──┐        ┌────▼─────────┐
            │  CALLING   │        │  TEARDOWN    │
            │ (HTTP 调用) │        │  (清理)      │
            └─────┬──────┘        └──────┬───────┘
                  │                      │
        ┌─────────▼─────────┐    ┌──────▼───────┐
        │   AFTER_REQUEST  │    │   PASSED     │
        │  (执行 Extract)  │    │   or FAILED  │
        └─────────┬─────────┘    └──────────────┘
                  │
        ┌─────────▼──────────┐
        │     VERIFYING       │
        │  (执行 Assertion)   │
        └─────────┬──────────┘
                  │
        ┌─────────▼──────────┐
        │      TEARDOWN      │
        │      (清理)        │
        └─────────┬──────────┘
                  │
        ┌─────────▼──────────┐
        │    PASSED/FAILED   │
        └────────────────────┘
```

## StepRunResult

执行结果：

```python
@dataclass
class StepRunResult:
    step_id: str
    status: str
    phase_results: list[PhaseResult]
    error: str | None
    duration_ms: float

    @property
    def passed(self) -> bool: ...
```

## 设计原则

1. **状态驱动**: 所有执行逻辑都在 handler 中，状态机只负责流转
2. **合法性校验**: 每次转换都校验是否合法
3. **终态保护**: 终态后不允许再转换
4. **自驱动**: 调用方只需 `run()`，不感知内部流转