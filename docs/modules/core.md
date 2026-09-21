# Core 模块

> 核心执行引擎模块：bootstrap / shutdown 入口、Hook 系统、Engine / Runner

## 目录结构

```
gimbal/core/
├── __init__.py
├── bootstrap.py           # bootstrap() / shutdown() 入口、Configuration 容器
├── runner.py              # Engine 执行引擎
├── scenario_runner.py     # ScenarioRunner、StepRunner、ScenarioRunResult
├── hooks.py               # HookPoint / Hook / HookResult / HookRegistry / HookTriggerer
├── plugin.py              # Plugin / PluginContext / PluginManifest / PluginState
└── server.py              # 服务端占位实现
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
        4. 发现 / 加载 / 激活插件（按 enabled 过滤，缺省 = 全部）
        5. 触发 FRAMEWORK_INIT hook（插件可在此注册全局监听、初始化连接池等）
        6. 装配 Reporter runtime（注册内置 reporter、订阅事件总线）
        7. 返回 Configuration
    """
```

**不**创建任何层级 Context（由 `Engine.run()` 负责）。

### shutdown()

`bootstrap()` 的对偶函数，框架关闭唯一入口：

```python
def shutdown(configuration: Configuration) -> None:
    """步骤：
        1. 幂等检查：标记 _gimbal_shutdown_done，重复调用直接返回
        2. 触发 FRAMEWORK_TEARDOWN 钩子（可让插件补充清理）
        3. 走 PluginLoader.deactivate_all() 统一卸载所有插件
        4. 兜底清空 hook_registry（覆盖绕过 Plugin.register_hook 的注册）
        5. 停 EventBus
    """
```

- **幂等性**：通过 `configuration._gimbal_shutdown_done` 标记防止重复触发。
- `deactivate_all()` 返回 `DeactivateReport`，调用方按需处理失败/成功统计。
- **hook_registry 兜底清空**：绕过 `Plugin.register_hook` 直接调 `ctx.hook_registry.register()` 注册的 hook 没被 plugin 记录，deactivate_all 不会清掉，shutdown 阶段统一 `clear()` 防止下次 bootstrap 残留。

### Configuration

`bootstrap()` 的唯一产出，`shutdown()` 的唯一输入：

```python
@dataclass(frozen=True)
class Configuration:
    """持有所有基础设施引用与已激活插件。"""
    cfg: BootstrapConfig                          # 合并后的完整配置快照（frozen）
    auth_registry: Any                            # gimbal.auth.registry.AuthRegistry
    ctx_manager: "ContextManager"
    dispatcher: Any                               # StrategyDispatcher
    event_bus: Any                                # InMemoryEventBus
    archive: Any                                  # InMemoryArchive
    hook_registry: "HookRegistry"
    plugin_registry: Any                          # PluginRegistry
    plugins: tuple["Plugin", ...] = field(default_factory=tuple)
    reporter_runtime: Any = None                  # Reporter 调度器，Engine.run() 阶段驱动
```

`frozen=True`：产出后不可修改，Engine 只读取。**唯一例外是 `auth_registry`**——它本身是不可变引用，但其内部 `_sessions` 字典在运行期会变（登录/刷新会写入 token）。

`auth_registry` / `event_bus` / `archive` / `dispatcher` / `plugin_registry` / `reporter_runtime` 字段用 `Any` 而非强类型以避免循环导入；运行时由对应模块解释。

## Hook 系统（`core/hooks.py`）

框架级 Hook 是**介入型**（interposable）的扩展点，与 Event 的**通知型**（fire-and-forget）形成对照：

| 维度 | Event | Hook |
|------|-------|------|
| 行为 | 通知（fire-and-forget） | 介入（interposable） |
| 中断主流程 | 不能 | 能（`HookSignal.STOP`） |
| 修改 payload | 不能 | 能（in-place 或 return 新对象） |

### HookPoint

