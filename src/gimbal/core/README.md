# Core 模块

执行引擎核心模块，负责将 Schema 定义的测试用例转化为可执行的流程。

## 设计理念

### 1. 执行链路

```
CLI
    │
    └── bootstrap()                    # 初始化基础设施（独立函数）
    │       ├── Configuration (frozen)
    │       ├── EventBus
    │       ├── Archive
    │       ├── ContextManager
    │       └── StrategyDispatcher
    │
    └── Engine(Configuration)
            │
            └── run(Scenario | Suite)
                    │
                    ├── Scenario → ScenarioRunner
                    │       │
                    │       └── StepRunner × n
                    │               │
                    │               └── StepStateMachine (自驱动)
                    │                       ├── _handle_before_request
                    │                       ├── _handle_calling
                    │                       ├── _handle_after_request
                    │                       ├── _handle_verifying
                    │                       └── _handle_teardown
                    │
                    └── Suite → 遍历 Scenario × n
```

### 2. 关注点分离

| 类 | 职责 |
|----|------|
| `bootstrap()` | 配置合并 + 基础设施初始化，返回 Configuration |
| `Engine` | 入口编排，根据 target 类型分发执行 |
| `ScenarioRunner` | 单个 Scenario 的执行流程编排 |
| `StepRunner` | 构造 StepStateMachine 并触发执行 |
| `StepStateMachine` | 驱动单个 Step 的完整生命周期（自驱动） |
| `AssetResolver` | 资产解析（占位） |

### 3. 职责分离原则

- `Engine` 只负责创建层级 Context 和分发执行，不感知具体执行逻辑
- `StepRunner` 只负责创建状态机和上下文，不驱动状态流转
- `StepStateMachine` 内部持有全部执行依赖，自己驱动整个流程直到终态

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `boostrap.py` | `bootstrap()` 函数、`Configuration` dataclass |
| `runner.py` | `Engine`、`RunResult` |
| `scenario_runner.py` | `ScenarioRunner`、`StepRunner`、`ScenarioRunResult` |
| `asset_resolver.py` | `AssetResolver`、`ResolvedAsset` |

---

## bootstrap()

框架启动唯一入口。

```python
def bootstrap(cli_ctx: CLIContext) -> Configuration:
    """框架启动函数。

    职责：
        1. 多来源配置合并 → BootstrapConfig
        2. 配置日志系统
        3. 初始化基础设施
        4. 返回 Configuration（frozen，不可修改）

    不创建任何层级 Context（由 Engine.run() 负责）。
    """
    # 1. 配置合并
    cfg = ConfigLoader().load(cli_ctx)

    # 2. 日志
    _configure_logging(cfg)

    # 3. 基础设施
    event_bus = InMemoryEventBus()
    archive = InMemoryArchive()
    ctx_manager = ContextManager(archive=archive, event_bus=event_bus)
    dispatcher = build_default_dispatcher()

    return Configuration(
        cfg=cfg,
        ctx_manager=ctx_manager,
        dispatcher=dispatcher,
        event_bus=event_bus,
        archive=archive,
    )
```

### Configuration

```python
@dataclass(frozen=True)
class Configuration:
    """bootstrap 的唯一产出。持有执行所需的全部基础设施引用。"""
    cfg: BootstrapConfig
    ctx_manager: ContextManager
    dispatcher: Any
    event_bus: Any
    archive: Any
```

---

## Engine

顶层执行器，持有 Configuration 引用。

```python
class Engine:
    """执行引擎。

    __init__ 只存引用，不做任何 I/O 或状态初始化。
    所有执行相关的状态都在 run() 内部创建，保证每次 run() 相互独立。
    """

    def __init__(self, configuration: Configuration) -> None:
        self._ictx = configuration

    def run(self, target: Scenario | Suite) -> RunResult:
        """执行入口。

        在此方法内创建本次执行的层级 context：
            1. FrameworkContext  —— 全量配置写入，run_id 在此生成
            2. SuiteContext      —— 单 scenario 执行时用 __default__ 占位
        然后分发到 ScenarioRunner。
        """
        # 1. 创建 FrameworkContext
        framework_ctx = ictx.ctx_manager.create_framework_context(
            run_id=str(uuid.uuid4()),
            cfg=ictx,
        )

        if isinstance(target, Scenario):
            return self._run_scenario(target, framework_ctx)
        elif isinstance(target, Suite):
            return self._run_suite(target, framework_ctx)
```

### _run_scenario()

```python
def _run_scenario(self, scenario: Scenario, framework_ctx: FrameworkContext) -> RunResult:
    # 为单 scenario 执行创建默认 SuiteContext
    suite_ctx = framework_ctx.ctx_manager.derive_suite_context(
        framework_ctx,
        suite_id="__default__",
        suite_name="Default Suite",
        tags=[],
        plugins={},
    )
    result = ScenarioRunner(
        framework_ctx.dispatcher,
        framework_ctx.ctx_manager
    ).run(scenario, suite_ctx)

    return RunResult(
        exit_code=0 if result.passed else 1,
        total=1,
        passed=1 if result.passed else 0,
        failed=0 if result.passed else 1,
        details=[{...}],
    )
```

