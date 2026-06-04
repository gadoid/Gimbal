# Statemachine 模块

> 状态机模块，驱动 Step 的执行流程 + 框架级 Hook 埋点

## 目录结构

```
gimbal/statemachine/
├── __init__.py
├── states.py       # StepState 枚举和合法转换表 VALID_TRANSITIONS
├── engine.py       # StepStateMachine
└── exceptions.py   # InvalidTransitionError, AlreadyTerminalError
```

## 核心组件

### StepState

Step 生命周期状态枚举：

```python
class StepState(str, Enum):
    # 等待/就绪
    PENDING = "pending"               # 创建但尚未调度

    # 执行阶段（对应 StrategyPhase）
    BEFORE_REQUEST = "before_request"  # Assign / SQL 注入
    CALLING = "calling"                # HTTP 发出、等待响应
    AFTER_REQUEST = "after_request"    # Extract 提取字段
    VERIFYING = "verifying"            # Assertion / DBChecker
    TEARDOWN = "teardown"              # SQL 清理 / Chaos 恢复

    # 终态
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"                    # 框架级异常
    SKIPPED = "skipped"

    @property
    def is_terminal(self) -> bool: ...
    @property
    def is_running(self) -> bool: ...
```

### VALID_TRANSITIONS

```python
VALID_TRANSITIONS: dict[StepState, frozenset[StepState]] = {
    StepState.PENDING: frozenset({
        StepState.BEFORE_REQUEST, StepState.SKIPPED,
    }),
    StepState.BEFORE_REQUEST: frozenset({
        StepState.CALLING, StepState.FAILED, StepState.TEARDOWN, StepState.ERROR,
    }),
    StepState.CALLING: frozenset({
        StepState.AFTER_REQUEST, StepState.FAILED, StepState.TEARDOWN, StepState.ERROR,
    }),
    StepState.AFTER_REQUEST: frozenset({
        StepState.VERIFYING, StepState.TEARDOWN, StepState.FAILED, StepState.ERROR,
    }),
    StepState.VERIFYING: frozenset({
        StepState.TEARDOWN, StepState.PASSED, StepState.FAILED, StepState.ERROR,
    }),
    StepState.TEARDOWN: frozenset({
        StepState.PASSED, StepState.FAILED, StepState.ERROR,
    }),
    # 终态不允许再跃迁
    StepState.PASSED: frozenset(),
    StepState.FAILED: frozenset(),
    StepState.ERROR: frozenset(),
    StepState.SKIPPED: frozenset(),
}
```

### StepStateMachine

```python
class StepStateMachine:
    """Step 执行状态机。

    用法：
        sm = StepStateMachine(
            step_id="step-001",
            step_schema=step,
            dispatcher=dispatcher,
            view=view,
            service_base_url="http://user-service",
            hook_registry=...,    # 可选
            event_bus=...,        # 可选
        )
        result = sm.run()
    """

    def __init__(
        self,
        *,
        step_id: str,
        step_schema: "Step",
        dispatcher: "StrategyDispatcher",
        view: "StepContextAdapter",
        service_base_url: str = "",
        on_transition: Optional[TransitionHook] = None,
        hook_registry: Optional[Any] = None,
        event_bus: Optional[Any] = None,
    ): ...

    def run(self) -> StepRunResult:
        """驱动状态机运行直到终态，返回执行结果。"""
        # 0. emit STEP_START
        # 1. 初始化 scratch.request_body
        # 2. _advance(PENDING -> BEFORE_REQUEST, reason="start")
        # 3. 内部循环：handler() -> 下一状态 -> _advance
        # 4. 异常：_try_advance(ERROR)
        # 5. emit STEP_END / STEP_FAILED

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

## 框架级 Hook 埋点

`StepStateMachine` 在关键节点触发 framework-level Hook：

| 节点 | Hook | payload |
|---|---|---|
| HTTP 发送前 | `HTTP_BEFORE_SEND` | `method`, `url`, `headers`, `body`, `timeout`, `step_id`, `ctx` |
| HTTP 接收后 | `HTTP_AFTER_RECV` | `method`, `url`, `status`, `headers`, `body`, `duration_ms`, `step_id`, `ctx` |

```python
def _fire_hook(self, point_name: str, payload: dict) -> bool:
    """触发 hook。返回 True 表示继续，False 表示被 STOP 中断。

    point_name 可以是 HookPoint 枚举的名字（如 "HTTP_BEFORE_SEND"），
    也可以是它的 value（如 "http.before_send"）。
    """
    if self._hooks is None:
        return True
    try:
        from gimbal.core.hooks import HookPoint
        # 优先按枚举名查（"HTTP_BEFORE_SEND"），再按 value 查（"http.before_send"）
        try:
            point = HookPoint[point_name]
        except KeyError:
            point = HookPoint(point_name)
    except (ValueError, ImportError):
        return True
    result = self._hooks.trigger(point, payload)
    return not result.stopped
```

**Issue 9 修复**：原实现只支持 `HookPoint(value)`，传入 `HTTP_BEFORE_SEND` 会抛 `ValueError`。修复后**优先按枚举名查**（`HookPoint[point_name]`），回退到按 value 查。

## 框架级 Event 埋点

通过 `event_bus` 在以下点 publish 事件：

| 事件 | 时机 |
|---|---|
| `StepStartEvent` | `run()` 入口 |
| `StepEndEvent` | `run()` 出口（PASSED/SKIPPED） |
| `StepFailedEvent` | `run()` 出口（FAILED/ERROR） |
| `HttpRequestEvent` | HTTP 调用前 |
| `HttpResponseEvent` | HTTP 调用后 |

`event_bus` 为 None 时静默跳过；`publish` 失败也不影响主流程（log debug）。

## StepRunResult

```python
@dataclass
class StepRunResult:
    step_id: str
    status: str
    phase_results: list[PhaseResult] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0

    @property
    def passed(self) -> bool: ...
```

## 设计原则

1. **状态驱动**：所有执行逻辑在 handler 中，状态机只负责流转。
2. **合法性校验**：每次 `_advance` 都校验 `VALID_TRANSITIONS`。
3. **终态保护**：终态后不允许再跃迁。
4. **自驱动**：调用方只需 `run()`，不感知内部流转。
5. **埋点可选**：`hook_registry` / `event_bus` 不传则不触发（向后兼容）。
6. **Hook 双查询**：枚举名优先，value 兜底——兼容两种调用风格。
7. **失败容错**：异常被吞，状态机进入 ERROR 而不是崩溃。
