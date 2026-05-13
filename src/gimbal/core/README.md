# Core 模块

执行引擎核心模块，负责将 Schema 定义的测试用例转化为可执行的流程。

## 设计理念

### 1. 执行链路

```
CLI (RunRequest)
    │
    └── Runner
            │
            ├── bootstrap()          # 初始化基础设施
            │       ├── EventBus
            │       ├── Archive
            │       ├── ContextManager
            │       └── StrategyDispatcher
            │
            └── run()
                    │
                    ├── Scenario → ScenarioRunner
                    │       │
                    │       └── StepRunner × n
                    │               │
                    │               ├── StepStateMachine
                    │               └── StrategyDispatcher
                    │
                    └── Suite → 遍历 Scenario × n
```

### 2. 关注点分离

| 类 | 职责 |
|----|------|
| `Runner` | 入口编排，基础设施初始化 |
| `ScenarioRunner` | 单个 Scenario 的执行流程 |
| `StepRunner` | 单个 Step 的阶段执行 |
| `AssetResolver` | 资产解析（占位） |

### 3. Request/Result 契约

```
CLI → RunRequest → Runner → RunResult → CLI
```

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `runner.py` | `Runner`, `RunRequest`, `RunResult` |
| `scenario_runner.py` | `ScenarioRunner`, `StepRunner` |
| `asset_resolver.py` | `AssetResolver`, `ResolvedAsset` |
| `bootstrap.py` | `bootstrap()` 函数（框架） |

---

## RunRequest / RunResult

### RunRequest

```python
class RunRequest(BaseModel):
    """CLI 层和执行层之间的唯一契约。"""
    run: RunUnion                    # Scenario / Suite / 对应 Ref
    reference: Reference = Reference()
    runtime: RuntimeOptions = RuntimeOptions()
```

### RuntimeOptions

```python
class RuntimeOptions(BaseModel):
    env: str = "dev"                        # 运行环境
    profile: str = "default"                 # Profile 名称
    log_level: str = "info"                 # 日志级别
    reporters: list[str] = []                # 报告器列表
    report_dir: str = "./reports"           # 报告目录
    output: str = "console"                 # 输出格式
    fail_fast: bool = False                 # 首个失败停止
```

### RunResult

```python
@dataclass
class RunResult:
    exit_code: int = 0                       # 退出码
    total: int = 0                          # 总数
    passed: int = 0                         # 通过数
    failed: int = 0                         # 失败数
    skipped: int = 0                        # 跳过数
    error: int = 0                          # 错误数
    details: list[dict] = field(default_factory=list)  # 详情
```

---

## Runner

顶层执行器。

```python
class Runner:
    def __init__(self, run_request: RunRequest, ctx: CLIContext) -> None:
        self.request = run_request
        self.cli_ctx = ctx

    def run(self) -> RunResult:
        # 1. bootstrap 基础设施
        infra = self._bootstrap()

        # 2. 根据 run 类型分发
        if isinstance(run_target, Scenario):
            return self._run_single_scenario(run_target, infra)
        elif isinstance(run_target, Suite):
            return self._run_suite(run_target, infra)
        else:
            return RunResult(exit_code=3, error=1)
```

### _bootstrap()

```python
def _bootstrap(self) -> "_Infra":
    """初始化最小化基础设施。

    当前使用内存实现（EventBus / Archive），
    生产环境替换为 MongoDB + MinIO 实现即可。
    """
    event_bus = InMemoryEventBus()
    archive = InMemoryArchive()
    ctx_manager = ContextManager(archive=archive, event_bus=event_bus)

    # 创建 Framework / Suite Context
    framework_ctx = ctx_manager.create_framework_context(...)
    suite_ctx = ctx_manager.derive_suite_context(...)

    dispatcher = build_default_dispatcher()

    return _Infra(
        ctx_manager=ctx_manager,
        framework_ctx=framework_ctx,
        suite_ctx=suite_ctx,
        dispatcher=dispatcher,
    )
```

---

## ScenarioRunner

驱动单个 Scenario 执行。

### 核心方法

```python
class ScenarioRunner:
    def run(self, scenario_schema: Scenario, suite_ctx: SuiteContext) -> ScenarioRunResult:
        # 1. 创建 ScenarioContext
        scenario_ctx = self._ctx_manager.derive_scenario_context(...)

        # 2. 注入 config 到 channels
        self._inject_config(scenario_schema, scenario_ctx)

        # 3. 顺序执行所有 steps
        for idx, step_union in enumerate(scenario_schema.steps):
            result = step_runner.run(step_union, scenario_ctx, idx)
            step_results.append(result)
            if result.status in ("failed", "error") and fail_fast:
                break

        # 4. finalize
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
    def passed(self) -> bool: ...
    @property
    def duration_ms(self) -> float: ...
```

