# Core 模块

> 核心执行引擎模块：bootstrap / shutdown 入口、Hook 系统、Plugin 抽象、Engine / Runner

## 目录结构

```
gimbal/core/
├── __init__.py
├── bootstrap.py        # bootstrap() / shutdown() 入口、Configuration 容器
├── runner.py          # Engine 执行引擎
├── scenario_runner.py # ScenarioRunner、StepRunner、ScenarioRunResult
├── asset_resolver.py  # 资产解析器（外层：CLI/Suite 拉取完整 scenario）
├── asset_materializer.py  # 资产物化器（内层：递归还原 Ref → 数据类对象）
├── hooks.py           # HookPoint / Hook / HookResult / HookRegistry / HookTriggerer
├── plugin.py          # Plugin / PluginContext / PluginManifest / PluginState
└── server.py          # 服务端（待实现）
```

## 启动与关闭

### bootstrap()

框架启动**唯一入口**：

```python
def bootstrap(cli_ctx: CLIContext) -> Configuration:
    """加载优先级: gimbal.yaml → env → mode → cli → 环境变量

    步骤：
        1. 配置日志系统（最先，在任何 logger 调用之前）
        2. 多来源配置合并 → BootstrapConfig
        3. 初始化基础设施（EventBus / Archive / ContextManager /
           Dispatcher / HookRegistry / PluginRegistry / AuthRegistry）
        4. 发现 / 加载 / 激活插件
        5. 触发 FRAMEWORK_INIT hook（插件可在此注册全局监听、初始化连接池等）
        6. 返回 Configuration
    """
```

**不**创建任何层级 Context（由 `Engine.run()` 负责）。

### shutdown()

`bootstrap()` 的对偶函数。框架关闭唯一入口：

```python
def shutdown(configuration: Configuration) -> None:
    """步骤：
        1. 触发 FRAMEWORK_TEARDOWN 钩子
        2. 走 PluginLoader.deactivate_all() 统一卸载所有插件
        3. 兜底清空 hook_registry（覆盖绕过 Plugin.register_hook 的注册）
        4. 停 EventBus
    """
```

`deactivate_all()` 返回 `DeactivateReport`，调用方按需处理失败/成功统计。

### Configuration

`bootstrap()` 的唯一产出，`shutdown()` 的唯一输入：

```python
@dataclass(frozen=True)
class Configuration:
    """持有所有基础设施引用与已激活插件。

    字段分类：
      - 配置快照:    cfg
      - 认证状态:    auth_registry        （运行期 token 容器，唯一可变）
      - 上下文管理:  ctx_manager
      - 策略调度:    dispatcher
      - 事件总线:    event_bus
      - 归档:        archive
      - 插件设施:    hook_registry / plugin_registry
      - 插件实例:    plugins
    """
    cfg: BootstrapConfig
    auth_registry: Any                 # gimbal.auth.registry.AuthRegistry
    ctx_manager: "ContextManager"
    dispatcher: Any                    # StrategyDispatcher
    event_bus: Any
    archive: Any
    hook_registry: "HookRegistry"
    plugin_registry: Any               # PluginRegistry
    plugins: tuple["Plugin", ...] = field(default_factory=tuple)
```

`frozen=True`：产出后不可修改，Engine 只读取。**唯一例外是 `auth_registry`**——它本身是不可变引用，但其内部 `_sessions` 字典在运行期会变（登录/刷新会写入 token）。

`auth_registry` 字段用 `Any` 而非强类型以避免循环导入；运行时由 `AuthManager` 解释。

## Hook 系统（`core/hooks.py`）

框架级 Hook 是**介入型**（interposable）的扩展点，与 Event 的**通知型**（fire-and-forget）形成对照。

### HookPoint

