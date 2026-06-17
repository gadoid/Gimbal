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
- 异步订阅使用固定大小线程池（`ThreadPoolExecutor`，`max_workers=8`），避免无限创建线程

```python
class InMemoryEventBus:
    """进程内事件总线。

    特性：
      - filter: event_type / event_type_pattern / run_id / step_id / scenario_id / custom
      - priority: 数字越小越先调用
      - mode: SYNC（同步） / ASYNC（异步线程） / BATCH（攒批）
      - 插件热卸载：unsubscribe_plugin 一次清理
    """

    def __init__(self) -> None:
        # 内部状态：_subscriptions, _batch_queue(默认 size=100/interval=1.0s),
        # _batch_thread, _async_executor(ThreadPoolExecutor max_workers=8)
        ...

    # ── 订阅 ──────────────────────────────────────
    def subscribe(
        self,
        handler: EventHandler,
        event_type: Optional[str] = None,
        *,
        filter: Optional[EventFilter] = None,
        mode: SubscriptionMode = SubscriptionMode.SYNC,
        plugin_name: Optional[str] = None,
        priority: int = 100,
    ) -> str:
        """三种调用风格（从最简到最强）：

        1. 极简（80% 用法）：只关心事件类型
            bus.subscribe(handler, "step.start")

        2. 显式 EventFilter（中等复杂度：正则 / run_id / step_id 过滤）
            bus.subscribe(handler, filter=EventFilter(
                event_type="step.*", step_id="step-000"))

        3. event_type 与 filter 叠加（罕见：filter 是基础，event_type 覆盖）
            bus.subscribe(handler, "step.start", filter=EventFilter(step_id="x"))
            # 最终 filter: event_type="step.start" + step_id="x"
        """
        ...

    # ── 取消订阅 ──────────────────────────────────
    def unsubscribe(self, subscription_id: str) -> bool:
        """按 subscription_id 取消单条订阅。返回 True 表示成功，False 表示未找到。"""
        ...

    def unsubscribe_plugin(self, plugin_name: str) -> int:
        """按插件名批量取消其名下所有订阅（用于插件热卸载），返回被移除数量。"""
        ...

    def list_subscriptions(self, plugin_name: Optional[str] = None) -> list[Subscription]:
        """列出当前所有订阅或按 plugin_name 过滤后的订阅快照（拷贝）。"""
        ...

    # ── 发布 ──────────────────────────────────────
    def publish(self, event: Any) -> None:
        """发布一个事件，按订阅 mode 派发：
            - SYNC：同步调用 handler
            - ASYNC：提交到 _async_executor 线程池（bus stop 后回退同步）
            - BATCH：入队 _batch_queue，达 batch_size 时 flush
        """
        ...

    def start_batch_loop(self) -> None:
        """启动后台批处理循环线程：每 _batch_interval 秒 flush 一次。"""
        ...

    def stop(self) -> None:
        """关闭总线：停止批处理循环、刷新剩余事件、关闭 ASYNC 线程池并等待 pending 任务。幂等。"""
        ...
```

`event_type` 与 `filter` 合并规则：`event_type` 优先，会通过 `filter.model_copy(update={"event_type": event_type})` 覆盖 `filter.event_type`（避免修改入参）。

### Subscription / EventFilter / SubscriptionMode

