# Statemachine 模块

> 状态机模块，驱动 Step 的执行流程 + 框架级 Hook 埋点

## 目录结构

```
gimbal/statemachine/
├── __init__.py
├── states.py       # StepState 枚举和合法转换表 VALID_TRANSITIONS
├── engine.py       # StepStateMachine
└── exceptions.py   # InvalidTransitionError, AlreadyTerminalError（来自 gimbal.exceptions 的 re-export）
```

## 核心组件

### StepState

Step 生命周期状态枚举：

```python
class StepState(str, Enum):
    """Step 生命周期状态。"""

    # ── 等待/就绪 ──────────────────────────────
    PENDING = "pending"               # 创建但尚未调度

    # ── 执行阶段（对应 StrategyPhase）──────────
    BEFORE_REQUEST = "before_request"  # Assign / SQL 注入
    CALLING = "calling"                # HTTP 发出、等待响应
    AFTER_REQUEST = "after_request"    # Extract 提取字段
    VERIFYING = "verifying"            # Assertion / DBChecker
    TEARDOWN = "teardown"              # SQL 清理 / Chaos 恢复

    # ── 终态 ───────────────────────────────────
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"                    # 框架级异常，区别于业务 FAILED
    SKIPPED = "skipped"

    @property
    def is_terminal(self) -> bool: ...
    @property
    def is_running(self) -> bool: ...
```

终态集合 `_TERMINAL_STATES = {PASSED, FAILED, ERROR, SKIPPED}`，运行态集合 `_RUNNING_STATES = {BEFORE_REQUEST, CALLING, AFTER_REQUEST, VERIFYING, TEARDOWN}`。

### VALID_TRANSITIONS

```python
VALID_TRANSITIONS: dict[StepState, frozenset[StepState]] = {
    StepState.PENDING: frozenset({
        StepState.BEFORE_REQUEST,
        StepState.SKIPPED,
    }),
    StepState.BEFORE_REQUEST: frozenset({
        StepState.CALLING,
        StepState.FAILED,   # 前置策略失败 → 直接 FAILED（跳过 HTTP 调用）
        StepState.TEARDOWN, # 前置失败且有 teardown 时
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
        StepState.PASSED,   # 没有 teardown 时直接 PASSED
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

```python
TransitionHook = Callable[[StepState, StepState, str], None]   # (from, to, reason)


# 内部 _CallSpec：HTTP 调用描述，由状态机在 CALLING 阶段合成。不属于 schema。
@dataclass
class _CallSpec:
    kind: str = "_call"
    method: str = "GET"
    url: str = ""
    headers: dict = field(default_factory=dict)
    body: dict = field(default_factory=dict)
    timeout: float = 30.0
    name: Optional[str] = "http_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = field(default_factory=list)


@dataclass
class StepRunResult:
    step_id: str
    status: str
    phase_results: list[PhaseResult] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0
    # 修复 #5：标记 step 失败的阶段（"calling"/"verifying"/"teardown"/None）
    # 方便 reporter 区分"网络失败"vs"断言失败"vs"清理失败"
    error_phase: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.status == "passed"