---

## StepRunner

驱动单个 Step 完成全部阶段。

### 执行阶段

```
PENDING → BEFORE_REQUEST → CALLING → AFTER_REQUEST → VERIFYING → [TEARDOWN] → PASSED/FAILED
```

### run() 方法流程

```python
def run(self, step_schema: Step, scenario_ctx: ScenarioContext, step_index: int) -> StepRunResult:
    # 1. 创建 StepContext
    step_ctx = self._ctx_manager.derive_step_context(...)

    # 2. 初始化状态机
    sm = StepStateMachine(step_id=step_id, on_transition=hook)

    # 3. BEFORE_REQUEST
    sm.advance(StepState.BEFORE_REQUEST)
    pr = self._run_phase(StrategyPhase.BEFORE_REQUEST, step_schema.strategy, view)
    if pr.hard_failed:
        sm.advance(StepState.TEARDOWN)
        self._run_teardown(...)
        return self._finalize(...)

    # 4. CALLING
    sm.advance(StepState.CALLING)
    call_result = self._do_http_call(step_schema, view, scenario_ctx)
    if call_result.failed:
        sm.advance(StepState.TEARDOWN)
        self._run_teardown(...)
        return self._finalize(...)

    # 5. AFTER_REQUEST
    sm.advance(StepState.AFTER_REQUEST)
    pr = self._run_phase(StrategyPhase.AFTER_REQUEST, step_schema.strategy, view)
    if pr.hard_failed:
        sm.advance(StepState.TEARDOWN)
        self._run_teardown(...)
        return self._finalize(...)

    # 6. VERIFYING
    sm.advance(StepState.VERIFYING)
    pr = self._run_phase(StrategyPhase.VERIFYING, step_schema.strategy, view)

    # 7. TEARDOWN (如果有)
    if has_teardown:
        sm.advance(StepState.TEARDOWN)
        self._run_teardown(...)
    else:
        terminal = StepState.PASSED if pr.all_passed else StepState.FAILED
        sm.advance(terminal)

    return self._finalize(...)
```

### _do_http_call()

```python
def _do_http_call(self, step_schema, view, scenario_ctx):
    # 1. 读取 API / Request
    api = step_schema.api
    request = step_schema.request
    body = getattr(request, "body", {})

    # 2. 合成 _CallSpec
    call_spec = _CallSpec(
        method=api.method,
        url=f"{service_url}{api.path}",
        headers=api.headers,
        body=body,
        timeout=api.timeout,
    )

    # 3. 分发执行
    return self._dispatcher.dispatch(call_spec, view)
```

### _CallSpec

内部 dataclass，用于 CallExecutor：

```python
@dataclass
class _CallSpec:
    kind: str = "_call"
    method: str = "GET"
    url: str = ""
    headers: dict = field(default_factory=dict)
    body: dict = field(default_factory=dict)
    timeout: float = 30.0
    # StrategyBase 必需字段
    name: Optional[str] = "http_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = field(default_factory=list)
```

---

## AssetResolver

资产解析器（占位）。

```python
class AssetResolver:
    """资产解析器。

    占位实现，演示接口。实际实现应：
      - 接入资产库（MongoDB + 对象存储）
      - 支持命名空间通配展开
      - 处理本地缓存与远端拉取的协调
    """

    def resolve(self, ids: list[str]) -> list[ResolvedAsset]:
        """将一组 ID（含通配）解析为具体的资产列表。"""
        ...

    def _is_namespace_wildcard(self, raw_id: str) -> bool:
        """命名空间通配：含 * 且只在分隔符之间。"""

    def _expand_namespace(self, pattern: str) -> list[ResolvedAsset]:
        """展开命名空间通配。占位实现。"""

    def _resolve_single(self, raw_id: str) -> ResolvedAsset | None:
        """解析单个 ID。占位实现。"""
```

---

## 执行示例

```python
from gimbal.core.runner import Runner, RunRequest, RuntimeOptions
from gimbal.schema import Scenario, Meta, Config

# 构造请求
request = RunRequest(
    run=scenario,
    runtime=RuntimeOptions(
        env="dev",
        fail_fast=True,
    )
)

# 执行
runner = Runner(request, cli_ctx)
result = runner.run()

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
