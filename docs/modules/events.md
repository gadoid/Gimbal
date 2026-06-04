# Events 模块

> 事件系统模块：进程内事件总线、订阅管理、事件类型定义、Protocol 抽象

## 目录结构

```
gimbal/events/
├── __init__.py        # 公共 API 导出
├── bus.py             # InMemoryEventBus
├── subscription.py    # Subscription / EventFilter / SubscriptionMode
├── protocols.py       # EventBusProtocol / HookRegistryProtocol
└── types.py           # FrameworkEvent / EventType / 所有具体事件类
```

## 设计理念

Event 与 Hook 形成对照：
- **Hook**（`core/hooks.py`）= 介入型（interposable），可中断主流程
- **Event**（`events/`）= 通知型（fire-and-forget），订阅者无法影响主流程

事件总线的实现可替换：`PluginContext` 通过 `EventBusProtocol` 持有引用，生产可换为 Redis/Kafka/gRPC 等分布式实现而插件代码无感。

## 核心组件

### InMemoryEventBus

进程内事件总线，支持：
- 多种过滤条件（event_type / 正则 / run_id / step_id / scenario_id / custom）
- 多种订阅模式（SYNC / ASYNC / BATCH）
- 优先级（数字越小越先调用）
- 插件热卸载（按 name 批量取消）

```python
class InMemoryEventBus:
    def subscribe(
        handler: EventHandler,
        event_type: Optional[str] = None,
        *,
        filter: Optional[EventFilter] = None,
        mode: SubscriptionMode = SubscriptionMode.SYNC,
        plugin_name: Optional[str] = None,
        priority: int = 100,
    ) -> str:
        """三种调用风格：

        1. 极简（80% 用法）：只关心事件类型
            bus.subscribe(handler, "step.start")

        2. 显式 EventFilter（中等复杂度）
            bus.subscribe(handler, filter=EventFilter(
                event_type="step.*", step_id="step-000"))

        3. 叠加（罕见）
            bus.subscribe(handler, "step.start",
                          filter=EventFilter(step_id="x"))
            # 最终 filter: event_type="step.start" + step_id="x"
        """

    def unsubscribe(subscription_id: str) -> bool
    def unsubscribe_plugin(plugin_name: str) -> int   # 按 name 批量取消
    def list_subscriptions(plugin_name=None) -> list[Subscription]
    def publish(event: Any) -> None
    def start_batch_loop() -> None                    # BATCH 模式才需要
    def stop() -> None                               # 停 batch loop、flush
```

`event_type` 与 `filter` 合并规则：`event_type` 优先，会覆盖 `filter.event_type`。

### Subscription / EventFilter / SubscriptionMode

```python
class SubscriptionMode(str, Enum):
    SYNC = "sync"           # 同步阻塞
    ASYNC = "async"         # 异步 fire-and-forget（后台线程）
    BATCH = "batch"         # 攒批，按 size/interval flush


EventHandler = Callable[[Any], None]


class EventFilter(BaseModel):
    """事件过滤规则（所有条件 AND，任一字段 None 表示不参与）。"""
    model_config = ConfigDict(extra="forbid")

    event_type: Optional[str] = None
    event_type_pattern: Optional[str] = None    # 正则
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    scenario_id: Optional[str] = None
    custom: dict[str, Any] = Field(default_factory=dict)

    def matches(self, event: Any) -> bool: ...


class Subscription(BaseModel):
    """一个事件订阅的不可变记录。"""
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    subscription_id: str
    event_filter: EventFilter
    handler: EventHandler
    mode: SubscriptionMode = SubscriptionMode.SYNC
    plugin_name: Optional[str] = None
    priority: int = 100
```

### Protocol 抽象

```python
@runtime_checkable
class EventBusProtocol(Protocol):
    """事件总线协议（PluginContext 持有的类型）。"""
    def subscribe(handler, event_type=None, *, filter=None,
                  mode=..., plugin_name=None, priority=100) -> str
    def unsubscribe(subscription_id: str) -> bool
    def publish(event: Any) -> None


@runtime_checkable
class HookRegistryProtocol(Protocol):
    """Hook 注册表协议（与 EventBusProtocol 对偶）。"""
    def register(point, handler, *, priority=100,
                 plugin_name=None, description="") -> str
    def unregister(hook_id: str) -> bool
```

只声明 `PluginContext` 实际调用的最小子集，避免泄露实现细节。`runtime_checkable` 允许运行时 `isinstance(obj, EventBusProtocol)` 检查。

## 事件类型

### EventType 枚举（与 HookPoint 对称）