class StepStateMachine:
    """Step 执行状态机。

    持有执行所需的全部上下文，自己驱动整个流程。

    用法::

        sm = StepStateMachine(
            step_id="step-001",
            step_schema=step,
            dispatcher=dispatcher,
            view=view,
            service_base_url="http://user-service",
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
    ) -> None:
        # 内部状态：_state (init=PENDING), _phase_results, _error, _error_phase
        # handler 表: {BEFORE_REQUEST, CALLING, AFTER_REQUEST, VERIFYING, TEARDOWN}
        ...

    @property
    def state(self) -> StepState: ...
    @property
    def phase_results(self) -> list[PhaseResult]: ...   # 浅拷贝

    def run(self) -> StepRunResult:
        """驱动状态机运行直到终态，返回执行结果。

        流程：
          0. emit STEP_START
          1. 初始化 scratch.request_body（来自 step_schema.request.body）
          2. _advance(PENDING -> BEFORE_REQUEST, reason="start")
          3. 内部循环：handler() -> 下一状态 -> _advance
          4. 异常：_try_advance(ERROR)
          5. emit STEP_END（PASSED/SKIPPED）或 STEP_FAILED（FAILED/ERROR）
        """
        ...
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
        └─────────┬────────┘    └──────────────┘
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

### 流转表

```
  PENDING
    └─→ BEFORE_REQUEST   执行 Assign 等前置策略
          ├─→ CALLING        策略全部通过
          └─→ TEARDOWN       hard-fail，跳过 HTTP
    CALLING               发出 HTTP 请求
          ├─→ AFTER_REQUEST  请求成功
          └─→ TEARDOWN       请求失败
    AFTER_REQUEST         执行 Extract 等后置策略
          ├─→ VERIFYING      策略全部通过
          └─→ TEARDOWN       hard-fail
    VERIFYING             执行 Assertion
          ├─→ PASSED         无 teardown 且全部通过
          ├─→ FAILED         无 teardown 且有失败
          └─→ TEARDOWN       有 teardown 策略（无论结果）
    TEARDOWN              执行清理策略
          ├─→ PASSED
          └─→ FAILED
```

### 各 handler 关键行为

- **`_handle_before_request`**：执行 `StrategyPhase.BEFORE_REQUEST` 阶段所有策略。`hard_failed` → `TEARDOWN`（跳过 HTTP），否则 → `CALLING`。
- **`_handle_calling`**：合成 `_CallSpec` 交给 dispatcher 执行，标记 `error_phase="calling"` 用于 reporter 区分。失败 → `TEARDOWN`，成功 → `AFTER_REQUEST`。
- **`_handle_after_request`**：执行 `StrategyPhase.AFTER_REQUEST` 阶段（Extract）。`hard_failed` → `TEARDOWN`，否则 → `VERIFYING`。
- **`_handle_verifying`**：执行 `StrategyPhase.VERIFYING` 阶段（Assertion）。若存在 `TEARDOWN` 策略则 → `TEARDOWN`（无论断言结果）；否则按 `hard_failed` 判定 → `PASSED` / `FAILED`。
- **`_handle_teardown`**：执行 `StrategyPhase.TEARDOWN` 阶段。
  - 前序阶段（含 hard 失败）→ `FAILED`
  - 业务阶段全通过 + teardown 失败 → `PASSED`（修复 B6：teardown 失败不污染业务结果，但 `error_phase="teardown"`）
  - 业务阶段全通过 + teardown 通过 → `PASSED`

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
| `StepStartEvent` | `run()` 入口（含 `step_id` + `step_name`） |
| `StepEndEvent` | `run()` 出口（PASSED/SKIPPED） |
| `StepFailedEvent` | `run()` 出口（FAILED/ERROR），`error` 截断 500 字符 |
| `HttpRequestEvent` | HTTP 调用前 |
| `HttpResponseEvent` | HTTP 调用后，`status_code` 非数字 fallback 0 |

```python
def _emit_step_start(self) -> None:
    if self._bus is None:
        return
    try:
        from gimbal.events.types import StepStartEvent
        self._bus.publish(StepStartEvent(
            step_id=self._step_id,
            step_name=getattr(self._step_schema, "name", "") or self._step_id,
        ))
    except Exception:
        logger.debug("[SM {}] emit STEP_START failed", self._step_id)

def _emit_step_failed(self, error: str) -> None:
    if self._bus is None:
        return
    try:
        from gimbal.events.types import StepFailedEvent
        self._bus.publish(StepFailedEvent(
            step_id=self._step_id,
            error=error[:500] if error else "",
            phase=self._state.value,
        ))
    except Exception:
        logger.debug("[SM {}] emit STEP_FAILED failed", self._step_id)

def _emit_http_response(self, call_spec, result) -> None:
    if self._bus is None:
        return
    try:
        from gimbal.events.types import HttpResponseEvent
        # 防御：HTTP 失败时 result.status 是字符串（"timeout"/"RequestError"），
        # int() 会抛 ValueError 吞掉整个事件；只把能转 int 的状态码写事件
        raw_status = getattr(result, "status", None)
        try:
            status_code = int(raw_status) if raw_status is not None else 0
        except (ValueError, TypeError):
            status_code = 0
        self._bus.publish(HttpResponseEvent(
            step_id=self._step_id,
            method=call_spec.method,
            url=call_spec.url,
            status_code=status_code,
            duration_ms=float(getattr(result, "duration_ms", 0.0) or 0.0),
            response_body=getattr(result, "body", None),
        ))
    except Exception:
        logger.debug("[SM {}] emit HTTP_RESPONSE failed", self._step_id)
```

`event_bus` 为 None 时静默跳过；`publish` 失败也不影响主流程（log debug）。

## 内部辅助方法

```python
def _advance(self, to: StepState, *, reason: str = "") -> None:
    """从当前状态合法地转换到 to：校验在 VALID_TRANSITIONS 白名单内，触发
    on_transition 回调（日志告警吞错），更新 self._state；
    非法抛 InvalidTransitionError。"""
    ...

def _try_advance(self, to: StepState, *, reason: str = "") -> bool:
    """包装 _advance：捕获 InvalidTransitionError / AlreadyTerminalError 时
    返回 False，成功推进返回 True。"""
    ...

def _run_phase(self, phase: str) -> PhaseResult:
    """通过 dispatcher 分发执行指定 phase 的所有策略，返回聚合的 PhaseResult。"""
    ...

def _has_phase(self, phase: str) -> bool:
    """检查 step schema 的 strategy 列表中是否至少存在一条 phase 等于 phase 的策略。"""
    ...

def _do_http_call(self) -> StrategyResult:
    """合成 _CallSpec 交给 CallExecutor 执行。

    - 修复 #6：删除 "http://<service_key>" 兜底（产生幽灵 URL），
      当 _service_base_url 为空时显式失败。
    - 修复 B2：优先取 scratch.request_body（被 BEFORE_REQUEST 阶段 Assign 修改过），
      没有则用原 body。
    - 触发 HTTP_REQUEST 事件 + HTTP_BEFORE_SEND hook（hook 中断则返回 ERROR）。
    - 调用 dispatcher.dispatch。
    - 触发 HTTP_RESPONSE 事件 + HTTP_AFTER_RECV hook。
    """
    ...
```

## 使用示例

### 基础用法

```python
from gimbal.statemachine.engine import StepStateMachine
from gimbal.strategy.dispatcher import StrategyDispatcher
from gimbal.context.views import StepContextAdapter

# 构造依赖
dispatcher = StrategyDispatcher(...)
view = StepContextAdapter(step_ctx)

# 构造状态机
sm = StepStateMachine(
    step_id="step-001",
    step_schema=step,
    dispatcher=dispatcher,
    view=view,
    service_base_url="http://user-service",
)

# 状态转换回调（可选）
def on_transition(from_s, to_s, reason):
    print(f"{from_s.value} -> {to_s.value} ({reason})")

sm = StepStateMachine(
    step_id="step-001",
    step_schema=step,
    dispatcher=dispatcher,
    view=view,
    on_transition=on_transition,
)

# 执行
result = sm.run()
print(f"status={result.status} duration_ms={result.duration_ms:.2f}")
if not result.passed:
    print(f"error_phase={result.error_phase} error={result.error}")
```

### 集成 Hook 与 Event

```python
sm = StepStateMachine(
    step_id="step-001",
    step_schema=step,
    dispatcher=dispatcher,
    view=view,
    service_base_url="http://user-service",
    hook_registry=hook_registry,    # 可选；用于 HTTP_BEFORE_SEND / HTTP_AFTER_RECV
    event_bus=event_bus,            # 可选；用于 publish StepStart/End/Failed + HttpRequest/Response
)
result = sm.run()
# event_bus 此时已收到：StepStartEvent → (HttpRequestEvent → HttpResponseEvent) → StepEndEvent / StepFailedEvent
```

### 完整 run() 流程

```python
def run(self) -> StepRunResult:
    t_start = datetime.now(timezone.utc)
    self._emit_step_start()                  # 1. STEP_START
    try:
        request_body = getattr(self._step_schema.request, "body", None) or {}
        if request_body:
            self._view.write_scratch("request_body", request_body)   # 2. 初始化 scratch

        self._advance(StepState.BEFORE_REQUEST, reason="start")       # 3. PENDING -> BEFORE_REQUEST

        while not self._state.is_terminal:                            # 4. 内部循环
            handler = self._handlers.get(self._state)
            if handler is None:
                self._advance(StepState.ERROR, reason=f"no handler for {self._state.value}")
                break
            next_state = handler()
            self._advance(next_state, reason=f"{self._state.value} done")
    except Exception as exc:
        self._error = traceback.format_exc()
        self._try_advance(StepState.ERROR, reason=str(exc))           # 5. 异常 -> ERROR

    duration_ms = (datetime.now(timezone.utc) - t_start).total_seconds() * 1000
    if self._state == StepState.FAILED or self._state == StepState.ERROR:
        self._emit_step_failed(self._error or f"final_state={self._state.value}")  # 6a. STEP_FAILED
    else:
        self._emit_step_end(duration_ms)                              # 6b. STEP_END

    return StepRunResult(
        step_id=self._step_id,
        status=self._state.value,
        phase_results=self._phase_results,
        error=self._error,
        error_phase=self._error_phase,
        duration_ms=duration_ms,
    )
```

## StepRunResult

```python
@dataclass
class StepRunResult:
    step_id: str
    status: str                                  # StepState.value 的字符串
    phase_results: list[PhaseResult] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0
    error_phase: Optional[str] = None            # "calling"/"verifying"/"teardown"/None

    @property
    def passed(self) -> bool:
        return self.status == "passed"
```

`error_phase` 字段（修复 #5）让 reporter 能区分失败原因：HTTP 失败（`calling`）、清理失败（`teardown`）。

> **实际写入时机与值**（来自 `statemachine/engine.py`）：
>
> | 阶段 | 何时写 `error_phase` | 值 |
> |------|---------------------|----|
> | `BEFORE_REQUEST` hard-fail | ❌ 不写 | 保持 `None`（handler 直接进 `TEARDOWN`，未赋值 `error_phase`） |
> | `CALLING` HTTP 失败 | ✅ 写 | `"calling"`（同时写 `error = "[calling] ..."`） |
> | `AFTER_REQUEST` hard-fail | ❌ 不写 | 保持 `None` |
> | `VERIFYING` 硬失败 | ❌ 不写 | 保持 `None`（仅通过 `StepState.FAILED` 标识） |
> | `TEARDOWN` 失败但业务通过（B6） | ✅ 写 | `"teardown"`（同时写 `error = "[teardown] ..."`） |
> | 终态为 `ERROR`（框架异常） | ❌ 不写 | 保持 `None`（信息在 `error` 字段） |
>
> 因此 reporter 通过 `error_phase` 能可靠区分的只有 **HTTP 失败** 与 **teardown 失败**；其他阶段的 hard-fail 仅体现为 `status != "passed"`，reporter 应结合 `phase_results` 中 `PhaseResult.hard_failed` 判断具体阶段。

## 设计原则

1. **状态驱动**：所有执行逻辑在 handler 中，状态机只负责流转。
2. **合法性校验**：每次 `_advance` 都校验 `VALID_TRANSITIONS`，非法转换抛 `InvalidTransitionError`。
3. **终态保护**：终态后不允许再跃迁（`VALID_TRANSITIONS[terminal] = frozenset()`）。
4. **自驱动**：调用方只需 `run()`，不感知内部流转。
5. **埋点可选**：`hook_registry` / `event_bus` 不传则不触发（向后兼容）。
6. **Hook 双查询**：枚举名优先，value 兜底——兼容两种调用风格（Issue 9 修复）。
7. **失败容错**：异常被吞，状态机进入 ERROR 而不是崩溃。
8. **teardown 不污染业务结果**：B6 修复——业务阶段全通过 + teardown 失败 → 终态仍 `PASSED`（`error_phase="teardown"`）。
9. **soft 失败不阻断**：Issue 9 修复——VERIFYING 阶段使用 `hard_failed` 而非 `all_passed` 判定，soft 失败不阻断进入 PASSED。
10. **HTTP 错误防御**：result.status 为字符串时（timeout / RequestError）安全 fallback `status_code=0`，避免 `int()` 抛异常吞掉整个事件。
