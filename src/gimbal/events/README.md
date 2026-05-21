# Events 模块

事件总线模块，提供同步内存事件发布/订阅能力。

## 设计理念

### 1. 事件流

```
Publisher ──publish()──▶ EventBus ──subscribe()──▶ Handler
                                   │
                                   ├── event_type → handlers
                                   └── "*" (wildcard) → all handlers
```

### 2. 设计原则

- **同步调用**：publish 后同步调用所有订阅者
- **事件类型自动推断**：根据事件对象的类型或 `event_type` 属性确定类型
- **通配订阅**：支持 `"*"` 订阅所有事件
- **错误隔离**：单个 handler 异常不影响其他 handler

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `bus.py` | `InMemoryEventBus` 事件总线实现 |
| `subscription.py` | 订阅管理（预留） |
| `types.py` | 事件类型定义（预留） |

---

## InMemoryEventBus

```python
class InMemoryEventBus:
    """同步内存事件总线。"""

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """订阅事件。"""
        self._handlers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        """发布事件，同步调用所有订阅者。"""
        pass
```

### EventHandler

```python
EventHandler = Callable[[Any], None]
```

---

## 使用示例

```python
from gimbal.events import InMemoryEventBus

bus = InMemoryEventBus()

# 订阅特定事件
def on_step_complete(event):
    print(f"Step completed: {event.step_id}")

bus.subscribe("step_complete", on_step_complete)

# 订阅所有事件
def on_any_event(event):
    print(f"Received event: {type(event).__name__}")

bus.subscribe("*", on_any_event)

# 发布事件
bus.publish(StepCompleteEvent(step_id="step-001"))
```

---

## 生产环境扩展

生产环境可替换为基于以下技术的实现：

- **asyncio**：异步事件处理
- **Redis**：分布式事件总线
- **Kafka**：高性能消息队列

接口保持不变，只需替换 `InMemoryEventBus` 为对应的实现。

---

## 运行测试

```bash
python -m gimbal.events
```
