# 扩展指南

## 概述

Gimbal 是一个为"可扩展"而设计的测试框架。框架内置的扩展点包括：

- **自定义策略 Executor**：添加新的 `kind` 策略
- **自定义报告器 Reporter**：添加新的报告格式（HTML / JSON / IM 通知 / 平台上传等）
- **自定义插件 Plugin**：通过 `PluginLoader` 流水线接入，订阅 Event / 注册 Hook / 注册 Strategy
- **自定义 Authenticator**：添加新的登录方式
- **自定义 ContentStore 后端**：替换资产仓库的存储介质
- **自定义 ResourceProvider**：添加新的外部资源句柄

下面按常见扩展点逐一给出最小可运行示例。

---

## 1. 添加自定义策略 Executor

### 1.1 实现 `StrategyExecutor`

```python
from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus


class MyCustomExecutor(StrategyExecutor):
    kind = "my_custom"  # 唯一标识，对应 StrategyBase.kind

    def execute(
        self,
        spec: "StrategyBase",
        view: "StrategyContextView",
    ) -> StrategyResult:
        try:
            # 业务逻辑
            return StrategyResult(
                status=StrategyStatus.PASSED,
                strategy_id=getattr(spec, "name", self.kind),
                message="执行成功",
            )
        except Exception as exc:
            # 不要让异常逃出；包裹进 StrategyResult
            return StrategyResult(
                status=StrategyStatus.ERROR,
                strategy_id=getattr(spec, "name", self.kind),
                error=str(exc),
            )
```

### 1.2 注册到 `StrategyDispatcher`

```python
from gimbal.strategy.dispatcher import StrategyDispatcher
from gimbal.core.hooks import HookRegistry

dispatcher = StrategyDispatcher(hook_registry=HookRegistry())
dispatcher.register(MyCustomExecutor())
```

或者在 bootstrap 阶段（如果是 plugin 形式）通过 `PluginContext` 注册。

### 1.3 规范

- `kind` 必须全局唯一。
- 不允许抛出异常，所有异常必须包裹进 `StrategyResult`。
- 执行耗时由 dispatcher 统一写入 `result.duration_ms`，executor 内部不必再计时。
- 通过 `view.promote_variable()` 把需要跨 Step 复用的数据写入 context。
- 软失败由 dispatcher 根据 `spec.onFailure` 自动标记 `soft=True`。

---

## 2. 通过插件订阅 Event / 注册 Hook / 注册 Strategy（推荐）

插件是当前推荐的最干净的扩展方式——通过 `PluginLoader` 流水线自动接入框架，并支持热卸载。

### 2.1 目录布局

```
plugins/
└── my_plugin/
    ├── plugin.yaml         # manifest
    └── my_plugin/
        ├── __init__.py
        └── plugin.py       # 实现类
```

### 2.2 写一个 `plugin.yaml`

```yaml
name: my_plugin
version: 0.1.0
entry_point: my_plugin.plugin:MyPlugin
description: "示例插件：监听 step 事件并打印"
gimbal_version: ">=0.1.0"
capabilities:
  - tracing
dependencies: []
config_schema:
  log_prefix:
    type: string
    default: "[my_plugin]"
default_config:
  log_prefix: "[my_plugin]"
```

### 2.3 实现 `Plugin` 子类

```python
from gimbal.core.plugin import Plugin, PluginContext
from gimbal.core.hooks import HookPoint
from gimbal.events.types import StepStartEvent, StepEndEvent


class MyPlugin(Plugin):
    # manifest 由 PluginLoader 在 _load_one 阶段从 spec 注入
    manifest = None  # 占位，实际由框架注入

    def on_load(self) -> None:
        # 可选：加载期初始化（读文件、开资源）
        pass

    def on_activate(self, ctx: PluginContext) -> None:
        # 1. 订阅事件
        ctx.register_event(
            "step.start",
            self._on_step_start,
            priority=50,
        )
        ctx.register_event(
            "step.end",
            self._on_step_end,
            priority=50,
        )

        # 2. 注册 Hook（HTTP 出站前注入 header）
        ctx.register_hook(
            HookPoint.HTTP_BEFORE_SEND,
            self._inject_header,
            priority=10,
            description="my_plugin: inject X-My-Plugin",
        )

    def on_deactivate(self) -> None:
        # 可选：清理资源
        pass

    # ── handlers ──
    def _on_step_start(self, event: StepStartEvent) -> None:
        print(f"{self.manifest.name}: step start -> {event.step_id}")

    def _on_step_end(self, event: StepEndEvent) -> None:
        print(f"{self.manifest.name}: step end   -> {event.step_id} status={event.status}")

    def _inject_header(self, payload: dict) -> None:
        # in-place 修改（in-place 修改需要显式 return payload 才会被标记为 modified）
        headers = payload.setdefault("headers", {})
        headers["X-My-Plugin"] = self.manifest.name
        return payload
```

### 2.4 启用插件

在 `gimbal.yaml` 中通过 `plugins:` 段指定白名单：

```yaml
plugins:
  - my_plugin
```

或在 CLI 启动时通过 `-P` 启用：

```bash
gimbal run launch examples/hello/scenario.yaml -P my_plugin
```

`PluginLoader` 会自动完成发现 → 依赖解析 → 加载 → 激活四阶段。卸载时按 `plugin_name` 精确清理其所有 Event / Hook 注册。

---

## 3. 通过 pip 安装的插件（entry point 形式）

如果想把插件发布为独立包，在 `pyproject.toml` 注册 entry point 即可被自动发现：