```python
class HookPoint(str, Enum):
    """框架所有可埋点的位置。"""
    # 框架生命周期
    FRAMEWORK_INIT     = "framework.init"
    FRAMEWORK_TEARDOWN = "framework.teardown"
    # Run 生命周期
    RUN_START = "run.start"
    RUN_END   = "run.end"
    # Suite 生命周期
    SUITE_START = "suite.start"
    SUITE_END   = "suite.end"
    # Scenario 生命周期
    SCENARIO_START = "scenario.start"
    SCENARIO_END   = "scenario.end"
    # Step 生命周期
    STEP_START  = "step.start"
    STEP_END    = "step.end"
    STEP_FAILED = "step.failed"
    # HTTP 调用前后
    HTTP_BEFORE_SEND = "http.before_send"   # payload: {method, url, headers, body, ctx}
    HTTP_AFTER_RECV  = "http.after_recv"    # payload: {method, url, status, headers, body, duration_ms, ctx}
    # Strategy 调用前后
    STRATEGY_BEFORE = "strategy.before"     # payload: {strategy_name, phase, ctx}
    STRATEGY_AFTER  = "strategy.after"      # payload: {strategy_name, phase, result, ctx}
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
    """fire() 的返回值"""
    stopped: bool = False
    stop_reason: str = ""
    stop_plugin: Optional[str] = None
    modified: bool = False              # handler 是否返回新对象（仅 return 才计 modified）
    errors: list[dict] = field(default_factory=list)   # handler 异常列表（仅记录，不抛出）

    def __bool__(self) -> bool:
        """支持 `if not result`：未中断时为 True（继续主流程）。"""
        return not self.stopped
```

### HookSignal.STOP

`HookSignal` 类作为命名空间承载 `STOP` 异常类。Handler 抛 `HookSignal.STOP(reason)` 即可中断主流程：

```python
def my_handler(payload):
    if some_condition:
        raise HookSignal.STOP("rate limited")   # 中断主流程
    mutate(payload)
```

### HookRegistry

```python
class HookRegistry:
    def register(
        point,                              # HookPoint 枚举或字符串
        handler,                            # Callable[[Any], Any]
        *,
        priority: int = 100,
        plugin_name: Optional[str] = None,
        description: str = "",
    ) -> str                                 # 返回 hook_id

    def unregister(hook_id: str) -> bool
    def unregister_plugin(plugin_name: str) -> int   # 按 name 批量注销
    def list_hooks(point=None, plugin_name=None) -> list[Hook]
    def trigger(point, payload) -> HookResult        # 按 priority 升序执行
    def clear() -> None                              # 兜底用：清空所有 hook
```

`point` 参数接受 `HookPoint` 枚举或字符串，字符串会内部归一化（与 `PluginContext.register_hook` 一致）。

执行规则：
- 同一 `point` 下多 handler 按 `priority` 升序
- 任何 handler 抛 `HookSignal.STOP` → 立即终止后续 handler 与主流程
- handler 异常被吞掉记入 `result.errors`，不影响其它 hook
- handler 返回非 `None` 值 → 替换 `payload` 并标记 `modified=True`
- 修复 #15：仅当 handler 实际返回新对象（替换 payload）时才标记 `modified`（in-place 修改需 handler 显式 return payload 才被识别）

### HookTriggerer

```python
class HookTriggerer:
    """轻量级 fire 包装，绑定到指定 registry"""

    def __init__(self, registry: HookRegistry) -> None: ...
    def fire(self, point: HookPoint, payload: Any) -> HookResult
```

常用模式：

```python
triggerer = HookTriggerer(registry)
result = triggerer.fire(HookPoint.HTTP_BEFORE_SEND, payload)
if not result:        # __bool__ → not self.stopped
    return            # 被某个 hook 拦截
# payload 已被 hook 改写，直接用
send(payload["request"])
```

## 异常类型

状态机相关异常统一在 `gimbal.exceptions` 中定义：

```python
# 状态机相关（继承自 StateMachineError）
class InvalidTransitionError(StateMachineError):
    """非法状态跃迁。"""
    code = "STATEMACHINE_INVALID_TRANSITION"

    def __init__(self, from_state: str, to_state: str) -> None:
        super().__init__(
            f"Invalid transition: {from_state!r} → {to_state!r}",
            from_state=from_state, to_state=to_state,
        )

class AlreadyTerminalError(StateMachineError):
    """对已处于终态的状态机发起跃迁。"""
    code = "STATEMACHINE_ALREADY_TERMINAL"

    def __init__(self, state: str) -> None:
        super().__init__(
            f"State machine is already in terminal state: {state!r}",
            state=state,
        )
```