### _run_suite()

```python
def _run_suite(self, suite: Suite, framework_ctx: FrameworkContext) -> RunResult:
    suite_ctx = framework_ctx.ctx_manager.derive_suite_context(
        framework_ctx,
        suite_id=getattr(suite, "suiteId", "__suite__"),
        suite_name=getattr(suite, "name", "Suite"),
        tags=[],
        plugins={},
    )
    runner = ScenarioRunner(framework_ctx.dispatcher, framework_ctx.ctx_manager)
    # 遍历执行，fail_fast 由 Configuration.cfg.fail_fast 控制
```

---

## RunResult

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

---

## ScenarioRunner

驱动整个 Scenario 的执行。

```python
class ScenarioRunner:
    def run(self, scenario_schema: Scenario, suite_ctx: SuiteContext) -> ScenarioRunResult:
        # 1. 派生 ScenarioContext
        scenario_ctx = self._ctx_manager.derive_scenario_context(
            suite_ctx,
            scenario_id=scenario_schema.scenarioId,
            scenario_name=scenario_schema.meta.name,
            description=scenario_schema.meta.description,
        )

        # 2. 注入 serviceDict / authDict 到 channels
        self._inject_config(scenario_schema, scenario_ctx)

        # 3. 创建 StepRunner，逐步执行
        step_runner = StepRunner(
            dispatcher=self._dispatcher,
            ctx_manager=self._ctx_manager,
            service_base_url=self._pick_base_url(scenario_schema),
        )

        step_results: list[StepRunResult] = []
        overall_status = "passed"

        for idx, step_union in enumerate(scenario_schema.steps):
            # 跳过未展开的 Ref
            if not hasattr(step_union, "api"):
                continue

            result = step_runner.run(step_union, scenario_ctx, idx)
            step_results.append(result)

            # fail_fast：首个失败即停止后续 step
            if not result.passed:
                overall_status = result.status
                break

        # 4. finalize ScenarioContext
        self._ctx_manager.finalize_scenario(scenario_ctx, overall_status)

        return ScenarioRunResult(...)
```

### ScenarioRunResult

```python
@dataclass
class ScenarioRunResult:
    scenario_id: str
    status: str           # passed / failed / error
    step_results: list[StepRunResult]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    @property
    def duration_ms(self) -> float:
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds() * 1000
        return 0.0
```

---

## StepRunner

构造 StepStateMachine 并触发执行。**不感知状态流转细节**。

```python
class StepRunner:
    """StepRunner 的职责：
      1. 创建 StepContext（由上层 scenario_ctx 派生）
      2. 构造 StepStateMachine（注入执行所需的全部依赖）
      3. 调用 sm.run()，拿到结果
      4. finalize StepContext
    """

    def run(
        self,
        step_schema: Step,
        scenario_ctx: ScenarioContext,
        step_index: int,
    ) -> StepRunResult:
        step_id = f"step-{step_index:03d}"

        # 1. 创建 StepContext
        step_ctx = self._ctx_manager.derive_step_context(
            scenario_ctx,
            step_id=step_id,
            step_name=step_id,
            strategy_kind="multi",
            strategy_spec=step_schema.model_dump(),
            resolved_vars={},
        )

        # 2. 构造状态机，注入全部执行依赖
        sm = StepStateMachine(
            step_id=step_id,
            step_schema=step_schema,
            dispatcher=self._dispatcher,
            view=StepContextAdapter(step_ctx),
            service_base_url=self._service_base_url,
        )

        # 3. 状态机自驱动运行
        result = sm.run()

        # 4. finalize StepContext
        step_status = StepStatus(result.status) \
            if result.status in StepStatus._value2member_map_ \
            else StepStatus.ERROR
        self._ctx_manager.finalize_step(step_ctx, step_status)

        return result
```

---

## 执行示例

```python
from gimbal.core.boostrap import bootstrap
from gimbal.core.runner import Engine, RunResult
from gimbal.cli.context import CLIContext

# 1. bootstrap 初始化基础设施
configuration = bootstrap(cli_ctx)

# 2. 创建 Engine
engine = Engine(configuration)

# 3. 执行
result = engine.run(scenario)  # 或 engine.run(suite)

# 检查结果
print(f"Exit code: {result.exit_code}")
print(f"Total: {result.total}, Passed: {result.passed}, Failed: {result.failed}")
```

---

## 运行测试

```bash
python -m gimbal.core.runner
python -m gimbal.core.scenario_runner
```