```python
class SubscriptionMode(str, Enum):
    SYNC = "sync"           # 同步阻塞
    ASYNC = "async"         # 异步 fire-and-forget（提交到线程池）
    BATCH = "batch"         # 攒批，达 size/interval 时 flush


EventHandler = Callable[[Any], None]


class EventFilter(BaseModel):
    """事件过滤规则（所有条件 AND，任一字段 None 表示不参与）。"""
    model_config = ConfigDict(extra="forbid")

    event_type: Optional[str] = None
    event_type_pattern: Optional[str] = None    # 正则（re.fullmatch）
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    scenario_id: Optional[str] = None
    custom: dict[str, Any] = Field(default_factory=dict)

    def matches(self, event: Any) -> bool:
        """判断 event 是否通过当前过滤规则：依次匹配 event_type、
        event_type_pattern(re.fullmatch，避免 "step.*" 误匹配 "stepper.*")、
        run_id、step_id、scenario_id 以及 custom 字典中的键值对。
        """
        ...


class Subscription(BaseModel):
    """一个事件订阅的不可变记录。"""
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    subscription_id: str          # uuid
    event_filter: EventFilter
    handler: EventHandler
    mode: SubscriptionMode = SubscriptionMode.SYNC
    plugin_name: Optional[str] = None    # 用于热卸载
    priority: int = 100                  # 数字越小越先调用
```

**EventFilter 匹配细节**：
- `event_type`：精确匹配 `event.event_type`
- `event_type_pattern`：使用 `re.fullmatch`（不是 `match`），避免 `"step.*"` 误匹配 `"stepper.*"`
- `run_id` / `step_id` / `scenario_id`：精确匹配
- `custom`：字典中每个 (k, v) 对应 `getattr(event, k) == v`，全等才放行

### Protocol 抽象

```python
@runtime_checkable
class EventBusProtocol(Protocol):
    """事件总线协议（PluginContext 持有的类型）。

    PluginContext 实际使用的方法子集：
        - subscribe:   注册事件订阅
        - unsubscribe: 取消单个订阅
        - publish:     发布事件
    """
    def subscribe(handler, event_type=None, *, filter=None,
                  mode=..., plugin_name=None, priority=100) -> str
    def unsubscribe(subscription_id: str) -> bool
    def publish(event: Any) -> None


@runtime_checkable
class HookRegistryProtocol(Protocol):
    """钩子注册表协议（与 EventBusProtocol 对偶）。"""
    def register(point, handler, *, priority=100,
                 plugin_name=None, description="") -> str
    def unregister(hook_id: str) -> bool
```

只声明 `PluginContext` 实际调用的最小子集，避免泄露实现细节。`runtime_checkable` 允许运行时 `isinstance(obj, EventBusProtocol)` 检查。

## 事件类型

### EventType 枚举（与 HookPoint 对称）

```python
class EventType(str, Enum):
    """让"订阅事件"和"注册 hook"的 API 看起来一样：

        bus.subscribe(handler, EventType.STEP_START)
        hook_registry.register(HookPoint.STEP_START, handler)

    字符串字面量仍然有效：
        bus.subscribe(handler, "step.start")
    """
    # 框架生命周期
    FRAMEWORK_INIT = "framework.init"
    FRAMEWORK_TEARDOWN = "framework.teardown"

    # Run 生命周期
    RUN_START = "run.start"
    RUN_END = "run.end"
    # Run 级元数据（CI/CD / git / 构建上下文等），由 CLI 在 bootstrap 之后 publish
    RUN_META = "run.meta"

    # Suite 生命周期
    SUITE_START = "suite.start"
    SUITE_END = "suite.end"

    # Scenario 生命周期
    SCENARIO_START = "scenario.start"
    SCENARIO_END = "scenario.end"

    # Step 生命周期
    STEP_START = "step.start"
    STEP_END = "step.end"
    STEP_FAILED = "step.failed"

    # HTTP 调用
    HTTP_REQUEST = "http.request"
    HTTP_RESPONSE = "http.response"

    # Context 提升
    CONTEXT_PROMOTION = "context.promotion"  # 兼容旧订阅；新订阅应使用 VARIABLE_PROMOTED
    VARIABLE_PROMOTED = "variable.promoted"

    # 插件生命周期
    PLUGIN_ACTIVATED = "plugin.activated"
    PLUGIN_FAILED = "plugin.failed"
    PLUGIN_DEACTIVATED = "plugin.deactivated"
```

字符串字面量与枚举值等价：
```python
bus.subscribe(handler, "step.start")             # 字符串
bus.subscribe(handler, EventType.STEP_START)     # 枚举
```

