# 架构概览

## 项目概述

Gimbal 是一个面向现代 API 测试场景的自动化测试框架（Python 3.11+），核心执行链路为：

**CLI → bootstrap(cli_ctx) → Engine.run → ScenarioRunner → StepRunner → StepStateMachine → StrategyDispatcher**。

整体采用分层、不可变配置 + 可插拔扩展点（Event / Hook / Plugin / Reporter）的设计，并提供一个仿 Docker Registry v2 的本地资产仓库用于跨项目复用 Suite / Scenario 资产。

## 顶层模块布局

```
src/gimbal/
├── ai/                 # AI 辅助（assistant_base / providers / prompts）
├── auth/               # 认证管理（AuthManager / AuthRegistry / 内置 authenticators）
├── cli/                # 命令行入口（Typer 应用、commands/、CLIContext）
├── compiler/           # 场景文件编译（parsers / assemblers / validators）
├── config/             # 多来源配置合并（loader / models / env / mode / gimbal.yaml）
├── context/            # 层级执行上下文（Framework → Suite → Scenario → Step / channels / views）
├── core/               # 框架核心：bootstrap、Engine、ScenarioRunner、StepRunner、hooks、plugin、server
├── events/             # 事件系统（bus / subscription / protocols / types）
├── exceptions.py       # 全局异常类（AssetNotFound、StrategyError 等）
├── log/                # 日志系统（logger / formatters / setup / intercept / integration）
├── observability/      # 可观测性后端（日志/指标/快照/追踪）
├── plugins/            # 插件机制（PluginLoader / spec / manifest / registry / categories）
├── preprocessor/       # Scenario 预处理器（引用物化、认证、模板展开、base_url 提取）
├── reporter/           # 报告系统（base / runtime / registry / builtin）
├── repository/         # 资产仓库（仿 Docker Registry v2：ContentStore / AssetStore / models）
├── resource/           # 资源管理（provider_base / handle / manager / providers）
├── scheduler/          # 调度原语（concurrency / dependency / retry / scheduler）
├── schema/             # Pydantic 数据模型（Scenario / Suite / Step / Strategy / Auth / Ref）
├── statemachine/       # 状态机引擎（engine / states）
├── strategy/           # 策略系统（executor_base / dispatcher / 内置 builtin）
├── suite/              # Suite 编排（environment / manager / plan / selector）
├── utils/              # 工具函数（jsonpath 等）
└── version.py          # 版本号
```

## 核心架构

### 1. 启动与执行链路

```
CLI (Typer)
    │
    ├── @starter.callback()         # 安装 SIGINT handler、构造 CLIContext
    │
    └── 子命令（run / asset / self-check）
            │
            ├── run suite / scenario / match / server / launch
            │       │
            │       ├── bootstrap(cli_ctx)         # 配置合并 + 基础设施初始化
            │       │     ├── configure_logging_from_cli(cfg)
            │       │     ├── ConfigLoader().load()  →  BootstrapConfig
            │       │     ├── EventBus / Archive / ContextManager / Dispatcher
            │       │     ├── HookRegistry / PluginRegistry / AuthRegistry
            │       │     ├── _load_plugins()  → PluginLoader.discover/resolve/load/activate
            │       │     ├── hook_registry.trigger(FRAMEWORK_INIT, payload)
            │       │     └── ReporterRuntime.setup(bus, config)
            │       │     → Configuration（frozen dataclass）
            │       │
            │       ├── _publish_run_meta(configuration)        # 发布 RunMetaEvent（此时 reporter_runtime 已 setup 但未 begin_all，无内置 reporter 订阅）
            │       │
            │       ├── engine = Engine(configuration, asset_store=...)
            │       │     └── engine.run(scenario | suite)   # 内部：FrameworkContext → RUN_START → reporter_runtime.begin_all → 分发 → RUN_END → reporter_runtime.finalize_all
            │       └── _print_run_report(result, fmt, artifacts)  # 终端/JSON 输出
            │
            ├── asset push / pull / list / inspect / remove / tag / gc   # 走"快路径"，不 bootstrap
            └── self-check            # bootstrap + exercise event_bus / hook_registry
```

