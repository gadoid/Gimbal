# Core 模块

> 核心执行引擎模块，包含 bootstrap、Engine、ScenarioRunner

## 目录结构

```
gimbal/core/
├── __init__.py
├── boostrap.py        # bootstrap() 入口和 Configuration
├── runner.py          # Engine 执行引擎
├── scenario_runner.py # ScenarioRunner, StepRunner
├── asset_resolver.py  # 资产解析器
└── server.py          # 服务端（待实现）
```

## 核心组件

### bootstrap()

框架启动唯一入口：

```python
def bootstrap(cli_ctx: CLIContext) -> Configuration:
    """框架启动唯一入口"""
    # 1. 多来源配置合并 → BootstrapConfig
    # 2. 配置日志系统
    # 3. 初始化基础设施（EventBus / Archive / ContextManager / Dispatcher）
    # 4. 返回 Configuration（不可变）
```

### Configuration

bootstrap 的唯一产出：

```python
@dataclass(frozen=True)
class Configuration:
    """持有所有基础设施引用"""
    cfg: BootstrapConfig              # 合并后的完整配置快照
    ctx_manager: ContextManager        # 上下文管理器
    dispatcher: StrategyDispatcher     # 策略分发器
    event_bus: InMemoryEventBus        # 事件总线
    archive: InMemoryArchive           # 存档
```

### Engine

执行引擎：

```python
class Engine:
    """执行引擎"""

    def __init__(self, configuration: Configuration):
        self._ictx = configuration

    def run(self, target: Scenario | Suite) -> RunResult:
        """执行入口"""
        # 1. 创建 FrameworkContext（每次 run 独立的 run_id）
        # 2. 分发到 ScenarioRunner
        # 3. 返回 RunResult
```

### RunResult

执行结果：

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
  │     │
  │     ├── Scenario → _run_scenario()
  │     │     │
  │     │     ├── create_suite_context()
  │     │     │
  │     │     └── ScenarioRunner.run()
  │     │           │
  │     │           ├── ScenarioPreprocessor.run()  # 认证 + 模板展开
  │     │           │
  │     │           └── StepRunner.run() × n
  │     │                 │
  │     │                 └── StepStateMachine.run()
  │     │                       │
  │     │                       └── 状态机驱动执行
  │     │
  │     └── Suite → _run_suite()
  │           │
  │           └── for scenario in suite: ScenarioRunner.run()
  │
  ▼
RunResult
```

## ScenarioRunner

驱动整个 Scenario 的执行：

```python
class ScenarioRunner:
    """驱动整个 Scenario 的执行"""

    def run(self, scenario_schema: Scenario, suite_ctx: SuiteContext) -> ScenarioRunResult:
        # 1. 派生 ScenarioContext
        # 2. 预处理：认证 + 模板展开 + 提取 base_url
        # 3. 逐步执行每个 step
        # 4. 汇总结果，finalize ScenarioContext
```

## StepRunner

构造 StepStateMachine 并触发执行：

```python
class StepRunner:
    """构造 StepStateMachine 并触发执行"""

    def run(self, step_schema: Step, scenario_ctx: ScenarioContext, step_index: int) -> StepRunResult:
        # 1. 创建 StepContext
        # 2. 构造 StepStateMachine
        # 3. 状态机自驱动运行
        # 4. finalize StepContext
```

## ScenarioRunResult

Scenario 执行结果：

```python
@dataclass
class ScenarioRunResult:
    scenario_id: str
    status: str
    step_results: list[StepRunResult]
    started_at: datetime | None
    ended_at: datetime | None

    @property
    def passed(self) -> bool: ...

    @property
    def duration_ms(self) -> float: ...
```

## 设计原则

1. **Configuration 不可变**: bootstrap 产出的 Configuration 是 frozen 的
2. **执行独立性**: 每次 `run()` 创建独立的 Context 层级
3. **分层职责**: bootstrap 只负责初始化，Engine 负责调度，Runner 负责执行
4. **fail_fast 支持**: Suite 执行时可选首次失败即终止