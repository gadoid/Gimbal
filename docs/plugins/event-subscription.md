# Event Subscription

> 端到端指南：如何订阅 Gimbal 框架事件 —— 过滤、优先级、同步 / 异步 / 批量、插件热卸载。

## 1. 三种订阅位置

Gimbal 中**所有"看框架发生什么事"**的需求都走 `InMemoryEventBus`：

| 位置 | 用什么订阅 | 说明 |
|---|---|---|
| **插件 on_activate** | `ctx.register_event(...)` | **推荐**。框架帮你把 `plugin_name` 传好 |
| **任意业务代码** | `bus.subscribe(...)` | 拿到 `event_bus` 引用后直接订阅，**必须手动传 `plugin_name`** 否则卸载清不掉 |
| **集成测试** | `bus.subscribe(...)` | 单测/集成测试用 `plugin_name="test"` 即可 |

**口诀**：能用 `ctx.register_event` 就用它；不能（不在插件里）就 `bus.subscribe`。

## 2. 三种调用风格

```python
from gimbal.events import InMemoryEventBus, EventFilter, SubscriptionMode, EventType
from gimbal.events.types import StepStartEvent, StepEndEvent

bus = InMemoryEventBus()

# ── 1. 极简（80% 用法）──
# 只关心事件类型，不带任何额外过滤
def on_step_start(event):
    print(f"Step started: {event.step_id}")

sid = bus.subscribe(on_step_start, "step.start")
# 等价于：bus.subscribe(on_step_start, event_type="step.start")

# ── 2. 显式 EventFilter（中等复杂度）──
# 正则匹配 step.* 所有事件，且仅 run_id="r-001"
bus.subscribe(
    on_step_start,
    filter=EventFilter(
        event_type_pattern=r"step\..*",
        run_id="r-001",
    ),
)

# ── 3. event_type + filter 叠加（罕见）──
# 显式 event_type 覆盖 filter.event_type，其余 filter 字段仍生效
bus.subscribe(
    on_step_start,
    "step.start",                       # 覆盖 → filter.event_type="step.start"
    filter=EventFilter(step_id="x"),    # 仍生效
)
# 实际过滤：event_type == "step.start" AND step_id == "x"
```

## 3. EventFilter 全部字段

```python
class EventFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str | None = None         # 精确类型（"step.start"）
    event_type_pattern: str | None = None # 正则（"step\\..*"）
    run_id: str | None = None
    step_id: str | None = None
    scenario_id: str | None = None
    custom: dict[str, Any] = {}          # 自定义键值，匹配 event 的同名属性
```

所有非 None 字段是 **AND** 关系；任一字段为 None 表示"不参与过滤"。

```python
# 实战：所有 run_id 包含 "prod" 的 step 失败
bus.subscribe(
    on_fail,
    filter=EventFilter(
        event_type="step.failed",
        run_id="prod-*",   # ⚠ 注意：这是精确匹配，不是 glob。run_id 含通配请用 run_id_pattern
    ),
)
# ↑ 当前 InMemoryEventBus 不支持 run_id 的 glob，仅 event_type_pattern 支持正则。
#   其它字段是字面量精确匹配。
```

## 4. 三种订阅模式（SubscriptionMode）

```python
class SubscriptionMode(str, Enum):
    SYNC = "sync"     # 默认；同步阻塞，按 priority 升序执行
    ASYNC = "async"   # 后台线程 fire-and-forget
    BATCH = "batch"   # 攒批，size/interval flush（需 start_batch_loop()）
```

### SYNC（默认）

```python
bus.subscribe(handler, "step.start", mode=SubscriptionMode.SYNC)
# 行为：发布者 publish() 阻塞到所有 SYNC handler 都跑完
# 用途：审计、断言、上下文相关的快速处理
```

### ASYNC

```python
bus.subscribe(handler, "step.end", mode=SubscriptionMode.ASYNC)
# 行为：handler 在新 daemon 线程里跑，publish() 立即返回
# 用途：网络上传、慢 IO、不能阻塞主流程的事
# 注意：handler 内异常**仍会被捕获**记日志，但 publish() 不感知
```

### BATCH

```python
# 步骤 1: bootstrap 时 start_batch_loop
bus.start_batch_loop()   # 启动 flush 线程（按 _batch_interval=1.0s 周期 flush）

# 步骤 2: 注册 batch 订阅
bus.subscribe(batch_handler, "step.end", mode=SubscriptionMode.BATCH)
# 行为：handler 攒批（默认 100 条/批或 1 秒间隔），到点 flush 时逐条调用
# 用途：批量上报、批量落盘、聚合统计

# shutdown 时记得 stop
bus.stop()   # 停止 loop + flush 残余
```

