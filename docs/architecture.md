# Architecture Overview

## 项目概述

Gimbal 是一个测试框架，采用分层架构设计，核心执行链路为：**CLI → Engine → ScenarioRunner → StepRunner → StepStateMachine → StrategyDispatcher**。

## 核心架构

### 1. 模块层次

```
CLI (命令行接口)
    │
    ├── bootstrap()                      # 独立初始化函数
    │       ├── EventBus                 # 事件总线
    │       ├── Archive                  # 归档存储
    │       ├── ContextManager           # 上下文管理器
    │       └── StrategyDispatcher       # 策略分发器
    │
    └── Engine (执行引擎入口)
            │
            └── run(target)
                    │
                    ├── Scenario → ScenarioRunner
                    │       │
                    │       ├── StepRunner × n
                    │       │       │
                    │       │       ├── StepStateMachine (状态机自驱动)
                    │       │       │
                    │       │       └── StrategyDispatcher (策略执行)
                    │       │
                    │       └── ContextManager (上下文管理)
                    │
                    └── Suite → 遍历 Scenario × n
```

### 2. 核心模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| **CLI** | `gimbal/cli/` | 命令行入口，用户交互 |
| **Engine** | `core/runner.py` | 执行入口，Context 创建，结果汇总 |
| **ScenarioRunner** | `core/scenario_runner.py` | 单个 Scenario 驱动，Step 编排 |
| **StepRunner** | `core/scenario_runner.py` | 单个 Step 执行，状态机构造 |
| **StepStateMachine** | `statemachine/engine.py` | 状态流转控制，阶段执行 |
| **StrategyDispatcher** | `strategy/dispatcher.py` | 策略分发执行 |
| **ContextManager** | `context/manager.py` | 层级上下文生命周期管理 |

### 3. Schema 数据模型

```
Scenario (场景)
├── Meta (元信息)
├── Config (配置)
│   ├── setup/teardown (前置/后置动作)
│   ├── services (服务URL映射)
│   ├── users (认证信息)
│   └── retry (重试策略)
├── resource (资源)
└── steps: list[StepUnion]  # Step 或 StepRef
    └── Step
        ├── api: ApiUnion
        ├── request: RequestUnion
        └── strategy: list[StrategyUnion]
```

### 4. Context 层次结构

```
FrameworkContext (根节点，唯一)
└── SuiteContext (Suite 级别)
    └── ScenarioContext (Scenario 级别)
        └── StepContext (Step 级别)
```

### 5. Step 执行状态流转

```
PENDING
  └─→ BEFORE_REQUEST   执行 Assign 等前置策略
        ├─→ CALLING        策略全部通过
        └─→ TEARDOWN       hard-fail，跳过 HTTP
  CALLING               发出 HTTP 请求
        ├─→ AFTER_REQUEST  请求成功
        └─→ TEARDOWN       请求失败
  AFTER_REQUEST         执行 Extract 等后置策略
        ├─→ VERIFYING      策略全部通过
        └─→ TEARDOWN       hard-fail
  VERIFYING             执行 Assertion
        ├─→ PASSED         无 teardown 且全部通过
        ├─→ FAILED         无 teardown 且有失败
        └─→ TEARDOWN       有 teardown 策略（无论结果）
  TEARDOWN              执行清理策略
        ├─→ PASSED
        └─→ FAILED
```

### 6. 策略分发

| Phase | Executor | 说明 |
|-------|----------|------|
| `BEFORE_REQUEST` | AssignExecutor | 变量赋值/注入 |
| `CALLING` | CallExecutor | HTTP 调用 |
| `AFTER_REQUEST` | ExtractExecutor | 字段提取 |
| `VERIFYING` | AssertionExecutor | 断言验证 |
| `TEARDOWN` | 各种 Executor | 清理/恢复 |

### 7. Discriminated Union

使用 Pydantic `Annotated[Union[...], Field(discriminator="kind")]` 实现类型安全联合体：

- `StepUnion` = `Step` | `StepRef`
- `ApiUnion` = `Api` | `ApiRef`
- `StrategyUnion` = `Extract` | `Assign` | `Assertion` | `StrategyRef`

## 设计原则

### 1. 职责分离

- **Engine**: 只负责创建 Context 和分发执行
- **ScenarioRunner**: 驱动单个 Scenario，不感知状态细节
- **StepRunner**: 构造状态机，调用 `sm.run()`
- **StepStateMachine**: 持有执行依赖，内部循环驱动状态流转

### 2. 上下文隔离

每次 `Engine.run()` 创建独立的 Context 层级，相互隔离，保证并发/重复执行的安全性。

### 3. 策略不可知

状态机只负责流转控制，不感知具体策略逻辑。策略执行委托给 `StrategyDispatcher`。

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
    details: list[dict] = field(default_factory=list)
```

### ScenarioRunResult

```python
@dataclass
class ScenarioRunResult:
    scenario_id: str
    status: str  # passed / failed / error
    step_results: list[StepRunResult]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
```

### StepRunResult

```python
@dataclass
class StepRunResult:
    step_id: str
    status: str
    phase_results: list[PhaseResult]
    error: Optional[str] = None
    duration_ms: float = 0.0
```

### PhaseResult

```python
@dataclass
class PhaseResult:
    phase: str
    results: list[StrategyResult]

    @property
    def all_passed(self) -> bool
    @property
    def any_failed(self) -> bool
    @property
    def hard_failed(self) -> bool
```

## 执行流程

```
1. CLI 解析命令，构造 Scenario/Suite 对象
2. bootstrap() 初始化基础设施（EventBus/Archive/ContextManager/Dispatcher）
3. Engine.run(target)
   ├── 创建 FrameworkContext (run_id 唯一)
   ├── Scenario: 创建默认 SuiteContext，执行 ScenarioRunner.run()
   └── Suite: 遍历 suite.scenarios，执行每个 ScenarioRunner.run()
4. ScenarioRunner.run()
   ├── 创建 ScenarioContext
   ├── 注入 services/users 到 channels
   ├── 遍历 scenario.steps (StepUnion 列表)
   │   ├── StepRef: 跳过（未展开）
   │   └── Step: 调用 StepRunner.run()
   └── 汇总结果，finalize
5. StepRunner.run()
   ├── 创建 StepContext
   ├── 构造 StepStateMachine
   ├── 调用 sm.run()
   └── finalize StepContext
6. StepStateMachine.run()
   ├── PENDING → BEFORE_REQUEST
   ├── 循环直到终态
   └── 返回 StepRunResult
```