```python
class EventType(str, Enum):
    """让"订阅事件"和"注册 hook"的 API 看起来一样。"""
    FRAMEWORK_INIT = "framework.init"
    FRAMEWORK_TEARDOWN = "framework.teardown"
    RUN_START = "run.start"
    RUN_END   = "run.end"
    SUITE_START / SUITE_END
    SCENARIO_START / SCENARIO_END
    STEP_START  / STEP_END  / STEP_FAILED
    HTTP_REQUEST  = "http.request"
    HTTP_RESPONSE = "http.response"
    CONTEXT_PROMOTION = "context.promotion"     # 兼容旧订阅
    VARIABLE_PROMOTED = "variable.promoted"     # 新订阅应使用
    PLUGIN_ACTIVATED / PLUGIN_FAILED / PLUGIN_DEACTIVATED
```

字符串字面量与枚举值等价：
```python
bus.subscribe(handler, "step.start")             # 字符串
bus.subscribe(handler, EventType.STEP_START)     # 枚举
```

### FrameworkEvent 基类

```python
class FrameworkEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_type: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    run_id: Optional[str] = None
```

子类必须显式声明 `event_type` 字面量：
```python
class StepStartEvent(FrameworkEvent):
    event_type: Literal["step.start"] = "step.start"
    scenario_id: str = ""
    step_id: str
    step_name: str
    strategy_kind: str = ""           # 由 ContextManager 填充
```

### 全部事件类型

| 事件 | event_type | 关键字段 |
|---|---|---|
| `FrameworkInitEvent` | `framework.init` | `framework_version` |
| `FrameworkTeardownEvent` | `framework.teardown` | — |
| `RunStartEvent` | `run.start` | `env`, `mode` |
| `RunEndEvent` | `run.end` | `total`, `passed`, `failed`, `error` |
| `SuiteStartEvent` | `suite.start` | `suite_id`, `suite_name` |
| `SuiteEndEvent` | `suite.end` | `suite_id`, `status` |
| `ScenarioStartEvent` | `scenario.start` | `scenario_id`, `scenario_name`, `step_count`, `suite_id=""` |
| `ScenarioEndEvent` | `scenario.end` | `scenario_id`, `status`, `step_count`, `suite_id=""` |
| `StepStartEvent` | `step.start` | `step_id`, `step_name`, `scenario_id=""`, `strategy_kind=""` |
| `StepEndEvent` | `step.end` | `step_id`, `status`, `duration_ms`, `assertion_count`, `assertion_passed`, `promotion_count`, `error_brief` |
| `StepFailedEvent` | `step.failed` | `step_id`, `error`, `phase` |
| `HttpRequestEvent` | `http.request` | `step_id`, `method`, `url`, `request_body`, `request_headers` |
| `HttpResponseEvent` | `http.response` | `step_id`, `method`, `url`, `status_code`, `duration_ms`, `response_body` |
| `VariablePromotedEvent` | `variable.promoted` | `key`, `from_layer`, `to_layer`, `by_step_id`, `by_scenario_id`, `overwrote_previous`, `reason` |
| `PluginActivatedEvent` | `plugin.activated` | `plugin_name`, `version`, `capabilities` |
| `PluginFailedEvent` | `plugin.failed` | `plugin_name`, `error`, `stage` |
| `PluginDeactivatedEvent` | `plugin.deactivated` | `plugin_name` |

**字段填充策略**：
- `scenario_id=""` / `suite_id=""` / `strategy_kind=""` 等字段在子模块（state machine / ScenarioRunner）直接发事件时为空，由 `ContextManager.project_step_*()` / `project_scenario_*()` 之类的投影函数在 archive 时统一填充。
- 旧名 `ContextPromotionEvent = VariablePromotedEvent`（deprecated 别名，保留以兼容旧订阅）。

## 使用示例

```python
from gimbal.events import (
    InMemoryEventBus, EventType, EventFilter, SubscriptionMode,
    StepStartEvent, StepEndEvent,
)

bus = InMemoryEventBus()

# 1. 极简订阅
def on_step_start(event: StepStartEvent):
    print(f"Step started: {event.step_id}")

bus.subscribe(on_step_start, EventType.STEP_START)

# 2. 复杂过滤（正则 + 特定 run_id）
bus.subscribe(
    on_step_start,
    filter=EventFilter(
        event_type_pattern=r"step\..*",
        run_id="run-001",
    ),
    mode=SubscriptionMode.ASYNC,
    plugin_name="my_plugin",
    priority=50,
)

# 3. 发布
bus.publish(StepStartEvent(
    step_id="step-000",
    step_name="login",
    run_id="run-001",
))
```

## 设计原则

1. **同步默认**：`SubscriptionMode.SYNC` 是默认行为，简单可预期。
2. **异常隔离**：单个 handler 抛异常被吞掉记入日志，不影响其它订阅者。
3. **name-based 清理**：`unsubscribe_plugin(name)` 一次清掉该插件的所有订阅；不维护 id 列表。
4. **Protocol 解耦**：`PluginContext` 持有 Protocol 而非具体类，可替换为分布式实现。
5. **frozen 事件**：`FrameworkEvent` 设为 `frozen=True, extra="forbid"`，事件一旦发出不可修改。
6. **枚举与字符串等价**：`EventType` 是 `str, Enum`，值仍是 dot.notation 字符串，用户可任选风格。
