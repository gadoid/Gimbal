# Writing a Plugin

> 端到端指南：从零开始写一个 Gimbal 插件，涵盖清单、入口点、生命周期、上下文、热卸载。

## 1. 插件是什么

Gimbal 的插件是**可热装载的扩展**，在 `bootstrap()` 阶段被 `PluginLoader` 发现 → 加载 → 激活；在 `shutdown()` 阶段统一卸载。

插件通过三种方式参与框架：
- **订阅事件**（`InMemoryEventBus`）：看到 / 监听框架里发生的事
- **注册 hook**（`HookRegistry`）：在框架的关键节点插入自己的逻辑（甚至能中断主流程）
- **注册 strategy**（`StrategyDispatcher`）：自定义一种 `StrategyKind`

> 详细 API 见 `docs/modules/plugins.md`（架构参考）。本篇专注于**实战开发**。

## 2. 目录结构

### 2.1 Filesystem 插件（最常用）

把插件放在项目根的 `plugins/` 目录：

```
gimbal_project/
├── gimbal.yaml
├── plugins/
│   └── my_logger/                # 插件目录（名字随意）
│       ├── plugin.yaml           # 清单文件（必须）
│       ├── plugin.yml            # 也可（按顺序找：plugin.yaml → plugin.yml → plugin.toml）
│       └── my_logger/            # Python 包
│           ├── __init__.py
│           └── plugin.py         # 入口类
```

### 2.2 Entry Point 插件（pip 安装）

发布到 PyPI 的第三方插件，在 `pyproject.toml` 声明 entry point：

```toml
[project]
name = "gimbal-slack-notifier"
version = "0.1.0"

[project.entry-points."gimbal.plugins"]
slack_notifier = "gimbal_slack_notifier.plugin:SlackNotifierPlugin"
```

只要 `pip install`，loader 就能发现。

## 3. plugin.yaml / plugin.toml

**必需字段**：`name`、`version`、`entry_point`

```yaml
# plugins/my_logger/plugin.yaml
name: my_logger
version: 1.0.0
entry_point: my_logger.plugin:MyLoggerPlugin
description: 把所有 step 执行日志落盘到 ./.gimbal-log/
author: your-name
homepage: https://example.com/my_logger

# 依赖其它插件（按名字）
dependencies:
  - core_utils

# 声明 gimbal 兼容版本（语义化）
gimbal_version: ">=1.0,<2.0"

# 声明能力（用于 PluginCategory 路由 / 过滤 / 校验）
capabilities:
  - logging
  - file_io

# 用户配置 schema（提示用，校验在插件内部）
config_schema:
  output_dir:
    type: string
    description: 日志落盘目录
  level:
    type: string
    enum: [debug, info, warning, error]

# 用户配置默认值（与 gimbal.yaml 的 plugin_configs 合并后注入 ctx.config）
default_config:
  output_dir: ./.gimbal-log
  level: info
```

`entry_point` 格式：`"module.path:ClassName"`，loader 内部走 `importlib.import_module(...)` + `getattr(module, "ClassName")` 拿到类。

## 4. 入口类