## 5. 优先级

```python
bus.subscribe(handler_a, "step.start", priority=10)  # 先调
bus.subscribe(handler_b, "step.start", priority=100) # 后调
bus.subscribe(handler_c, "step.start", priority=50)  # 中间
```

**数字越小越先调用**。订阅加入后，`_subscriptions` 列表按 priority **升序排序**，每次 publish 也按这个顺序遍历。

注意：
- SYNC 模式严格按 priority 升序串行
- ASYNC 模式在 priority 顺序上并发触发（一个 handler 起一个线程）
- BATCH 模式仅影响"谁先入队"（无实质差异），flush 时按 sub 顺序逐条

## 6. 完整事件类型清单

参考 [modules/events.md](../modules/events.md) 的 "全部事件类型" 表格。常用 7 类：

| 事件 | 何时发 | 关键字段 |
|---|---|---|
| `FrameworkInitEvent` | bootstrap 完成 | `framework_version` |
| `RunStartEvent` / `RunEndEvent` | run 入口 / 出口 | `env`, `mode`, `total`/`passed`/`failed`/`error` |
| `SuiteStartEvent` / `SuiteEndEvent` | suite 入口 / 出口 | `suite_id`, `status` |
| `ScenarioStartEvent` / `ScenarioEndEvent` | scenario 入口 / 出口 | `scenario_id`, `step_count`, `status` |
| `StepStartEvent` / `StepEndEvent` / `StepFailedEvent` | step 入口 / 出口 / 失败 | `step_id`, `step_name`, `duration_ms`, `error` |
| `HttpRequestEvent` / `HttpResponseEvent` | HTTP 调用前后 | `method`, `url`, `status_code`, `duration_ms` |
| `VariablePromotedEvent` | 变量从 step 提升到 scenario | `key`, `from_layer`, `to_layer`, `by_step_id` |
| `PluginActivatedEvent` / `PluginFailedEvent` / `PluginDeactivatedEvent` | 插件生命周期 | `plugin_name`, `error`, `stage` |

事件字符串字面量（`"step.start"`）和 `EventType` 枚举（`EventType.STEP_START`）等价。

## 7. 实战模式

### 7.1 把所有失败 step 落盘 JSON Lines

```python
import json
from pathlib import Path
from gimbal.events import InMemoryEventBus, EventFilter
from gimbal.events.types import StepFailedEvent

def setup_step_failure_logger(bus: InMemoryEventBus, out: Path, plugin_name: str = "step_failure_logger"):
    out.parent.mkdir(parents=True, exist_ok=True)
    fh = open(out, "a", encoding="utf-8")

    def on_fail(event: StepFailedEvent):
        rec = {
            "ts":      event.timestamp.isoformat(),
            "run_id":  event.run_id,
            "step_id": event.step_id,
            "error":   event.error,
            "phase":   event.phase,
        }
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()

    bus.subscribe(
        on_fail,
        filter=EventFilter(event_type="step.failed"),
        plugin_name=plugin_name,    # ← 必须传，否则卸载清不掉
        mode=SubscriptionMode.SYNC, # 主流程一致性
    )
    return fh
```

### 7.2 异步上传 step 响应给监控系统

```python
import httpx
from gimbal.events import InMemoryEventBus, EventFilter, SubscriptionMode

def setup_metrics_uploader(bus: InMemoryEventBus, endpoint: str, plugin_name: str = "metrics_uploader"):
    client = httpx.Client(timeout=5.0)

    def on_step_end(event):
        try:
            client.post(endpoint, json={
                "run_id": event.run_id,
                "step_id": event.step_id,
                "status": event.status,
                "duration_ms": event.duration_ms,
            })
        except Exception:
            pass  # 主流程不该被埋点阻塞

    bus.subscribe(
        on_step_end,
        filter=EventFilter(event_type="step.end"),
        mode=SubscriptionMode.ASYNC,  # ← 异步，不阻塞主流程
        plugin_name=plugin_name,
    )
```

### 7.3 批量聚合

```python
from collections import Counter
from gimbal.events import InMemoryEventBus, EventFilter, SubscriptionMode

status_counter: Counter[str] = Counter()

def setup_batch_aggregator(bus: InMemoryEventBus, plugin_name: str = "batch_aggregator"):
    def on_step_end(event):
        status_counter[event.status] += 1

    bus.subscribe(
        on_step_end,
        filter=EventFilter(event_type="step.end"),
        mode=SubscriptionMode.BATCH,  # ← 攒批
        plugin_name=plugin_name,
    )

# bootstrap 时：
bus.start_batch_loop()  # 启动 flush 线程
# shutdown 时：
bus.stop()
```

### 7.4 在插件内订阅