所有框架异常都继承自 `GimbalError`，可通过统一基类捕获并使用 `to_dict()` 序列化。

## Plugin 系统（`core/plugin.py`）

`Plugin` 是所有插件的抽象基类。**它本身不知道 EventBus / HookRegistry 的存在**，这些由 `PluginContext` 在 `activate()` 时注入。

### PluginState

```python
class PluginState(str, Enum):
    DISCOVERED   = "discovered"      # 找到 manifest
    LOADED       = "loaded"          # 类已 import，实例已创建
    ACTIVATING   = "activating"      # 正在注册回调
    ACTIVATED    = "activated"
    DEACTIVATING = "deactivating"
    DEACTIVATED  = "deactivated"
    FAILED       = "failed"          # 任意阶段失败
```

### PluginManifest

```python
@dataclass
class PluginManifest:
    """从 plugin.yaml / plugin.toml 解析出的清单。"""
    name: str                                # 必需
    version: str                             # 必需
    entry_point: str                         # 必需，例 "my_plugin.plugin:MyPlugin"
    description: str = ""
    author: str = ""
    homepage: str = ""
    dependencies: list[str] = field(default_factory=list)        # 其它插件名
    gimbal_version: str = ""                 # 兼容的 gimbal 版本（语义化）
    capabilities: list[str] = field(default_factory=list)        # 声明的能力
    config_schema: dict = field(default_factory=dict)           # 用户配置 schema
    default_config: dict = field(default_factory=dict)           # 用户配置默认值
```

### PluginContext

`activate()` 时由框架注入的运行时句柄集合。**通过 Protocol 持有基础设施引用**，因此可以替换为分布式实现而不影响插件代码。

```python
@dataclass
class PluginContext:
    plugin_name: str
    config: dict                             # 用户配置（与 default_config 合并后）
    event_bus: EventBusProtocol
    hook_registry: HookRegistryProtocol
    plugin_registry: Any = None              # 通用插件注册表
    event_count: int = 0                     # 计数器（仅供 activate 日志）
    hook_count: int = 0                      # 计数器（仅供 activate 日志）

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
    def on_activate(self, ctx) -> None: ...           # 子类必须（abstractmethod）
    def on_deactivate(self) -> None: pass              # 子类可选
```

`PluginLoader` 负责：import entry_point → 实例化 → `load()` → 创建 `PluginContext` → `activate()` → 卸载时 `deactivate()` + 清理 event/hook 注册。

## 执行引擎

### Engine

```python
class Engine:
    """执行引擎。__init__ 只存引用，不做任何 I/O 或状态初始化。
    所有执行相关的状态都在 run() 内部创建，保证每次 run() 相互独立。
    """

    def __init__(self, configuration: Configuration) -> None:
        self._ictx = configuration
        # 最近一次 run() 产出的 ReportArtifact 列表
        self._artifacts: list = []

    @property
    def artifacts(self) -> list:
        """最近一次 run() 产出的 ReportArtifact 列表。
        仅在 Engine.run() 完成后非空。
        """
        return list(self._artifacts)

    def run(self, target: Scenario | Suite) -> RunResult:
        """执行入口。
        在此方法内创建本次执行的层级 context：
            1. FrameworkContext —— 全量配置写入，run_id 在此生成
            2. SuiteContext     —— 单 scenario 执行时用 __default__ 占位
        然后分发到 ScenarioRunner。
        """
```

`artifacts` 属性在 `run()` 完成后非空，包含所有 reporter 产出的 `ReportArtifact`（metadata 写入，artifact 本身由 reporter 落盘）。CLI 用来打印。

CLI 使用示例：

```python
from gimbal.core.bootstrap import bootstrap
from gimbal.core.runner import Engine

configuration = bootstrap(cli_ctx)
engine = Engine(configuration)
result = engine.run(scenario)
print(engine.artifacts)        # 列出所有 ReportArtifact
```

