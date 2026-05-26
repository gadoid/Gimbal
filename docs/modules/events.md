# Events 模块

> 事件系统模块，提供同步内存事件总线

## 目录结构

```
gimbal/events/
├── __init__.py
├── bus.py          # InMemoryEventBus
├── subscription.py # 订阅管理
└── types.py        # 事件类型定义
```

## 核心组件

### InMemoryEventBus

同步内存事件总线：

```python
class InMemoryEventBus:
    """同步内存事件总线"""

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """订阅事件"""
        self._handlers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        """发布事件"""
        event_type = getattr(event, "event_type", type(event).__name__)
        # 调用所有订阅者
        for handler in self._handlers.get(event_type, []):
            handler(event)
        # 通配订阅 "*" 接收所有事件
        for handler in self._handlers.get("*", []):
            handler(event)
```

## 事件类型

框架预定义的事件类型：

```python
# Scenario 事件
ScenarioStartedEvent
ScenarioCompletedEvent

# Step 事件
StepStartedEvent
StepCompletedEvent

# 变量提升事件
PromotionEvent

# 自定义事件
CustomEvent
```

## 使用示例

```python
from gimbal.events.bus import InMemoryEventBus
from gimbal.events.types import ScenarioStartedEvent

# 创建事件总线
event_bus = InMemoryEventBus()

# 订阅事件
def on_scenario_started(event: ScenarioStartedEvent):
    print(f"Scenario started: {event.scenario_id}")

event_bus.subscribe("ScenarioStartedEvent", on_scenario_started)

# 发布事件
event_bus.publish(ScenarioStartedEvent(
    timestamp=datetime.utcnow(),
    run_id="run-001",
    suite_id="suite-001",
    scenario_id="sc-001",
))
```

## 设计原则

1. **同步调用**: publish 后同步调用所有订阅者
2. **通配订阅**: 支持 `*` 订阅所有事件
3. **异常隔离**: 订阅者异常不影响其他订阅者
4. **可替换**: 生产环境可替换为 asyncio / Redis / Kafka 实现