### FrameworkEvent 基类

```python
class FrameworkEvent(BaseModel):
    """所有框架事件的基类。

    子类必须显式声明 event_type 字面量，例如：
        class StepStartEvent(FrameworkEvent):
            event_type: Literal["step.start"] = "step.start"
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_type: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
| `RunEndEvent` | `run.end` | `total`, `passed`, `failed`, `error`, `skipped` (默认 0) |
| `RunMetaEvent` | `run.meta` | `meta: dict[str, Any]`（CI/CD / git / 触发人 / 业务自定义 KV） |
| `SuiteStartEvent` | `suite.start` | `suite_id`, `suite_name` |
| `SuiteEndEvent` | `suite.end` | `suite_id`, `status` |
| `ScenarioStartEvent` | `scenario.start` | `scenario_id`, `scenario_name`, `step_count`, `suite_id=""` |
| `ScenarioEndEvent` | `scenario.end` | `scenario_id`, `status`, `step_count`, `suite_id=""`, `meta: dict` |
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
- `RunMetaEvent.meta` 是开放 dict，reporter 可在 `bootstrap()` 之后订阅以获得 CI/git 等元信息，保持 "一切皆事件" 架构一致性。
- 旧名 `ContextPromotionEvent = VariablePromotedEvent`（deprecated 别名，保留以兼容旧订阅）。

## 使用示例

### 基础订阅

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

# 2. 复杂过滤（正则 + 特定 run_id + 异步模式）
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

# 3. 叠加：event_type 覆盖 filter.event_type
bus.subscribe(on_step_start, "step.start",
              filter=EventFilter(step_id="x"))

# 4. 发布
bus.publish(StepStartEvent(
    step_id="step-000",
    step_name="login",
    run_id="run-001",
))
```

### BATCH 模式（攒批上报）

```python
# BATCH 订阅：handler 只在批处理 flush 时被调用一次，参数是 event 列表
def on_batch(events: list):
    report_to_remote(events)

bus.subscribe(
    on_batch,
    EventType.STEP_END,
    mode=SubscriptionMode.BATCH,
    plugin_name="reporter",
)

# 必须启动批处理循环，否则事件只在达 batch_size=100 时 flush
bus.start_batch_loop()

# ... 业务执行 ...

bus.stop()   # 停止循环、flush 剩余、关闭 ASYNC 线程池
```

### 插件热卸载

```python
# 插件注册时携带 plugin_name
bus.subscribe(handler, EventType.STEP_START, plugin_name="auth-plugin")
bus.subscribe(handler, EventType.STEP_END,   plugin_name="auth-plugin")

# 插件卸载：一次清掉所有相关订阅
removed = bus.unsubscribe_plugin("auth-plugin")
print(f"Removed {removed} subscriptions")
```

## 设计原则

1. **同步默认**：`SubscriptionMode.SYNC` 是默认行为，简单可预期。
2. **异常隔离**：单个 handler 抛异常被 `logger.exception` 记录但吞掉，不影响其它订阅者（保证事件总线"绝不向上传播异常"）。
3. **name-based 清理**：`unsubscribe_plugin(name)` 一次清掉该插件的所有订阅；不维护 id 列表。
4. **Protocol 解耦**：`PluginContext` 持有 Protocol 而非具体类，可替换为分布式实现。
5. **frozen 事件**：`FrameworkEvent` 设为 `frozen=True, extra="forbid"`，事件一旦发出不可修改。
6. **枚举与字符串等价**：`EventType` 是 `str, Enum`，值仍是 dot.notation 字符串，用户可任选风格。
7. **线程池化**：ASYNC 模式用 `ThreadPoolExecutor(max_workers=8)` 替代裸线程列表，`stop()` 关闭并等待 pending 任务；flush 失败时回退到同步避免事件丢失。
8. **fullmatch 过滤**：`event_type_pattern` 用 `re.fullmatch`，避免 `"step.*"` 误匹配 `"stepper.*"`。