```python
class HookPoint(str, Enum):
    """框架所有可埋点的位置。"""
    # 框架生命周期
    FRAMEWORK_INIT    = "framework.init"
    FRAMEWORK_TEARDOWN= "framework.teardown"
    # Run / Suite / Scenario / Step 生命周期
    RUN_START = "run.start"
    RUN_END   = "run.end"
    SUITE_START / SUITE_END
    SCENARIO_START / SCENARIO_END
    STEP_START / STEP_END / STEP_FAILED
    # HTTP 调用前后
    HTTP_BEFORE_SEND  = "http.before_send"   # payload: {method,url,headers,body,ctx}
    HTTP_AFTER_RECV   = "http.after_recv"    # payload: {method,url,status,headers,body,duration_ms,ctx}
    # Strategy 调用前后
    STRATEGY_BEFORE   = "strategy.before"
    STRATEGY_AFTER    = "strategy.after"
```

新增埋点只需：加枚举值 + 在主流程调一次 `fire(HookPoint.XXX, payload)`，无需改其它代码。

### Hook / HookResult

```python
@dataclass
class Hook:
    """一条 hook 注册记录"""
    hook_id: str                        # uuid
    point: HookPoint
    handler: Callable[[Any], Any]
    priority: int = 100                 # 越小越先执行
    plugin_name: Optional[str] = None   # 用于热卸载
    description: str = ""


@dataclass
class HookResult:
    stopped: bool = False
    stop_reason: str = ""
    stop_plugin: Optional[str] = None
    modified: bool = False              # 是否有 handler 改写/返回了新对象
    errors: list[dict] = field(default_factory=list)

    def __bool__(self) -> bool:
        return not self.stopped          # if not triggerer.fire(...): return
```

### HookSignal.STOP

Handler 抛 `HookSignal.STOP(reason)` 即可中断主流程。`HookSignal` 类作为命名空间承载 `STOP` 异常类。

### HookRegistry

```python
class HookRegistry:
    def register(point, handler, *, priority=100, plugin_name=None, description="") -> str
    def unregister(hook_id) -> bool
    def unregister_plugin(plugin_name) -> int   # 按 name 批量注销
    def list_hooks(point=None, plugin_name=None) -> list[Hook]
    def trigger(point, payload) -> HookResult   # 按 priority 升序执行
    def clear() -> None                         # 兜底用：清空所有 hook
```

`point` 参数接受 `HookPoint` 枚举或字符串，字符串会内部归一化。

执行规则：
- 同一 `point` 下多 handler 按 `priority` 升序
- 任何 handler 抛 `HookSignal.STOP` → 立即终止后续 handler 与主流程
- handler 异常被吞掉记入 `result.errors`，不影响其它 hook
- handler 返回新对象 → 替换 `payload`

### HookTriggerer

```python
class HookTriggerer:
    def fire(self, point: HookPoint, payload: Any) -> HookResult
```

轻量级 `fire` 包装。常用模式：

```python
result = triggerer.fire(HookPoint.HTTP_BEFORE_SEND, payload)
if not result:        # __bool__ → not self.stopped
    return            # 被某个 hook 拦截
# payload 已被 hook 改写
```

## Plugin 系统（`core/plugin.py`）

`Plugin` 是所有插件的抽象基类。**它本身不知道 EventBus / HookRegistry 的存在**，这些由 `PluginContext` 在 `activate()` 时注入。

### PluginState

```python
class PluginState(str, Enum):
    DISCOVERED  = "discovered"     # 找到 manifest
    LOADED      = "loaded"         # 类已 import，实例已创建
    ACTIVATING  = "activating"     # 正在注册回调
    ACTIVATED   = "activated"
    DEACTIVATING= "deactivating"
    DEACTIVATED = "deactivated"
    FAILED      = "failed"         # 任意阶段出错
```

### PluginManifest

```python
@dataclass
class PluginManifest:
    name: str                       # 必需
    version: str                    # 必需
    entry_point: str                # 必需，例 "my_plugin.plugin:MyPlugin"
    description: str = ""
    author: str = ""
    homepage: str = ""
    dependencies: list[str] = field(default_factory=list)
    gimbal_version: str = ""        # 兼容的 gimbal 版本（语义化）
    capabilities: list[str] = field(default_factory=list)
    config_schema: dict = field(default_factory=dict)
    default_config: dict = field(default_factory=dict)
```

