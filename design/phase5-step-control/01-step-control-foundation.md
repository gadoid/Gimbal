# 阶段 1：First-class 控制能力

> Status: **Stash（待评审）**
> 解决: CLI `--step-to` 等参数真正可用；运行时控制能力 first-class
> 依赖: 无（阶段 1 是基础）
> 产出: 4 个 first-class 抽象 + 1 个内置 FlowControl 实现

---

## 1. 现状评估

现有 CLI 表面（[src/gimbal/cli/commands/run_scenario.py:39-50](src/gimbal/cli/commands/run_scenario.py#L39-L50)）声明了 3 个 flag：

| Flag | 当前实现 |
|---|---|
| `--step-from` | 仅做范围校验，未消费 |
| `--step-to` | 仅做范围校验，未消费 |
| `--breakpoint` | 仅做类型校验，未消费 |

**结论**：3 个 flag 都是 stub，CLI 接通是工作的 30%，剩下 70% 在框架核心——而**框架核心缺少承载控制意图的抽象**。

### 现有 4 套"中断语义"的内联代码

[src/gimbal/core/scenario_runner.py:278-331](src/gimbal/core/scenario_runner.py#L278-L331) 的 for 循环里**已经塞了 3 套中断**：

| 中断源 | 位置 | 终态 |
|---|---|---|
| scenario `timeout` | line 280-295 | `error` |
| SIGINT cancel | line 297-306 | `error` + marker |
| step 失败冒泡 | line 325-331 | `passed=false` |

每加一种新中断（如 step_to）就要改 for 循环——**违反开闭原则**。

## 2. 4 个 first-class 抽象

### 2.1 `GatePoint`（决策时机）

```python
# 伪代码描述
class GatePoint(str, Enum):
    """控制决策点——独立于 HookPoint 的正交维度。

    现有 HookPoint 表达"事件发生"，GatePoint 表达"决策时刻"。
    两者独立存在，可在同一执行位置布点。
    """
    STEP_BEFORE_ENTER = "step.before_enter"           # step 选择前
    SCENARIO_BEFORE_ENTER = "scenario.before_enter"   # scenario 选择前
    RUN_BEFORE_ENTER = "run.before_enter"             # run 选择前
```

**与 HookPoint 的关系**：
- `STEP_START` = step 即将开始（已决定要跑）
- `STEP_BEFORE_ENTER` = step 在 for 循环决策时（"要不要进"）

| 维度 | HookPoint | GatePoint |
|---|---|---|
| 语义 | 事件通知 | 决策时机 |
| 中断主流程 | ✅（`HookSignal.STOP`）| ✅（`ControlSignal.HALT/PAUSE/SKIP`）|
| 默认插件 | `ScenarioStartListener` 等 | `StepRangeGatePlugin` 等 |
| 时机粒度 | 阶段开始/结束 | 选择期 |

### 2.2 `ControlSignal`（控制信号）

```python
# 伪代码
class ControlSignal:
    """控制信号——独立于 HookSignal 的语义化集合。

    HookSignal.STOP 是"异常中断"，ControlSignal 是"控制意图"。
    现有 STOP 保留（异常路径），ControlSignal 处理控制路径。
    """
    HALT     = "halt"        # 计划性终止（"按计划停"）
    PAUSE    = "pause"       # 暂停（"等一下等会儿继续"）
    SKIP     = "skip"        # 跳过当前（"这个不要"）
    RETRY    = "retry"       # 重试当前
    COMPLETE = "complete"    # 自然完成（默认行为）
```

**与 HookSignal 的关系**：

| 信号 | 语义 | reporter 渲染 | CLI exit_code |
|---|---|---|---|
| `HookSignal.STOP` | 异常中断 | 红色 error | 非 0 |
| `ControlSignal.HALT` | 计划性终止 | 黄色 banner | 0（计划完成）|
| `ControlSignal.SKIP` | 跳过 | 灰色 | 0 |
| `ControlSignal.PAUSE` | 暂停 | 蓝色 | — |

### 2.3 `FlowControl`（控制策略）

```python
# 伪代码
class FlowControl(BaseModel):
    """step 间 / scenario 间 / run 间的控制流策略。

    与 Strategy 的对称关系：
      Strategy    → step 内做什么
      FlowControl → step 间做什么
    """
    kind: Literal["step_range", "step_limit", "fail_threshold", ...]

    # step_range: 从 idx=N 开始，到 idx=M 停止
    step_from: Optional[int] = None
    step_to:   Optional[int] = None

    # fail_threshold: 累计硬失败 N 次后停止
    max_failures: Optional[int] = None

    # pause_points: 在某些 step 后暂停
    pause_at: list[int] = Field(default_factory=list)
```

**与 Strategy 的对称**：
- `Strategy` 用 discriminated union（[src/gimbal/schema/strategy.py:81-84](src/gimbal/schema/strategy.py#L81) `Union[Extract, Assign, Assertion, StrategyRef]`，`discriminator="kind"`）实现 first-class 扩展
- `FlowControl` 同样用 discriminated union，让用户能扩展自己的控制策略

**内置实现**：
- `StepRangeFlowControl`（解决 step_to 需求）
- `FailThresholdFlowControl`（累计失败 N 次停）
- `TimeoutFlowControl`（替代现有内联 timeout）

### 2.4 `RuntimeControl`（运行时控制注入）

```python
# 伪代码
class RuntimeControl(BaseModel):
    """运行时控制——从 CLI / Configuration 注入，run 内不变。

    与 BootstrapConfig 平级，但语义是"运行时控制"不是"配置"。
    注入路径：CLI → Configuration.runtime → Engine.run() → ScenarioRunner
    """
    flow_controls: list[FlowControl] = Field(default_factory=list)
    breakpoints:   list[int]         = Field(default_factory=list)
    halt_on_first_failure: bool = False
    mode: Literal["execute", "validate", "dry_run"] = "execute"
```

**与 BootstrapConfig 的边界**：

| 类型 | 语义 | 是否可变 |
|---|---|---|
| `BootstrapConfig` | 框架配置（环境、日志、路径）| ❌ 不可变 |
| `RuntimeControl` | 运行时控制（控制流、暂停点）| ❌ 不可变（但语义独立） |

## 3. 4 层状态分层

把"step 范围控制"的状态拆成 4 层：

```
┌────────────────────────────────────────────────────────────┐
│ 第 1 层：入参状态 (RuntimeControl)                          │
│   - 数据类对象，被 Configuration 注入，ScenarioRunner.run 接收│
│   - 静态，整个 run 内不变                                   │
├────────────────────────────────────────────────────────────┤
│ 第 2 层：运行状态 (ScenarioRunState)                        │
│   - 挂在 ScenarioContext 上，被 ScenarioRunner 与 StepStateMachine 共同读写│
│   - 动态，伴随 step 推进变化                                │
├────────────────────────────────────────────────────────────┤
│ 第 3 层：step 级标记 (StepRunResult.controlled_halt)       │
│   - 标记"这个 step 是否触发控制中止"                         │
│   - 让 step 列表能反映"哪些 step 被框架主动停了"             │
├────────────────────────────────────────────────────────────┤
│ 第 4 层：scenario 终态 (ScenarioRunResult.halted)           │
│   - 整个 scenario 是不是被控制中止的                         │
│   - 携带 halted_at_step_index / halt_reason                │
│   - 被 RunResult.halted 计数、reporter 渲染                 │
└────────────────────────────────────────────────────────────┘
```

**关键原则**：每一层状态只服务于一个读侧消费者，**不要让上层状态做下层的事**。

## 4. 实现细节

### 4.1 新增/修改文件清单

| 文件 | 类型 | 改动 |
|---|---|---|
| `gimbal/control/__init__.py` (新) | 模块 | 新建 control 模块 |
| `gimbal/control/point.py` (新) | 抽象 | `GatePoint` 枚举 |
| `gimbal/control/signal.py` (新) | 抽象 | `ControlSignal` + `GateResult` |
| `gimbal/control/flow.py` (新) | 抽象 | `FlowControl` discriminated union + 内置实现 |
| `gimbal/control/gate.py` (新) | 抽象 | `GateBase` plugin 基类 + `StepRangeGate` 默认实现 |
| `gimbal/control/runtime.py` (新) | 抽象 | `RuntimeControl` 数据类 |
| `gimbal/context/scenario.py` | 修改 | 新增 `run_state: ScenarioRunState` 字段 |
| `gimbal/context/__init__.py` | 修改 | 导出 `ScenarioRunState` |
| `gimbal/core/hooks.py` | 修改 | 新增 `HookPoint.STEP_BEFORE_ENTER` |
| `gimbal/statemachine/engine.py` | 修改 | 入口 trigger `STEP_BEFORE_ENTER` hook；接收 `step_index / total` |
| `gimbal/statemachine/states.py` | 修改 | （可选）新增 `StepState.CONTROL_HALT` 终态 |
| `gimbal/core/scenario_runner.py` | 修改 | `run()` 接 `runtime_control`；for 循环调用 `gate_runner`；Result 扩展 |
| `gimbal/core/runner.py` | 修改 | `Engine._run_scenario` 透传 `runtime_control`；`RunResult` 加 `halted` 字段 |
| `gimbal/cli/commands/run_scenario.py` | 修改 | 把 `--step-from/--to/--breakpoint` 真正组装为 `RuntimeControl` |
| `gimbal/config/models.py` | 修改 | `Configuration` 加 `runtime: RuntimeControl` 字段 |
| `gimbal/reporter/*.py` | 修改 | 渲染 halted 状态 |

### 4.2 关键数据类

```python
# 伪代码
@dataclass
class ScenarioRunState:
    """Scenario 级别的运行期控制状态。"""
    current_step_index: int = 0
    total_steps: int = 0
    halt_requested: bool = False
    halt_reason: str = ""
    halted_at_step_index: Optional[int] = None
    halted_by: str = ""          # "timeout" / "cancel" / "step_to" / "fail_threshold"
    # 统计
    cumulative_failures: int = 0
    cumulative_successes: int = 0


@dataclass
class StepRunResult:
    # 现有字段
    step_id: str
    status: str
    phase_results: list[PhaseResult]
    error: Optional[str] = None
    duration_ms: float = 0.0
    error_phase: Optional[str] = None
    # 新增字段
    controlled_halt: bool = False   # 这个 step 是否触发控制中止
    control_reason: str = ""


@dataclass
class ScenarioRunResult:
    # 现有字段
    scenario_id: str
    status: str
    step_results: list[StepRunResult]
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    # 新增字段
    halted: bool = False
    halted_at_step_index: Optional[int] = None
    halt_reason: str = ""
    halt_kind: str = ""              # "timeout" / "cancel" / "step_to" / ...
    total_resolved_steps: int = 0    # 阶段 2 用


@dataclass
class RunResult:
    # 现有字段
    exit_code: int = 0
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)
    # 新增字段
    halted: int = 0
```

### 4.3 Gate 调度流程

```
ScenarioRunner.run(scenario_ctx) {
    for idx, step in step_resolver:           ← 阶段 2 改用 StepResolver
        # 1. Gate 决策
        gate_result = gate_runner.run(
            GatePoint.STEP_BEFORE_ENTER,
            {
                "step_index": idx,
                "total_steps": self._total,
                "scenario_ctx": scenario_ctx,
                "runtime_control": self._runtime_control,
            }
        )

        if gate_result.signal == ControlSignal.SKIP:
            # 跳过当前 step
            continue
        elif gate_result.signal == ControlSignal.HALT:
            # 计划性终止
            self._run_state.halt_requested = True
            self._run_state.halted_at_step_index = idx
            self._run_state.halt_reason = gate_result.reason
            self._run_state.halted_by = gate_result.source
            break
        elif gate_result.signal == ControlSignal.PAUSE:
            # 暂停（留待阶段 4 实现）
            ...

        # 2. 正常执行 step
        result = step_runner.run(step, scenario_ctx, idx, self._run_state)
        step_results.append(result)

        # 3. 累计统计
        if result.passed:
            self._run_state.cumulative_successes += 1
        elif result.status == "failed":
            self._run_state.cumulative_failures += 1

        # 4. 异常路径（保留兼容）
        if not result.passed and not result.controlled_halt:
            overall_status = result.status
            break
}
```

### 4.4 CLI 接通

```python
# src/gimbal/cli/commands/run_scenario.py - 伪代码
@app.command()
def scenario(
    # ... 现有参数 ...
    step_from: Optional[int] = typer.Option(None, "--step-from"),
    step_to:   Optional[int] = typer.Option(None, "--step-to"),
    breakpoint_: list[int] = typer.Option([], "--breakpoint"),
):
    # 现有校验
    if step_from is not None and step_to is not None and step_from > step_to:
        raise typer.BadParameter("--step-from 不能大于 --step-to")

    # 构造 RuntimeControl
    runtime_control = RuntimeControl(
        flow_controls=[
            StepRangeFlowControl(step_from=step_from, step_to=step_to)
        ] if (step_from is not None or step_to is not None) else [],
        breakpoints=breakpoint_,
    )

    # 注入到 Configuration
    configuration.runtime = runtime_control

    # ... 后续执行 ...
```

## 5. 中断语义的统一

阶段 1 完成后，4 套"中断"统一到 `ScenarioRunResult.halted` + `halted_by` 字段：

| 触发源 | `halted_by` 值 | `halted_at_step_index` | reporter 渲染 |
|---|---|---|---|
| step_to 到点 | `"step_to"` | 触发时的 idx | 黄色 banner "halted at step N" |
| 累计失败超阈值 | `"fail_threshold"` | 触发时的 idx | 黄色 banner "halted: failures > N" |
| scenario timeout | `"timeout"` | 触发时的 idx | 红色 banner（保持原样）|
| SIGINT cancel | `"cancel"` | 触发时的 idx | 红色 banner（保持原样）|

**关键原则**：不要给每种中断发明独立字段，统一在 `halted` / `halt_reason` / `halt_kind` 三个字段里表达。

## 6. 兼容性策略

### 6.1 老 scenario JSON
- 100% 兼容——`Step` / `Scenario` / `StrategyBase` 字段不动
- 老 JSON 不带 `run_control` → RuntimeControl 默认为空，走原路径

### 6.2 老 CLI 调用
- 100% 兼容——3 个 flag 行为变化是"真正生效"（之前是 stub）
- 不传任何 flag → RuntimeControl 默认为空，行为与原版一致

### 6.3 老 Plugin 体系
- 100% 兼容——`HookPoint` / `Strategy` / `Reporter` 都不动
- 新增 `GatePoint` 是正交维度，不影响老 hook

### 6.4 老 Reporter
- 兼容——只新增 `halted` 渲染，老 status（`passed` / `failed` / `error`）渲染不变
- `exit_code` 计算逻辑：halted 不算 error，但单独计入 `RunResult.halted`

## 7. 改动量估算

| 模块 | 行数估计 |
|---|---|
| `gimbal/control/` (5 个新文件) | 250-400 |
| `gimbal/context/scenario.py` | 5-10 |
| `gimbal/core/hooks.py` | 2 |
| `gimbal/statemachine/engine.py` | 10-20 |
| `gimbal/core/scenario_runner.py` | 30-50 |
| `gimbal/core/runner.py` | 5-10 |
| `gimbal/cli/commands/run_scenario.py` | 10-15 |
| `gimbal/config/models.py` | 5-10 |
| `gimbal/reporter/*` | 10-30/reporter |

**总计：~330-540 行**，分散在 12-15 个文件。

## 8. 测试覆盖

| 测试维度 | 覆盖点 |
|---|---|
| 单元测试（每个抽象） | GatePoint / ControlSignal / FlowControl / RuntimeControl |
| 集成测试（CLI 接通） | `--step-from=2 --step-to=5` 真正跳过 / 停止 |
| 兼容测试 | 老 JSON 跑出来行为不变 |
| Reporter 测试 | 渲染 halted 状态 |
| 状态机测试 | STEP_BEFORE_ENTER hook 触发顺序 |

## 9. 验收标准

- [ ] `gimbal run scenario xxx.json --step-to=5` 真正停在第 5 个 step
- [ ] `gimbal run scenario xxx.json --step-from=2` 真正从第 2 个 step 开始
- [ ] 多种中断源统一到 `ScenarioRunResult.halted` 字段
- [ ] 老 scenario JSON 行为不变
- [ ] 老 plugin 不受影响
- [ ] 阶段 1 的所有抽象都是 first-class（在 schema / context / result 中显式声明）