要点：

- `bootstrap(cli_ctx)` 是框架启动的**唯一入口**，产出 frozen `Configuration`；不创建任何层级 Context。
- `Engine.run(target)` 才是执行入口；每次调用都会创建独立的 `FrameworkContext`（含 `run_id`），保证多次执行互不影响。
- `asset` 子命令组走"快路径"，不经过 bootstrap，直接构造 `LocalFsContentStore` + `AssetStore`，因为仓库管理不依赖 Context/Plugin/Hook。
- `self-check` 是**集成测试级**的子命令，会真实 bootstrap + 手动驱动 EventBus / HookRegistry，验证基础设施回路。

### 2. 核心模块职责

| 模块 | 主要文件 | 职责 |
|------|----------|------|
| **CLI** | `cli/main.py` / `cli/commands/` | Typer 命令树（`run` / `asset` / `self-check`），共享参数与参数解析 |
| **bootstrap** | `core/bootstrap.py` | 配置合并、基础设施初始化、插件加载、Reporter 装配、FRAMEWORK_INIT 触发 |
| **Engine** | `core/runner.py` | 接收 Scenario/Suite，派生 FrameworkContext，分发到 ScenarioRunner，驱动 Reporter 生命周期 |
| **ScenarioRunner** | `core/scenario_runner.py` | 单个 Scenario 驱动：调用 Preprocessor → 遍历 StepRunner → 汇总结果 |
| **StepRunner** | `core/scenario_runner.py` | 单个 Step 执行：构造 `StepStateMachine`，调用 `sm.run()` |
| **StepStateMachine** | `statemachine/engine.py` | 状态流转控制，PENDING → BEFORE_REQUEST → CALLING → AFTER_REQUEST → VERIFYING → TEARDOWN |
| **StrategyDispatcher** | `strategy/dispatcher.py` | 策略分发执行（kind → StrategyExecutor），含 STRATEGY_BEFORE/AFTER 埋点、软失败标记 |
| **ContextManager** | `context/manager.py` | 层级 Context 生命周期管理（Framework/Suite/Scenario/Step） |
| **Preprocessor** | `preprocessor/scenario_preprocessor.py` | 引用物化、认证、变量生成、构建查询根、模板展开、提取 base_url |
| **EventBus** | `events/bus.py` | 进程内事件总线（filter / priority / SYNC/ASYNC/BATCH / 插件热卸载） |
| **HookRegistry** | `core/hooks.py` | Hook 注册表（按 priority 升序、STOP 中断、payload 改写） |
| **PluginLoader** | `plugins/loader.py` | 插件发现 / 依赖解析 / 加载 / 激活 / 卸载四阶段流水线 |
| **ReporterRuntime** | `reporter/runtime.py` | Reporter 调度（begin_all / finalize_all），产出 `ReportArtifact` 列表 |
| **AssetStore** | `repository/store.py` | 资产仓库门面：push/pull/list/inspect/remove/tag，digest 校验，tag 解析 |

### 3. Schema 数据模型

```
Scenario (场景)
├── meta (元信息)
├── config (配置)
│   ├── setup/teardown (前置/后置动作)
│   ├── services (服务 URL 映射)
│   ├── users (认证信息)
│   └── retry (重试策略)
├── resource (资源)
└── steps: list[StepUnion]  # Step | StepRef
    └── Step
        ├── api: ApiUnion                  # Api | ApiRef
        ├── request: RequestUnion          # Request | RequestRef
        └── strategy: list[StrategyUnion]  # Extract | Assign | Assertion | Call | StrategyRef | ...

Suite (套件)
├── suite: list[ScenarioUnion]   # Scenario | ScenarioRef
└── …

RunUnion  (外层, CLI 入口接受这几种)
├── Scenario | ScenarioRef
└── Suite    | SuiteRef
```

