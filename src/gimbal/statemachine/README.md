# Statemachine 模块

状态机引擎，负责维护 Step 执行过程中的状态流转和合法性校验。

## 设计理念

### 1. 无副作用

状态机**只维护状态**，不持有任何业务逻辑：

- 不知道"如何执行策略"
- 只负责"我现在处于哪个状态、下一步可以去哪里"
- 具体业务逻辑在 `Runner` / `ScenarioRunner` 的执行循环里

### 2. 状态流转图

```
                    ┌─────────────┐
                    │   PENDING   │
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              │              ▼
   ┌────────────────┐      │      ┌─────────────┐
   │ BEFORE_REQUEST │──────┘      │   SKIPPED   │
   └───────┬────────┘             └─────────────┘
           │
           ▼
   ┌────────────────┐
   │    CALLING     │──────────┐
   └───────┬────────┘          │
           │                    ▼
           ▼            ┌────────────────┐
   ┌────────────────┐  │    TEARDOWN    │
   │ AFTER_REQUEST  │──┤                │
   └───────┬────────┘  └───────┬────────┘
           │                    │
           ▼                    ▼
   ┌────────────────┐  ┌────────────────┐
   │   VERIFYING    │  │    PASSED     │◄─┐
   └───────┬────────┘  └────────────────┘  │
           │                                 │
           ▼                    ┌────────────┘
   ┌────────────────┐          │
   │    TEARDOWN    │──────────┘
   └───────┬────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌────────┐  ┌────────┐
│ PASSED │  │ FAILED │
└────────┘  └────────┘
```

### 3. 跃迁合法性

通过 `VALID_TRANSITIONS` 字典硬编码所有合法跃迁，非法跃迁直接抛出异常。

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `states.py` | 状态枚举与合法跃迁表 |
| `engine.py` | 状态机引擎实现 |
| `exceptions.py` | 异常定义 |

---

## 状态定义

### StepState 枚举

```python
class StepState(str, Enum):
    # 等待/就绪
    PENDING = "pending"          # 创建但尚未调度

    # 执行阶段
    BEFORE_REQUEST = "before_request"   # Assign / SQL 注入
    CALLING = "calling"                 # HTTP 发出、等待响应
    AFTER_REQUEST = "after_request"     # Extract 提取字段
    VERIFYING = "verifying"             # Assertion / DBChecker
    TEARDOWN = "teardown"              # SQL 清理 / Chaos 恢复

    # 终态
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"      # 框架级异常
    SKIPPED = "skipped"
```

### 状态属性

| 属性 | 说明 |
|------|------|
| `is_terminal` | 是否终态（PASSED/FAILED/ERROR/SKIPPED） |
| `is_running` | 是否运行态（BEFORE_REQUEST/CALLING/AFTER_REQUEST/VERIFYING/TEARDOWN） |

### 终态集合

```python
_TERMINAL_STATES = frozenset({
    StepState.PASSED,
    StepState.FAILED,
    StepState.ERROR,
    StepState.SKIPPED,
})
```

### 运行态集合

```python
_RUNNING_STATES = frozenset({
    StepState.BEFORE_REQUEST,
    StepState.CALLING,
    StepState.AFTER_REQUEST,
    StepState.VERIFYING,
    StepState.TEARDOWN,
})
```

---

## 合法跃迁表