```toml
[project.entry-points."gimbal.plugins"]
my_plugin = "my_package.plugin:MyPlugin"
```

`PluginLoader.discover()` 会扫描 `gimbal.plugins` 组并把 entry point 包装为 `PluginSpec`，其余流程与本地 plugin 完全一致。

---

## 4. 添加自定义 Report Reporter

### 4.1 实现 `Reporter` 接口

```python
from gimbal.reporter.base import Reporter
from gimbal.core.runner import RunResult


class MyCustomReporter(Reporter):
    name = "my_custom"  # 唯一标识

    def on_run_start(self, framework_ctx) -> None:
        ...

    def on_scenario_start(self, scenario_id: str) -> None:
        ...

    def on_scenario_end(self, result) -> None:
        ...

    def on_step_start(self, step_id: str) -> None:
        ...

    def on_step_end(self, result) -> None:
        ...

    def on_finalize(self, summary: RunResult) -> list:
        # 返回 ReportArtifact 列表
        ...
```

### 4.2 注册到 `ReporterRegistry`

```python
from gimbal.reporter.registry import ReporterRegistry

registry = ReporterRegistry()
registry.register(MyCustomReporter())
```

`Engine.run()` 在执行期间调用 `reporter_runtime.begin_all()` / `finalize_all()` 驱动所有 reporter；产物作为 `ReportArtifact` 列表返回给 CLI 打印。

### 4.3 在 CLI 中启用

```bash
gimbal run launch examples/hello/scenario.yaml --reporter my_custom --report-dir ./report
```

---

## 5. 添加自定义 Authenticator

### 5.1 实现 `Authenticator` 子类

```python
from gimbal.auth.authenticator import Authenticator


class MyAuthenticator(Authenticator):
    kind = "my_auth"   # 对应 schema.auth 中的 kind

    def login(self, session: "AuthSession") -> None:
        # 业务登录逻辑
        session.token = "..."
```

### 5.2 注册到 `AuthRegistry`

```python
from gimbal.auth.registry import AuthRegistry

registry = AuthRegistry()
registry.register(MyAuthenticator())
```

或在 plugin 的 `on_activate` 中调用 `auth_registry.register(...)`。

---

## 6. 替换资产仓库后端（ContentStore）

`AssetStore` 接受一个实现了 `ContentStore` 协议的后端。框架内置 `LocalFsContentStore`，可以自行实现：

```python
from typing import BinaryIO
from gimbal.repository.store import ContentStore
from gimbal.repository.models import AssetRef, AssetRecord


class S3ContentStore:
    def push_blob(self, digest: str, data: bytes | BinaryIO) -> None: ...
    def pull_blob(self, digest: str) -> bytes: ...
    def has_blob(self, digest: str) -> bool: ...
    def put_manifest(self, ref: AssetRef, digest: str, record_json: str) -> None: ...
    def get_manifest(self, ref: AssetRef) -> tuple[str, str] | None: ...
    def delete_manifest(self, ref: AssetRef) -> bool: ...
    def list_tags(self, namespace: str, name: str) -> list[str]: ...
    def list_assets(self, namespace: str | None = None) -> list[AssetRecord]: ...
    def find_by_digest(self, digest: str) -> list[AssetRecord]: ...


from gimbal.repository.store import AssetStore
store = AssetStore(backend=S3ContentStore(...))
```

`asset` CLI 子命令组走"快路径"，需要 CLI 与 `AssetStore` 共享同一后端；可通过 `--registry` / 自定义入口扩展。

---

## 7. 添加新的执行阶段（StrategyPhase）

如需新增 `StrategyPhase`：

1. 在 `schema/strategy.py` 的 `StrategyPhase` 枚举加新值。
2. 在 `statemachine/states.py` 的 `StepState` 枚举加新状态。
3. 在 `statemachine/engine.py` 的状态机 handler 字典中注册新阶段的处理函数。
4. 在 `StrategyDispatcher.register()` 中加入处理该 phase 的 executor（如果有新策略类型）。

> 这是一项破坏性较大的改动，建议先在 fork 内验证后再合入。

---

## 8. 扩展配置来源

`ConfigLoader` 负责合并多来源配置（CLI > env > mode > gimbal.yaml > 默认值）。要插入新的来源：

```python
from gimbal.config.loader import ConfigLoader


class MyConfigLoader(ConfigLoader):
    def load(self, cli_ctx) -> "BootstrapConfig":
        base = super().load(cli_ctx)
        # 合并自定义来源
        # 注意：返回的 BootstrapConfig 是 frozen=True，需要 model_copy(update=...)
        return base.model_copy(update={"extra_field": "..."})
```

---

## 9. 最佳实践

1. **保持职责单一**：每个扩展只关注一个功能（策略 / 报告 / 认证 / 后端）。
2. **使用插件而非全局副作用**：能写成 Plugin 就写成 Plugin，可享受自动激活 / 热卸载 / 配置注入。
3. **错误处理**：所有异常必须包裹进结果对象（`StrategyResult` / `ReportArtifact` / `CheckResult` 等），不要让异常逃出到主流程。
4. **日志记录**：使用 `gimbal.log.get_logger(__name__)` 记录日志，与框架保持一致的 logging 路径。
5. **类型注解**：提供完整 type hint，便于框架 / 插件代码做静态检查。
6. **单元测试**：为扩展编写单元测试；插件类可以用 `bootstrap()` 真实启动一次验证。
7. **plugin_name**：所有通过 `PluginContext` 注册的 Event / Hook / Strategy 都自带 `plugin_name`，框架按名字精确清理，不要手动管理 id 列表。