### 4. Context 层次结构

```
FrameworkContext (根节点, run_id 唯一, 持 BootstrapConfig + 基础设施引用)
└── SuiteContext (Suite 级别; 单 scenario 执行时 suite_id="__default__")
    └── ScenarioContext (Scenario 级别)
        └── StepContext (Step 级别)
```

Context 之间的数据流动受控：`promote_from()` 单向提升，`seal` 机制在执行完毕后封印。

### 5. Step 执行状态流转

> 下表与 `statemachine/states.py:VALID_TRANSITIONS` + `engine.py` 各 handler 的实际返回完全一致。
> 简化版会丢失"前/中阶段 hard-fail → FAILED"的合法路径，故此处列出全部 4 个目标态（FAILED / TEARDOWN / ERROR / 下一阶段）。

```
PENDING
  └─→ BEFORE_REQUEST                     # 初始推进（start）
BEFORE_REQUEST                           # 执行 Assign 等前置策略
  ├─→ CALLING                            # 策略全部通过
  ├─→ FAILED                             # hard-fail 且无 teardown（VALID_TRANSITIONS 允许但 handler 默认走 TEARDOWN）
  ├─→ TEARDOWN                           # hard-fail + 有 teardown（handler 实际行为）
  └─→ ERROR                              # 框架异常（_try_advance 兜底）
CALLING                                  # 发出 HTTP 请求
  ├─→ AFTER_REQUEST                      # 请求成功
  ├─→ FAILED                             # VALID_TRANSITIONS 允许；handler 实际走 TEARDOWN
  ├─→ TEARDOWN                           # HTTP 失败（handler 实际行为）
  └─→ ERROR
AFTER_REQUEST                            # 执行 Extract 等后置策略
  ├─→ VERIFYING                          # 策略全部通过
  ├─→ FAILED                             # VALID_TRANSITIONS 允许
  ├─→ TEARDOWN                           # hard-fail（handler 实际行为）
  └─→ ERROR
VERIFYING                                # 执行 Assertion
  ├─→ PASSED                             # 无 teardown + 全部通过
  ├─→ FAILED                             # 无 teardown + 硬失败
  ├─→ TEARDOWN                           # 有 teardown 策略（无论断言结果）
  └─→ ERROR
TEARDOWN                                 # 执行清理策略
  ├─→ PASSED                             # 业务通过 + teardown 通过 / 业务通过 + teardown 软失败（B6：teardown 失败不污染业务结果）
  ├─→ FAILED                             # 业务阶段已有 hard-fail
  └─→ ERROR
```

**终态**：`PASSED` / `FAILED` / `ERROR` / `SKIPPED`（均不允许再跃迁）。

### 6. 策略分发

| Phase          | 默认 Executor   | 说明 |
|----------------|-----------------|------|
| BEFORE_REQUEST | `AssignExecutor`| 变量赋值 / 注入 |
| CALLING        | `CallExecutor`  | HTTP 调用 |
| AFTER_REQUEST  | `ExtractExecutor`| 字段提取 |
| VERIFYING      | `AssertionExecutor` | 断言验证 |
| TEARDOWN       | 各种 Executor   | 清理 / 恢复 |

- 框架通过 `build_default_dispatcher(hook_registry=...)` 一次性注册所有内置 executor。
- `StrategyDispatcher.dispatch()` 统一负责：disabled 跳过、STRATEGY_BEFORE 埋点、计时、STRATEGY_AFTER 埋点、软失败标记、兜底异常捕获。
- `onFailure != ABORT` 时策略失败标记为 `soft=True`，`PhaseResult.hard_failed` 据此区分硬/软失败。

### 7. Discriminated Union

使用 Pydantic `Annotated[Union[...], Field(discriminator="kind")]` 实现类型安全联合体：