```python
# plugins/my_logger/my_logger/plugin.py
from __future__ import annotations
from pathlib import Path
from typing import Any

from gimbal.core.plugin import Plugin, PluginContext, PluginManifest
from gimbal.events.types import StepStartEvent, StepEndEvent, StepFailedEvent
from gimbal.core.hooks import HookPoint


# 1. 类属性：声明 manifest
class MyLoggerPlugin(Plugin):
    manifest = PluginManifest(
        name="my_logger",
        version="1.0.0",
        entry_point="my_logger.plugin:MyLoggerPlugin",  # 冗余（loader 已解析），便于手动 import
        description="Step 执行日志落盘",
        capabilities=["logging"],
        default_config={"output_dir": "./.gimbal-log", "level": "info"},
    )

    def __init__(self) -> None:
        super().__init__()
        self._log_dir: Path | None = None
        self._fh: Any = None

    # 2. 可选：加载阶段（轻量 init，不应注册回调）
    def on_load(self) -> None:
        # 解析 manifest 之外的东西（不依赖 ctx）
        pass

    # 3. 必须：激活阶段（注册 event / hook / strategy）
    def on_activate(self, ctx: PluginContext) -> None:
        # 用户配置（与 default_config 合并后）
        self._log_dir = Path(ctx.config["output_dir"])
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._fh = open(self._log_dir / "steps.log", "a", encoding="utf-8")

        # === 事件订阅 ===
        # 写法 1：极简（只关心类型）
        ctx.register_event("step.start", self._on_step_start, priority=50)

        # 写法 2：显式 EventFilter（指定 run_id 等）
        from gimbal.events.subscription import EventFilter, SubscriptionMode
        ctx.register_event(
            StepEndEvent,
            self._on_step_end,
            filter=EventFilter(event_type="step.end", run_id="sentinel"),
            mode=SubscriptionMode.ASYNC,   # 后台线程跑
        )

        # 写法 3：所有 step.failed（精确类型用 enum 值字符串）
        ctx.register_event(StepFailedEvent, self._on_step_failed)

        # === Hook 注册 ===
        # HTTP 发出前：可改写 payload（method/url/headers/body）
        ctx.register_hook(
            HookPoint.HTTP_BEFORE_SEND,
            self._sign_request,
            priority=100,
            description="给所有出向请求加 X-Logger 头",
        )

        # === 自己发事件（可选） ===
        # ctx.emit(MyCustomEvent(...))

    # 4. 可选：卸载阶段
    def on_deactivate(self) -> None:
        if self._fh:
            self._fh.flush()
            self._fh.close()
            self._fh = None

    # ── 事件 handlers ──
    def _on_step_start(self, event: StepStartEvent) -> None:
        self._write(f"[start] step={event.step_id} name={event.step_name}")

    def _on_step_end(self, event: StepEndEvent) -> None:
        self._write(f"[end]   step={event.step_id} status={event.status} dur={event.duration_ms}ms")

    def _on_step_failed(self, event: StepFailedEvent) -> None:
        self._write(f"[FAIL]  step={event.step_id} error={event.error[:200]}")

    # ── Hook handler ──
    def _sign_request(self, payload: dict) -> dict:
        """HTTP_BEFORE_SEND hook。返回 dict 替换 payload；返回 None 保留原值。"""
        headers = dict(payload.get("headers", {}))
        headers["X-Logger"] = self.manifest.name
        return {**payload, "headers": headers}

    def _write(self, line: str) -> None:
        if self._fh:
            self._fh.write(line + "\n")
            self._fh.flush()
```

### 必须遵守

1. **类属性 `manifest`**：子类必须定义（类型注解 `# type: ignore[assignment]` 可消除 mypy 抱怨）。
2. **`on_activate` 必须实现**（`@abstractmethod`）。
3. **`on_activate` 中**所有注册（`register_event` / `register_hook`）**必须传 `plugin_name=ctx.plugin_name`**——`PluginContext` 帮你自动传了，所以你**不需要**手动传，但你**必须**用 `ctx.register_*` 而不是直接调 `event_bus.subscribe()`。原因：直接调用会绕过 `plugin_name`，**卸载时清不掉**。
4. **可抛异常**：`on_load` / `on_activate` 可抛异常，框架会把插件置为 `FAILED` 状态。`on_deactivate` 不应抛（异常会被吞掉记日志，但**不阻止**状态机置为 `DEACTIVATED`）。

## 5. PluginContext 完整 API

```python
class PluginContext:
    plugin_name: str                  # 框架注入的插件名（= manifest.name）
    config: dict                      # 用户配置（default_config + user_configs 合并）
    event_bus: EventBusProtocol       # 通过 Protocol 持有的事件总线（可换分布式）
    hook_registry: HookRegistryProtocol
    plugin_registry: Any              # 通用插件注册表（按需使用）

    # 计数器：仅用于日志，不参与清理
    event_count: int                  # activate 后打印 "events=N"
    hook_count: int

    # 订阅 event（核心 API）
    def register_event(
        self,
        event_type: str,              # 字符串或事件类（str(EventType.X)）
        handler: Callable[[Any], None],
        *,
        priority: int = 100,          # 数字越小越先调用
        mode: SubscriptionMode | None = None,  # None = SYNC
    ) -> str                          # 返回 subscription_id（一般不用）

    # 注册 hook
    def register_hook(
        self,
        point: HookPoint | str,       # HookPoint 枚举或字符串
        handler: Callable[[Any], Any],
        *,
        priority: int = 100,
        description: str = "",
    ) -> str

    # 发事件（插件也可以往总线上发）
    def emit(self, event: FrameworkEvent) -> None
```

## 6. 三种调用风格（订阅事件）

`event_bus.subscribe()` / `ctx.register_event()` 支持三种调用风格（**`event_type` 优先**于 `filter.event_type`）：

```python
# 1. 极简（80% 场景）
ctx.register_event("step.start", on_step_start)

# 2. 显式 EventFilter（中等复杂度）
from gimbal.events.subscription import EventFilter
ctx.register_event(
    on_step_start,
    filter=EventFilter(event_type="step.*", run_id="r-001"),
)

# 3. 叠加（罕见）：event_type 覆盖 filter.event_type
ctx.register_event(
    on_step_start,
    "step.start",                       # 最终生效的 type
    filter=EventFilter(step_id="x"),    # 其余 filter 字段仍生效
)
# 等价于：filter.event_type="step.start" + step_id="x"
```

## 7. Hook vs Event：什么时候用哪个