```python
from gimbal.core.plugin import Plugin, PluginContext, PluginManifest
from gimbal.events.types import StepEndEvent, StepFailedEvent
from gimbal.events.subscription import SubscriptionMode

class MyAuditPlugin(Plugin):
    manifest = PluginManifest(
        name="my_audit", version="1.0.0",
        entry_point="my_audit.plugin:MyAuditPlugin",
    )

    def on_activate(self, ctx: PluginContext) -> None:
        # 同步：审计（确保写入落盘）
        ctx.register_event(StepEndEvent, self._audit_end, priority=10)

        # 异步：上报（不阻塞主流程）
        ctx.register_event(
            StepFailedEvent,
            self._report_failure,
            mode=SubscriptionMode.ASYNC,
        )

    def _audit_end(self, event: StepEndEvent) -> None:
        # 同步：写到本地 + DB
        ...

    def _report_failure(self, event: StepFailedEvent) -> None:
        # 异步：HTTP 上报
        ...
```

### 7.5 在集成测试中订阅

```python
from gimbal.events import InMemoryEventBus, EventFilter
from gimbal.events.types import StepEndEvent

def test_step_end_event():
    bus = InMemoryEventBus()
    received: list[StepEndEvent] = []

    def collect(event):
        received.append(event)

    bus.subscribe(collect, "step.end", plugin_name="test")

    # ... 跑一次 run ...
    bus.publish(StepEndEvent(step_id="s1", status="passed", duration_ms=10.0))

    assert len(received) == 1
    assert received[0].step_id == "s1"
```

## 8. 自己发事件

```python
# 在插件里：
ctx.emit(MyCustomEvent(payload=...))

# 在任意地方（不推荐，除非有合理理由）：
bus.publish(MyCustomEvent(...))
```

`MyCustomEvent` 必须是 `FrameworkEvent` 子类，`event_type` 用 `Literal` 限定：

```python
from typing import Literal
from pydantic import ConfigDict
from gimbal.events.types import FrameworkEvent

class MyCustomEvent(FrameworkEvent):
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_type: Literal["my.custom"] = "my.custom"
    payload: dict = {}
```

## 9. 异常隔离

handler 抛异常**被吞掉**记日志，**不影响其它订阅者**：

```python
# handler A 抛异常 → 日志记录 handler error → handler B / C 仍正常收到
```

**这是设计**，不是 bug。事件总线是"通知型"，订阅者失败不能让主流程挂掉。

## 10. 热卸载（name-based）

```python
# 一次清空该插件所有订阅
removed = bus.unsubscribe_plugin("my_plugin")
# removed = 实际移除的订阅数
```

**`PluginContext` 内部不维护订阅 id 列表**——只用 `event_count` / `hook_count` 计数器供日志打印。框架按 `plugin_name` 字段在 `_subscriptions` 列表里筛选删除。

**约束**：
- 直接调 `bus.subscribe(handler, "x")` **不传 `plugin_name`** 的订阅是"匿名"的，`unsubscribe_plugin` 拿不到
- **总是**用 `ctx.register_event(...)`（在插件内）或显式 `bus.subscribe(..., plugin_name="...")`（在插件外）

## 11. 完整 API 速查

```python
# ── InMemoryEventBus ──
bus.subscribe(
    handler,
    event_type: str | None = None,
    *,
    filter: EventFilter | None = None,
    mode: SubscriptionMode = SubscriptionMode.SYNC,
    plugin_name: str | None = None,
    priority: int = 100,
) -> str                              # subscription_id

bus.unsubscribe(subscription_id: str) -> bool
bus.unsubscribe_plugin(plugin_name: str) -> int       # 关键：按 name 清
bus.list_subscriptions(plugin_name: str | None = None) -> list[Subscription]
bus.publish(event: Any) -> None
bus.start_batch_loop() -> None
bus.stop() -> None

# ── PluginContext ──
ctx.register_event(event_type, handler, *, priority=100, mode=None) -> str
ctx.register_hook(point, handler, *, priority=100, description="") -> str
ctx.emit(event: FrameworkEvent) -> None
```

## 12. 错误排查速查

| 现象 | 可能原因 |
|---|---|
| 订阅收不到事件 | `event_type` 拼错 / `EventFilter` 字段不匹配（精确匹配） |
| handler 在 BATCH 模式但没攒满 | 没调 `bus.start_batch_loop()` |
| handler 静默失败 | 抛异常被吞，看 `[EventBus] Handler error` 日志 |
| 卸载后还有 handler 跑 | 没传 `plugin_name` / 用了 `bus.subscribe(handler, "x")` 匿名调用 |
| `assert bus._subscriptions` 为空 | 用 `bus.list_subscriptions(plugin_name="...")` 调试 |