### PluginContext

`activate()` 时由框架注入的运行时句柄集合。**通过 Protocol 持有基础设施引用**，因此可以替换为分布式实现而不影响插件代码。

```python
@dataclass
class PluginContext:
    plugin_name: str
    config: dict                    # 用户配置（与 default_config 合并后）
    event_bus: EventBusProtocol
    hook_registry: HookRegistryProtocol
    plugin_registry: Any = None
    # 计数器：仅供 activate 日志打印注册数
    # 实际的清理走 name-based 路径
    event_count: int = 0
    hook_count: int = 0

    def register_event(event_type, handler, *, priority=100, mode=None) -> str
    def register_hook(point, handler, *, priority=100, description="") -> str
    def emit(event: FrameworkEvent) -> None
```

**注意**：`event_count` / `hook_count` 是计数器，**不是** id 列表。卸载时通过 `event_bus.unsubscribe_plugin(name)` / `hook_registry.unregister_plugin(name)` 按 name 批量清理，**不需要 id**。原实现的 id 列表从未被消费过，已移除。

### Plugin

```python
class Plugin(ABC):
    manifest: PluginManifest                # 子类必须定义

    def __init__(self) -> None:
        self.state: PluginState = PluginState.DISCOVERED
        self.ctx: Optional[PluginContext] = None
        self.error: Optional[str] = None

    def load(self) -> None                  # 调 on_load()，失败置 FAILED
    def activate(ctx) -> None               # 调 on_activate()，失败置 FAILED + 发 PluginFailedEvent
    def deactivate() -> None                # 调 on_deactivate()，最后状态置 DEACTIVATED

    def on_load(self) -> None: pass                    # 子类可选
    def on_activate(self, ctx) -> None: ...           # 子类必须
    def on_deactivate(self) -> None: pass              # 子类可选
```

`PluginLoader` 负责：import entry_point → 实例化 → `load()` → 创建 `PluginContext` → `activate()` → 卸载时 `deactivate()` + 清理 event/hook 注册。

## 执行引擎

### Engine

```python
class Engine:
    def __init__(self, configuration: Configuration) -> None:
        self._ictx = configuration         # 只存引用，不做任何 I/O

    def run(self, target: Scenario | Suite) -> RunResult:
        """每次 run() 独立创建 FrameworkContext（run_id）"""
```

`run()` 内部：
1. 创建 `FrameworkContext`（每次独立 `run_id`）
2. 触发 `RUN_START` 事件
3. 按 `Scenario` / `Suite` 分发
4. 触发 `RUN_END` 事件

### RunResult

```python
@dataclass
class RunResult:
    exit_code: int = 0
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    details: list[dict] = field(default_factory=list)
```

## ScenarioRunner / StepRunner

### ScenarioRunner

```python
class ScenarioRunner:
    def __init__(
        self,
        dispatcher: StrategyDispatcher,
        ctx_manager: ContextManager,
        *,
        hook_registry: Any = None,
        event_bus: Any = None,
        auth_registry: Any = None,        # 注入运行期 token 容器
        asset_store: Any = None,          # Phase 0：注入 AssetStore（供 Preprocessor 物化 Ref）
    ): ...

    def run(self, scenario_schema, suite_ctx) -> ScenarioRunResult:
        # 1. 派生 ScenarioContext
        # 2. 预处理：ScenarioPreprocessor
        #    Phase 0  引用物化（asset_store 不为 None 时；AssetMaterializer 还原 Ref 节点）
        #    Phase 1  认证（写入 auth_registry）
        #    Phase 2  构建查询根
        #    Phase 3  模板展开（${} 替换为实际值）
        #    Phase 4  提取 base_url
        # 3. 触发 SCENARIO_START 事件
        # 4. 顺序执行每个已展开的 step（任一失败则中断）
        # 5. finalize ScenarioContext
        # 6. 触发 SCENARIO_END 事件
```

