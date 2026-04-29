# Plugins 模块

插件层，提供扩展机制，允许在场景执行过程中拦截事件。

## 文件说明

### `base.py`
`Plugin` - 插件抽象基类，定义插件接口：

**接口方法：**
- `on_event(event)` - 接收事件回调
- `on_start()` - 场景开始前的钩子
- `on_end()` - 场景结束后的钩子

### `response_time.py`
`ResponseTimePlugin` - 响应时间监控插件（示例实现）：

**功能：**
- 监听 `STEP_COMPLETED` 事件
- 从事件数据中提取 HTTP 响应时间
- 与阈值比较，记录慢步骤
- 在 `on_end` 时输出统计报告

**初始化参数：**
- `threshold_ms` - 响应时间阈值（毫秒），默认 1000ms

**输出格式：**
```
[ResponseTimePlugin] Avg: 123.45ms, Max: 567.89ms
[ResponseTimePlugin] Slow steps: ['get_user', 'create_order']
```

## 使用示例

```python
from plugins import Plugin, ResponseTimePlugin
from runtime import EventBus

# 使用内置插件
plugin = ResponseTimePlugin(threshold_ms=2000)
runner.add_plugin(plugin)

# 自定义插件
class CustomPlugin(Plugin):
    def on_event(self, event):
        if event.type == EventType.STEP_FAILED:
            print(f"Step failed: {event.data['step_name']}")

    def on_start(self):
        print("Scenario starting...")

    def on_end(self):
        print("Scenario finished")

runner.add_plugin(CustomPlugin())
```

## 注册流程

```
TestRunner.add_plugin(plugin)
    └── event_bus.subscribe(plugin.on_event)
```

插件通过 `EventBus` 订阅感兴趣的事件类型，在场景执行过程中自动接收回调。