| | Event | Hook |
|---|---|---|
| 语义 | 通知（"事情发生了"） | 介入（"我在这里加一段逻辑"） |
| 中断主流程 | ❌ 不可能 | ✅ 抛 `HookSignal.STOP` |
| 改写 payload | ❌ event 是 `frozen=True` | ✅ 返回新对象替换 |
| 数量 | 一个点可有多个订阅 | 一个点可有多个 handler |
| 模式 | SYNC/ASYNC/BATCH | SYNC（按 priority 升序串行） |

**口诀**：
- 想要 **看** 框架里发生什么 → 订阅 event
- 想要 **改** / **拦** 框架行为 → 注册 hook
- 想要 **"事件发生时我也做点别的"** → 两者皆可，event 更轻量

## 8. 注册自定义 StrategyExecutor（可选）

```python
from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus
from gimbal.strategy.dispatcher import StrategyDispatcher

class GrepExecutor(StrategyExecutor):
    kind = "grep"   # 在 scenario.json 中用 {"kind": "grep", ...} 引用

    def execute(self, spec, view):
        # view 是 StrategyContextView
        body = view.resolve(spec.target, default="")
        if spec.pattern not in str(body):
            return StrategyResult(
                status=StrategyStatus.FAILED,
                strategy_id=getattr(spec, "name", self.kind),
                message=f"pattern {spec.pattern!r} not found in {spec.target!r}",
            )
        return StrategyResult(
            status=StrategyStatus.PASSED,
            strategy_id=getattr(spec, "name", self.kind),
        )

class MyLoggerPlugin(Plugin):
    manifest = PluginManifest(
        name="my_logger", version="1.0.0",
        entry_point="my_logger.plugin:MyLoggerPlugin",
    )

    def on_activate(self, ctx: PluginContext) -> None:
        # 通过 ctx.plugin_registry 拿到 dispatcher
        dispatcher: StrategyDispatcher = ctx.plugin_registry.get("strategy_dispatcher")
        dispatcher.register(GrepExecutor())
        # ...
```

> 实际更常见的做法是**单文件脚本**用 CLI `gimbal run launch` + 一份 YAML，不写插件就拿到全部内置 strategy。仅在需要**新 strategy 类型**或**多公司共享的横切逻辑**时才写插件。

## 9. 加载失败怎么办

- `on_load` 抛异常 → 插件置 `FAILED`，loader 跳过其激活
- `on_activate` 抛异常 → 插件置 `FAILED`，**已注册的 event/hook 仍会被清理**（loader 的兜底）
- 任何阶段的失败都会发 `PluginFailedEvent`

```python
# 调试：跑 gimbal self-check 看框架级自检
# 调试：跑一次场景，从 log 看 [Plugin:xxx] load failed / activate failed
```

## 10. 卸载语义（必读）

`bootstrap.shutdown()` 调用 `PluginLoader.deactivate_all()`，**唯一卸载入口**：

1. 对每个插件调 `plugin.on_deactivate()`
2. 对每个插件调 `event_bus.unsubscribe_plugin(plugin_name)`（按 name 批量清空该插件的所有订阅）
3. 对每个插件调 `hook_registry.unregister_plugin(plugin_name)`（同上）
4. `DeactivateReport` 记录成功 / 失败

**PluginContext 内只记 `event_count` / `hook_count` 两个计数器**——**不维护 id 列表**。旧实现里 `registered_event_ids: list[str]` 等字段是死代码，从未被消费，已移除。

因此：
- **不要**自己存 id 列表去手动 `unsubscribe()`，框架会按 name 兜底
- **必须**用 `ctx.register_event()` / `ctx.register_hook()`，让框架知道 plugin_name
- **必须**用 `ctx.emit()` 发事件，**不要**直接调 `event_bus.publish()`（虽然 `event_bus` 是公开字段，但绕开 ctx 会让事件"匿名"）

## 11. 完整 lifecycle 图

```
DISCOVERED           (loader.find_manifest 找到 plugin.yaml)
     │
     ▼
LOADED               (loader.load_all: import + 实例化 + on_load)
     │
     ▼
ACTIVATING           (loader.activate_all: 构造 ctx + 调 on_activate)
     │  ── 异常 ──▶ FAILED
     ▼
ACTIVATED            (ctx.event_count / hook_count 供日志)
     │ ... 框架运行 ...
     ▼
DEACTIVATING         (shutdown: 调 on_deactivate)
     │  ── 异常被吞（仍 DEACTIVATED）
     ▼
DEACTIVATED          (loader 同时 unsubscribe_plugin + unregister_plugin)
```

## 12. 完整可运行示例

见 `docs/plugins/examples/`（仓库中如有）—— 一个 logger 插件 + 一个 HTTP 签名插件 + 一个 strategy 插件。
