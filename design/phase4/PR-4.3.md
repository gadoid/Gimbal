# PR-4.3 Engine 接入 Retry / Parallel / Timeout(对齐 schema)

> Phase 4 / PR 3 of 9
> 优先级: 🟡 P1 实现
> 估计工作量: 2 PD
> 阻塞: PR-4.8

## 一句话目标

把 README / schema 已宣告但 Engine 不支持的若干执行控制项 (`retry_count / retry_interval / scenario_timeout / suite_timeout / request_timeout / poll_timeout / poll_interval`、并行模式) **真正读进执行路径**, 与现有 `RetryPolicy / TimePolicy` 对齐。

---

## 背景与动机

### 现状 finding

**Pydantic 已就绪, Engine 没接**:

| 字段 | 来源 | Engine 读取情况 |
|---|---|---|
| `BootstrapConfig.request_timeout` | config/models.py | ❌ 任何位置 read |
| `BootstrapConfig.scenario_timeout` | config/models.py | ❌ |
| `BootstrapConfig.suite_timeout` | config/models.py | ❌ |
| `BootstrapConfig.poll_timeout` / `poll_interval` | config/models.py | ❌ |
| `BootstrapConfig.retry_count` / `retry_interval` | config/models.py | ❌ |
| `RetryPolicy` | schema/retrypolicy.py | 部分 retry — StepStateMachine 内有 hotfix |
| `TimePolicy` | schema/timepolicy.py | ❌ |

**实现的 requirement gap**:

- README / `--help` 中提及 `--parallel` / `--order parallel` / `--retry N` / `--timeout`, **CLI 参数已就绪** (`cli/commands/run_launch.py`), 但 Engine 不读也不传;
- 多 service 场景 `ScenarioPreprocessor._pick_base_url` 显式降级 + warn, 但 schema 没禁;
- status: 用户用 `policy=...` 不生效; retry 走 hotfix; 并发永远串行。

### 同源问题面

- step state machine 把 retry 编码为"跃迁到 PENDING" — `VALID_TRANSITIONS` 没把这个边列入合法, 靠 hotfix 救;
- state machine 的 `error_phase` 与 schema 的 `TimePolicy.phase` 是两个 namespace, 两套契约;
- `SetUp / Teardown` 不在 step state machine 内, 失败时是否 retry 由谁决定未明示;
- Engine 没有 scheduler 接口 — 未来接 `scheduler/concurrency.py` (空壳) 必须重写。

## 范围与非目标

**In scope**:

- Engine 内部引入 `Scheduler` Protocol 接口(空实现 `SerialScheduler` / `ParallelScheduler` 两种)
- 读取 `RetryPolicy` (per step / scenario / suite 三层), 替换现有 hotfix
- 读取 `TimePolicy`, 与 state machine 的 `error_phase` 对齐
- CLI `--retry` / `--timeout` / `--parallel` / `--order` 真正传给 Engine
- 单测覆盖 happy / retry / partial-fail / cancel-during-retry

**Out of scope**:

- scheduler/concurrency.py 真实多进程 / 多线程池(那是空壳子包的 PR-4.6 决策内容)
- 跨 suite 并发(只到 scenario 级)
- Backpressure / rate-limit

---

## 设计

### 1. Scheduler 接口

```python
# core/scheduler.py
class Scheduler(Protocol):
    """调度抽象, Engine 透过此协议调度 scenario / step."""

    def schedule_scenarios(
        self,
        scenarios: list[Scenario],
        run_one: Callable[[Scenario], ScenarioResult],
    ) -> list[ScenarioResult]: ...


class SerialScheduler:
    """默认. 顺序跑 scenario, 第一失败后是否继续由 fail_fast 决定."""

class ParallelScheduler:
    """ThreadPool(max_workers=N). 每个 scenario 一个 future."""
    def __init__(self, max_workers: int = 4): ...
```

> 多进程 scheduler (`ProcessPoolScheduler`) **不在本 PR** 范围, 列 phase5.

### 2. Retry 抽象

```python
# core/retry.py
@dataclass
class RetryPolicy:
    max_attempts: int = 1                # 1 = 不重试
    interval_seconds: float = 0.0
    backoff: Literal["fixed", "exponential"] = "fixed"
    retry_on_phases: tuple[str, ...] = ("calling", "verifying")   # teardown 不重试
    retry_on_exceptions: tuple[type[Exception], ...] = ()
```

Engine.run → ScenarioRunner.run_scenario → for step:
- 用 `RetryPolicy.max_attempts + interval_seconds` 循环;
- 检测到 token.cancel() 则跳出;
- retry 期间该 step 的 context 不释放 (`scratch` 内 is volatile);
- 失败的 result 累积到 `StepResult.attempts`.

### 3. Timeout 抽象

```python
# core/timeout.py
@dataclass
class TimeoutPolicy:
    request_timeout: float | None      # 单次 HTTP 请求 (秒)
    scenario_timeout: float | None      # 整个 scenario (秒, 包括 setup + 所有 step + teardown)
    step_timeout: float | None          # 单 step (秒, 不含 retry)
```