```python
VALID_TRANSITIONS: dict[StepState, frozenset[StepState]] = {
    # PENDING 可以跳转到 BEFORE_REQUEST 或直接 SKIPPED
    StepState.PENDING: frozenset({
        StepState.BEFORE_REQUEST,
        StepState.SKIPPED,
    }),

    # BEFORE_REQUEST 可以跳转到 CALLING（成功）
    # 或 FAILED（前置策略失败）、TEARDOWN（前置失败有 teardown）、ERROR
    StepState.BEFORE_REQUEST: frozenset({
        StepState.CALLING,
        StepState.FAILED,
        StepState.TEARDOWN,
        StepState.ERROR,
    }),

    # CALLING 可以跳转到 AFTER_REQUEST（成功）
    # 或 FAILED、TEARDOWN、ERROR
    StepState.CALLING: frozenset({
        StepState.AFTER_REQUEST,
        StepState.FAILED,
        StepState.TEARDOWN,
        StepState.ERROR,
    }),

    # AFTER_REQUEST 可以跳转到 VERIFYING（成功）
    # 或 FAILED、TEARDOWN、ERROR
    StepState.AFTER_REQUEST: frozenset({
        StepState.VERIFYING,
        StepState.TEARDOWN,
        StepState.FAILED,
        StepState.ERROR,
    }),

    # VERIFYING 可以跳转到 PASSED（无 teardown）、TEARDOWN（有 teardown）
    # 或 FAILED、ERROR
    StepState.VERIFYING: frozenset({
        StepState.TEARDOWN,
        StepState.PASSED,
        StepState.FAILED,
        StepState.ERROR,
    }),

    # TEARDOWN 只能跳转到终态
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

---

## StepStateMachine 类

### 核心方法

| 方法 | 说明 |
|------|------|
| `advance(to, reason)` | 将状态推进到目标状态 |
| `try_advance(to, reason)` | 尝试跃迁，失败返回 False（不抛异常） |

### 只读属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `state` | `StepState` | 当前状态 |
| `is_terminal` | `bool` | 是否终态 |
| `history` | `tuple[TransitionRecord]` | 跃迁历史 |

### TransitionRecord

跃迁审计记录：

```python
@dataclass
class TransitionRecord:
    from_state: StepState    # 源状态
    to_state: StepState      # 目标状态
    reason: str              # 跃迁原因
    at: datetime             # 跃迁时间
```

### TransitionHook

跃迁回调函数类型：

```python
TransitionHook = Callable[[StepState, StepState, str], None]
# (from_state, to_state, reason)
```

### 使用示例

```python
from gimbal.statemachine import StepStateMachine, StepState

# 创建状态机
sm = StepStateMachine(
    step_id="step-001",
    on_transition=lambda f, t, r: print(f"[{f}] → [{t}]: {r}")
)

# 驱动状态流转
sm.advance(StepState.BEFORE_REQUEST, reason="start")
sm.advance(StepState.CALLING, reason="before_request done")
# ... 执行 HTTP 调用
sm.advance(StepState.AFTER_REQUEST, reason="call done")
sm.advance(StepState.VERIFYING, reason="after_request done")
sm.advance(StepState.PASSED, reason="all assertions passed")

# 检查终态
assert sm.is_terminal
print(f"Final state: {sm.state}")
print(f"History: {sm.history}")
```

---

## 异常

| 异常 | 说明 |
|------|------|
| `InvalidTransitionError` | 非法状态跃迁 |
| `AlreadyTerminalError` | 对已处于终态的状态机发起跃迁 |

### InvalidTransitionError

```python
class InvalidTransitionError(StateMachineError):
    def __init__(self, from_state: str, to_state: str) -> None:
        super().__init__(
            f"Invalid transition: {from_state!r} → {to_state!r}"
        )
        self.from_state = from_state
        self.to_state = to_state
```

---

## 与核心模块的集成

**设计原则**：状态机持有执行所需的全部依赖（dispatcher、view、step schema），自己驱动整个流程直到终态。调用方只需要 `sm.run()`，不感知内部如何流转。

```
Engine.run()
    │
    └── ScenarioRunner.run()
            │
            └── StepRunner.run()
                    │
                    ├── 创建 StepContext
                    ├── 构造 StepStateMachine（注入全部依赖）
                    └── 调用 sm.run()

StepStateMachine.run() 【状态机内部自驱动】
    │
    ├── _advance(PENDING → BEFORE_REQUEST)
    │
    └── while not is_terminal:
            ├── handler = _handlers[current_state]
            ├── next_state = handler()    # handler 返回下一个状态
            └── _advance(next_state)

    各状态 handler:
        _handle_before_request() → CALLING 或 TEARDOWN
        _handle_calling()         → AFTER_REQUEST 或 TEARDOWN
        _handle_after_request()  → VERIFYING 或 TEARDOWN
        _handle_verifying()      → PASSED/FAILED 或 TEARDOWN
        _handle_teardown()       → PASSED/FAILED
```

---

## 运行测试

```bash
python -m gimbal.statemachine.engine
```