- `StepUnion` = `Step` | `StepRef`（内层，Phase 0 由 `AssetMaterializer` 递归还原）
- `ApiUnion` = `Api` | `ApiRef`（同 Phase 0 还原）
- `RequestUnion` = `Request` | `RequestRef`（同 Phase 0 还原）
- `StrategyUnion` = `Extract` | `Assign` | `Assertion` | `Call` | `StrategyRef`（同 Phase 0 还原）
- `RunUnion` = `Scenario` | `ScenarioRef` | `Suite` | `SuiteRef`（**外层**，CLI 入口直接接受这四种，由 `AssetResolver` / 仓库操作解析）

所有 `*Ref` 节点都通过 `kind` 字段（`"step_ref"` / `"api_ref"` / `"request_ref"` / `"strategy_ref"` / `"scenario_ref"` / `"suite_ref"`）被 Pydantic 自动分发到对应子类。

### 8. Event 与 Hook 的区别

| 维度 | Event | Hook |
|------|-------|------|
| 方向 | 通知型（fire-and-forget） | 介入型（interposable） |
| 订阅者能否中断 | 否 | 是（`raise HookSignal.STOP`） |
| 订阅者能否改写 payload | 否（不可变 dataclass） | 是（dict / dataclass 字段 in-place 修改，或 `return` 新对象替换） |
| 执行顺序 | priority 升序 | priority 升序 |
| 模式 | SYNC / ASYNC / BATCH | 全部同步触发 |

- `EventType` / `HookPoint` 分别在 `events/types.py` 与 `core/hooks.py` 定义枚举；新增埋点只需要在枚举里加一行。
- 插件通过 `PluginContext.register_event()` / `register_hook()` 注册时，会携带 `plugin_name`，卸载时由框架按名字精确清理。
- **双侧同名埋点**：部分关键事件在 `EventType` 与 `HookPoint` **值完全相同**——例如 `framework.init` / `framework.teardown` / `run.start` / `run.end` / `scenario.start` / `scenario.end` / `step.start` / `step.end` / `step.failed` 既是 Event 也是 Hook。这种设计让"先观察后介入"或"先拦截后通知"两种用法可自由组合。Event 在主流程中由框架 `bus.publish()` 主动发出，Hook 由主流程在执行前/后显式 `trigger()` 调用；两者互不替代。

## 设计原则

### 1. 职责分离

- **bootstrap**：负责配置 + 基础设施 + 插件加载，**不**创建层级 Context。
- **Engine**：负责 FrameworkContext 生命周期与 Reporter 调度，**不**感知 Step 细节。
- **ScenarioRunner**：驱动单个 Scenario，**不**感知状态细节。
- **StepRunner**：构造状态机，调用 `sm.run()`。
- **StepStateMachine**：持有执行依赖，内部循环驱动状态流转，**不**感知具体策略逻辑。
- **StrategyDispatcher**：策略执行委托目标，**不**感知状态机。

### 2. 上下文隔离

每次 `Engine.run()` 创建独立的 Context 层级（Framework → Suite → Scenario → Step），互不共享；`run_id` 由 `uuid.uuid4()` 生成，保证并发 / 重复执行的安全性。

### 3. 策略不可知

状态机只负责流转控制，不感知具体策略逻辑。策略执行委托给 `StrategyDispatcher`，新增策略类型只需实现 `StrategyExecutor` 并 `dispatcher.register()`。

### 4. 不可变配置

`BootstrapConfig` 与 `Configuration` 都是 frozen dataclass，产出后不可修改（`auth_registry` 等引用对象内部可变更，但引用本身不变），保证 Engine / Runner 只读不写。

### 5. 失败容错分层

- EventBus：handler 异常被吞掉记日志，不影响主流程。
- HookRegistry：handler 异常被吞掉记日志，STOP 异常可中断主流程。
- PluginLoader：单插件 import / activate 失败被隔离，不影响其它插件。
- 整体原则：单点失败不拖垮整体；只有"结构性失败"（如循环依赖）才视为致命。

## 关键数据结构

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
    details: list[dict[str, Any]] = field(default_factory=list)