`Engine.run()` 把 `scenario_timeout` 包成 outer timer, 触发 `cancel_token.cancel()` + `StepStatus = timeout`;

`StepStateMachine.run_step()` 包 `step_timeout` 包 `request_timeout` (HTTP 客户端层).

### 4. State machine 改动

- `RetryPolicy` 与 statemachine 的 `VALID_TRANSITIONS` 解耦:
  - 单次 step 仍走 `PENDING → CALLING → VERIFYING → ...`
  - retry 是 step 的"外层 for-loop", **不是状态机内部跃迁**
- `error_phase` (calling / verifying / teardown) 由 step state machine 输出, `RetryPolicy.retry_on_phases` 决定是否重试
- `teardown` 不参与 retry, 失败单独记录到 result.teardown_error
- 新增 `TIMEOUT` 状态(终态), 用于被 `scenario_timeout` 中断

### 5. CLI 真正串通

`cli/commands/run_launch.py`:

```python
def launch(...):
    ...
    scheduler = (ParallelScheduler(max_workers=N)
                 if parallel else SerialScheduler())
    retry_policy = RetryPolicy(
        max_attempts=retry + 1,                 # CLI --retry N
        interval_seconds=retry_interval,
        retry_on_phases=("calling",),            # 默认不改
    )
    timeout_policy = TimeoutPolicy(
        request_timeout=request_timeout,
        scenario_timeout=scenario_timeout,
    )
    engine = Engine(
        configuration, asset_store=asset_store,
        scheduler=scheduler,
        retry_policy=retry_policy,
        timeout_policy=timeout_policy,
    )
    result = engine.run(scenario, cancel_token=...)
```

### 6. CLI 参数补齐

| Flag | 当前 | 本 PR 补 |
|---|---|---|
| `--parallel` / `--workers N` | 字段尚未读 | 接入 Scheduler |
| `--retry N` / `--retry-interval` | 部分字段未传 | 接入 RetryPolicy |
| `--scenario-timeout` | 字段未传 | 接入 TimeoutPolicy |
| `--request-timeout` | 字段未传 | 接入 TimeoutPolicy |
| `--order {sequence,random,parallel}` | 不存在 | 列入 (若 reviewer 同意加) |

### 7. 测试矩阵

| 用例 | 验证 |
|---|---|
| SerialScheduler 单 scenario 顺序 | happy |
| ParallelScheduler 并发 4 个 | 同 scenario_id 互不污染 |
| RetryPolicy.max_attempts=3, 第 2 次成功 | result.status=passed, attempts=2 |
| RetryPolicy.retry_on_phases=(), verifying 失败不重试 | result.status=failed, attempts=1 |
| scenario_timeout=0.5, scenario 内部 sleep > 0.5 | step 状态=timeout |
| 取消中途触发 | 立即退 |
| Engine 默认值与 BootstrapConfig 默认值一致 | 配置兼容 |

---

## 验收 (DoD)

### 必须

- [ ] `core/scheduler.py` Protocol + Serial / Parallel 实现
- [ ] `core/retry.py` RetryPolicy 实现
- [ ] `core/timeout.py` TimeoutPolicy 实现
- [ ] `Engine.run()` 接受这三个 policy 参数
- [ ] CLI 接入, `--retry / --parallel / --scenario-timeout` 真正生效
- [ ] State machine hotfix 移除, retry 不再走 PENDING 跃迁
- [ ] tests/unit/test_engine_retry.py + test_engine_parallel.py + test_engine_timeout.py
- [ ] DECISIONS D31 / CHANGELOG

### Nice to have

- [ ] exp backoff (`backoff=exponential, max_interval=30`)
- [ ] 跨 suite 并发(留 phase5)

---

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| retry-on-teardown 让 reporter 误判通过 | teardown 失败仍记 failed, 不被 retry 覆盖 | 关闭 retry_on_phases |
| Parallel 与 reporter 单线程假设冲突 | ParallelScheduler 用 `ReporterRuntime.shutdown` 同步点 | 切换回 SerialScheduler (CLI fallback) |
| scenario_timeout 与 cancel_token 重叠 | Engine 内部二者协同, 不冲突 | 取消本 PR 改动, 走 hotfix |
| Schema `RetryPolicy` 字段集与本 PR 重定义不一致 | D31 决定 schema 是否 deprecated | 兼容 adapter |

---

## 任务清单

- [ ] T1 core/scheduler.py (Protocol + 2 impl)
- [ ] T2 core/retry.py
- [ ] T3 core/timeout.py
- [ ] T4 Engine / ScenarioRunner 接入
- [ ] T5 State machine 删 hotfix
- [ ] T6 CLI 参数接通
- [ ] T7 单测三件套
- [ ] T8 DECISIONS D31 / CHANGELOG

---

## 依赖与并行

- **依赖**: PR-4.2 (cancel token)
- **被依赖**: PR-4.5 (测试), PR-4.7 (docs), PR-4.8 (收口)
- **可并行**: PR-4.4 (preprocessor)