`run()` 内部：
1. 创建 `FrameworkContext`（每次独立 `run_id`）
2. 触发 `RUN_START` 事件
3. 启动所有 reporter（`reporter_runtime.begin_all`）
4. 按 `Scenario` / `Suite` 分发到 `_run_scenario` / `_run_suite`
5. 触发 `RUN_END` 事件
6. 终结所有 reporter，产出 `ReportArtifact` 列表（`reporter_runtime.finalize_all`）

### RunResult

```python
@dataclass
class RunResult:
    exit_code: int = 0            # 0 = 全部通过；1 = 有失败；2 = 异常；3 = 无法识别的执行目标类型
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)
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
    ): ...

    def run(self, scenario_schema, suite_ctx) -> ScenarioRunResult:
        # 1. 派生 ScenarioContext
        # 2. 预处理：ScenarioPreprocessor
        #    Phase 1  认证（写入 auth_registry）
        #    Phase 2  构建查询根
        #    Phase 3  模板展开（${} 替换为实际值，fail-fast）
        #    Phase 4  提取 base_url
        # 3. 触发 SCENARIO_START 事件（step_count = 实际可执行 step 数）
        # 4. 顺序执行每个已展开的 step（任一失败则中断）
        #    - 修复 B3：scenario_timeout 强制执行（cooperative timeout，每 step 前检查 elapsed time）
        #    - 修复 B8：cancel flag 检查（SIGINT 用户中断）
        #    - 失败/超时/取消时插入 __scenario_<kind>__ 标记 step
        # 5. finalize ScenarioContext
        # 6. 触发 SCENARIO_END 事件（携带 scenario.meta 拍平 dict）
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
        # 2. 构造 StepStateMachine（注入 dispatcher / view / hook / bus / service_base_url）
        # 3. 状态机自驱动运行 sm.run()
        # 4. finalize StepContext
```

`step_schema` 在 `StepRunner` 之前已由 `ScenarioPreprocessor` 完成模板展开，这里不再做解析工作。

### ScenarioRunResult

```python
@dataclass
class ScenarioRunResult:
    scenario_id: str
    status: str                                  # "passed" / "failed" / "error"
    step_results: list[StepRunResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    ended_at:   Optional[datetime] = None

    @property
    def passed(self) -> bool:
        """便捷属性：status == 'passed' 时为 True。"""
        return self.status == "passed"

    @property
    def duration_ms(self) -> float:
        """便捷属性：以毫秒为单位计算 Scenario 的总耗时。"""
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds() * 1000
        return 0.0
```

## 执行流程

```
CLI (run launch / run match)
  │
  ▼
bootstrap(cli_ctx) → Configuration
  │
  ▼
Engine(configuration)                                    ← core/runner.py
  │
  ├── run(Scenario | Suite)
  │     │
  │     ├── create_framework_context(run_id)
  │     ├── 触发 RUN_START 事件
  │     ├── reporter_runtime.begin_all(...)
  │     │
  │     ├── Scenario → _run_scenario()
  │     │     │
  │     │     ├── derive_suite_context(...)        # suite_id="__default__"
  │     │     │
  │     │     └── ScenarioRunner.run(...)
  │     │           │
  │     │           ├── derive_scenario_context(...)
  │     │           ├── ScenarioPreprocessor.run(scenario, ctx)
  │     │           │     ├─ Phase 1  认证 (AuthManager → AuthRegistry)
  │     │           │     ├─ Phase 2  构建查询根 (scenario > bootstrap)
  │     │           │     ├─ Phase 3  模板展开 (${auth.*} ${service.*} ${var.*})
  │     │           │     └─ Phase 4  提取 base_url
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
  │           └── for scenario in suite.suite: ScenarioRunner.run(...)
  │                 （fail_fast 时未通过即 break）
  │     │
  │     ├── 触发 RUN_END 事件
  │     └── reporter_runtime.finalize_all(result)  → 写入 engine.artifacts
  │
  ▼
RunResult
  │
  ▼
shutdown(configuration)
  ├── 幂等检查（_gimbal_shutdown_done）
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