```

### Configuration

```python
@dataclass(frozen=True)
class Configuration:
    cfg: BootstrapConfig                # 合并后的配置快照
    auth_registry: AuthRegistry        # 可变的 AuthSession 容器
    ctx_manager: ContextManager         # 上下文管理器
    dispatcher: StrategyDispatcher      # 策略分发器
    event_bus: InMemoryEventBus         # 事件总线
    archive: Archive                    # 归档存储
    hook_registry: HookRegistry         # Hook 注册表
    plugin_registry: PluginRegistry     # 插件注册表
    plugins: tuple[Plugin, ...]         # 已激活的插件实例
    reporter_runtime: ReporterRuntime   # Reporter 调度器
```

### CLIContext

```python
class CLIContext(BaseModel):
    config_file: Path | None = None
    mode: str = "local"
    env: str = "dev"
    report_dir: str = "./report/"
    log_level: str = "info"
    no_color: bool = False
    extras: dict[str, Any] = Field(default_factory=dict)
```

### AssetRef / AssetRecord / AssetContent

仿 Docker Registry v2 的不可变数据模型（详见 `repository/models.py`）：

- `AssetRef`：`namespace/name:tag` 或 `namespace/name@digest`
- `AssetRecord`：digest + size + kind + media_type + metadata
- `AssetContent`：record + raw bytes + (可选) 解析后的对象

## 执行流程（端到端）

```
1. CLI 解析命令，构造 Scenario/Suite 对象
2. bootstrap(cli_ctx) 初始化基础设施
     - 日志系统 → ConfigLoader → BootstrapConfig
     - EventBus / Archive / ContextManager / Dispatcher / HookRegistry / PluginRegistry / AuthRegistry
     - PluginLoader 流水线（discover → resolve_deps → load_all → activate_all）
     - hook_registry.trigger(FRAMEWORK_INIT, payload)
     - ReporterRuntime.setup
3. _publish_run_meta(configuration)   # 发布 RunMetaEvent（CI/Git 上下文）
4. Engine.run(target)
     ├── 创建 FrameworkContext（run_id 唯一）
     ├── reporter_runtime.begin_all(framework_ctx, …)
     ├── emit RunStartEvent
     ├── Scenario: 派生 __default__ SuiteContext → ScenarioRunner.run()
     └── Suite:    派生 SuiteContext        → 遍历 ScenarioRunner.run()（按 fail_fast 控制）
5. ScenarioRunner.run()
     ├── 创建 ScenarioContext
     ├── ScenarioPreprocessor.run()
     │     ├── Phase 0  引用物化（AssetMaterializer 递归还原内层 Ref）
     │     │   ├── StepRef     → Step
     │     │   ├── ApiRef      → Api
     │     │   ├── RequestRef  → Request
     │     │   └── StrategyRef → Extract/Assign/Assertion/Call
     │     ├── Phase 1  认证（AuthManager → AuthRegistry）
     │     ├── Phase 1.5  变量生成（合并 scenario.config.vars + BootstrapConfig.vars；CLI 赢；生成式调 Generator）  ★
     │     ├── Phase 2  构建查询根（services + auth.snapshot + vars）
     │     ├── Phase 3  模板展开（${auth.*} ${service.*} ${var.*}）
     │     └── Phase 4  提取 base_url
     ├── 遍历已展开的 steps（此时已无 Ref 节点）
     │   └── Step: 调用 StepRunner.run()
     └── 汇总结果，finalize
6. StepRunner.run()
     ├── 创建 StepContext
     ├── 构造 StepStateMachine
     ├── 调用 sm.run()
     └── finalize StepContext
7. StepStateMachine.run()
     ├── PENDING → BEFORE_REQUEST → CALLING → AFTER_REQUEST → VERIFYING → TEARDOWN
     ├── 循环直到终态
     └── 返回 StepRunResult
8. emit RunEndEvent
9. reporter_runtime.finalize_all(result) → list[ReportArtifact]
10. _print_run_report(result, fmt, artifacts)   # 终端 / JSON 输出
```