### StepRunner

```python
class StepRunner:
    def __init__(
        self,
        dispatcher: StrategyDispatcher,
        ctx_manager: ContextManager,
        service_base_url: str = "",
        *,
        hook_registry: Any = None,
        event_bus: Any = None,
    ): ...

    def run(self, step_schema, scenario_ctx, step_index) -> StepRunResult:
        # 1. 创建 StepContext
        # 2. 构造 StepStateMachine（注入 dispatcher / view / hook / bus）
        # 3. 状态机自驱动运行
        # 4. finalize StepContext
```

`step_schema` 在 `StepRunner` 之前已由 `ScenarioPreprocessor` 完成模板展开，这里不再做解析。

### ScenarioRunResult

```python
@dataclass
class ScenarioRunResult:
    scenario_id: str
    status: str                                  # "passed" / "failed" / "error"
    step_results: list[StepRunResult]
    started_at: Optional[datetime]
    ended_at:   Optional[datetime]

    @property
    def passed(self) -> bool: ...
    @property
    def duration_ms(self) -> float: ...
```

## 执行流程

```
CLI
  │
  ▼
bootstrap(cli_ctx) → Configuration
  │
  ▼
Engine(configuration)
  │
  ├── run(Scenario | Suite)
  │     │
  │     ├── create_framework_context(run_id)
  │     ├── 触发 RUN_START 事件
  │     │
  │     ├── Scenario → _run_scenario()
  │     │     │
  │     │     ├── derive_suite_context(...)        # suite_id="__default__"
  │     │     │
  │     │     └── ScenarioRunner.run()
  │     │           │
  │     │           ├── derive_scenario_context(...)
  │     │           ├── ScenarioPreprocessor.run()  # 认证 + 模板展开
  │     │           ├── 触发 SCENARIO_START
  │     │           │
  │     │           └── StepRunner.run() × n
  │     │                 │
  │     │                 ├── derive_step_context(...)
  │     │                 ├── StepStateMachine.run()
  │     │                 └── finalize_step(...)
  │     │
  │     └── Suite → _run_suite()
  │           │
  │           ├── derive_suite_context(...)        # 用 Suite 自身信息
  │           └── for scenario in suite.suite: ScenarioRunner.run()
  │                 （fail_fast 时未通过即 break）
  │     │
  │     └── 触发 RUN_END 事件
  │
  ▼
RunResult
  │
  ▼
shutdown(configuration)
  ├── 触发 FRAMEWORK_TEARDOWN
  ├── PluginLoader.deactivate_all(...)            # 统一卸载入口
  ├── hook_registry.clear() 兜底                  # 覆盖绕过 Plugin.register_hook 的注册
  └── event_bus.stop()
```

## 设计原则

1. **Configuration 不可变**：`frozen=True`，产出后只能读。**唯一可变**是 `auth_registry`（内部 `_sessions` 在运行期写入 token，但引用本身不变）。
2. **执行独立性**：每次 `run()` 创建独立的 `FrameworkContext` / `SuiteContext`，互不串扰。
3. **分层职责**：`bootstrap` 只初始化，`Engine` 只调度，`Runner` 只执行，状态机只管状态流转。
4. **name-based 清理**：插件卸载走 `unsubscribe_plugin(name)` / `unregister_plugin(name)`，**不维护 id 列表**。`PluginContext` 内只记计数器供日志。
5. **shutdown 兜底清空 hook**：有些代码路径绕过 `Plugin.register_hook` 直接调 `ctx.hook_registry.register()`，其 hook 未被任何 plugin 记录，deactivate_all 不会清掉。shutdown 阶段统一 `hook_registry.clear()`。
6. **fail_fast 支持**：Suite 执行时可选首次失败即终止。
7. **状态机隔离**：StepRunner 不感知状态流转，状态机自驱动运行，runner 只负责构造/收尾。
