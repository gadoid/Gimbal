# Runtime 模块

执行层，框架的运行时核心，负责场景的执行调度和事件管理。

## 文件说明

### `context.py`
- `FailureRecord` - 失败记录数据类，记录步骤名、动作类型、错误信息、时间戳
- `ExecutionContext` - 执行上下文，贯穿整个场景执行过程，管理：
  - 变量存储（`set_variable` / `get_variable`）
  - 失败记录（`add_failure`）
  - 断言结果（`add_assertion`）
  - 执行时间统计

### `events.py`
定义事件系统：
- `EventType` - 事件类型枚举（步骤开始/完成/失败、场景开始/完成、断言成功/失败）
- `Event` - 事件数据类，包含事件类型、事件数据、时间戳

### `bus.py`
`EventBus` - 事件总线，实现发布/订阅模式：
- `subscribe(event_type, handler)` - 订阅事件
- `unsubscribe(event_type, handler)` - 取消订阅
- `publish(event)` - 发布事件

### `dispatcher.py`
`ActionDispatcher` - 动作调度器：
- 根据 `Action.type` 将动作分发到对应的 `ActionHandler` 处理器
- 支持通过 `register_handler` 注册自定义处理器

### `executor.py`
`StepExecutor` - 步骤执行器状态机：
- `execute_step(step, context)` - 执行单个步骤
- `execute_scenario(scenario, context)` - 执行整个场景

## 事件流程

```
SCENARIO_STARTED
  └── STEP_STARTED (per step)
        └── [Action Dispatched]
  └── STEP_COMPLETED / STEP_FAILED (per step)
SCENARIO_COMPLETED
```

## 使用示例

```python
from runtime import EventBus, ActionDispatcher, StepExecutor, ExecutionContext

event_bus = EventBus()
dispatcher = ActionDispatcher()
executor = StepExecutor(event_bus, dispatcher)

context = ExecutionContext(scenario_name="Test")
executor.execute_scenario(scenario, context)

print(f"Failures: {len(context.failures)}")
print(f"Assertions: {len(context.assertions)}")
```
