# PR-4.3 Engine 接入 Retry / Timeout / Multi-service + Observability 桥接(单线程)

> Phase 4 / PR 3 of 7
> 优先级: 🟡 P1 实现
> 估计工作量: 9 PD (原 10 PD, 单线程约束下砍掉 Scheduler/ParallelScheduler 后净省 1 PD)
> 阻塞: PR-4.8

## 一句话目标

> **2026-07-01 用户明确约束**: GIMBAL 1.0 = **单线程自动化测试框架**。不实现并发 / 调度 / 并行执行, 这些留 phase5+。

把 README / schema 已宣告但 Engine 不支持的**单线程执行控制项**真正读进执行路径:
- `RetryPolicy` (per step / scenario / suite 三层) — 替换 state machine 内的 hotfix
- `TimeoutPolicy` (`request_timeout` / `scenario_timeout`) — 真实生效
- multi-service 显式错误(替代静默降级)
- observability.logger 桥接到 `gimbal.log` backend

**不在 1.0 范围**: Scheduler Protocol / ParallelScheduler / 跨 scenario 并发 / 多进程 / `--parallel / --workers / --order parallel` flag 接受并报错。

---

## 背景与动机

### 现状 finding

**Pydantic 已就绪, Engine 没接**:

| 字段 | 来源 | Engine 读取情况 | 1.0 必要性 |
|---|---|---|---|
| `BootstrapConfig.request_timeout` | config/models.py | ❌ 任何位置 read | 🛑 必要 |
| `BootstrapConfig.scenario_timeout` | config/models.py | ❌ | 🛑 必要 |
| `BootstrapConfig.retry_count` / `retry_interval` | config/models.py | ❌ | 🛑 必要 |
| `RetryPolicy` | schema/retrypolicy.py | 部分 retry — StepStateMachine 内有 hotfix | 🛑 必要 |
| `TimePolicy` | schema/timepolicy.py | ❌ | 🛡️ nice |
| `BootstrapConfig.poll_timeout` / `poll_interval` | config/models.py | ❌ | 🛡️ nice |

### 实现的 requirement gap(单线程视角)

- README / `--help` 中提及 `--retry N` / `--scenario-timeout`, CLI 参数已就绪 (`cli/commands/run_launch.py`), **Engine 不读也不传**(单线程语义下, 这是必须修的)
- 多 service 场景 `ScenarioPreprocessor._pick_base_url` 显式降级 + warn, **但 schema 没禁**(单线程 1.0 不支持多 service, 必须显式报错)
- Step state machine 把 retry 编码为"跃迁到 PENDING" — `VALID_TRANSITIONS` 没把这个边列入合法, **靠 hotfix 救**

### 已被推后的(单线程下不做)

| 项 | 推到 |
|---|---|
| `Scheduler` Protocol + `SerialScheduler` / `ParallelScheduler` 抽象 | phase5+ (单线程不需要接口) |
| `ParallelScheduler(ThreadPool(max_workers=N))` | phase5+ (用户明确不要并发) |
| `scheduler/concurrency.py` 接入 | phase5+ (扩展位, 1.0 不接) |
| 跨 scenario / 跨 suite 并发 | phase5+ |
| `--parallel` / `--workers N` / `--order parallel` flag | 1.0 接 flag 但**显式报错** `NotSupportedIn1_0` |
| `ProcessPoolScheduler` | phase5+ |
| 跨 suite 并发 / Backpressure / rate-limit | phase5+ |

---

## 范围与非目标

### In scope

- `RetryPolicy` 真实读进 Engine, 替换 state machine hotfix(走外层 for-loop)
- `TimeoutPolicy` 真实读进 Engine (`request_timeout` / `scenario_timeout`)
- State machine 加 `TIMEOUT` 终态, `scenario_timeout` 中断时正确表达
- `teardown` 失败不参与 retry, 单独记录到 `result.teardown_error`
- CLI `--retry N / --scenario-timeout / --request-timeout` 真正接通 Engine
- multi-service (`services=[...]`) 显式错误 `MultiServiceNotSupportedIn1_0`, 不再静默降级
- `--parallel / --workers / --order parallel` flag 接受但显式报错(用户在旧 README 复制粘贴过来时有清晰提示)
- `observability.logger.StructuredLogger` 桥接到 `gimbal.log` 的可选 backend

### Out of scope

- Scheduler Protocol / ParallelScheduler / ThreadPool(phase5+)
- 跨 scenario / 跨 suite 并发(phase5+)
- `scheduler/concurrency.py` 接入(phase5+)
- 多进程 / Backpressure / rate-limit(phase5+)

---

## 设计

### 1. Retry 抽象(单线程语义)

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

**单线程实现**(无需 Scheduler Protocol):

```python
# core/scenario_runner.py
def run_step_with_retry(step, retry_policy, cancel_token):
    for attempt in range(1, retry_policy.max_attempts + 1):
        if cancel_token.cancelled:
            return StepResult(status=CANCELLED, attempts=attempt - 1)

        result = step_state_machine.run_step(step)
        if result.status == PASSED:
            return result

        if not should_retry(result, retry_policy):
            return result

        if attempt < retry_policy.max_attempts:
            time.sleep(retry_policy.interval_seconds)
    return result  # 最后一次失败
```

- retry 是 step 的**外层 for-loop**, **不是状态机内部跃迁**
- 检测到 `cancel_token.cancel()` 则跳出
- retry 期间该 step 的 context 不释放 (`scratch` 内 is volatile)
- 失败的 result 累积到 `StepResult.attempts`

### 2. Timeout 抽象

```python
# core/timeout.py
@dataclass
class TimeoutPolicy:
    request_timeout: float | None      # 单次 HTTP 请求 (秒)
    scenario_timeout: float | None      # 整个 scenario (秒, 包括 setup + 所有 step + teardown)
    step_timeout: float | None          # 单 step (秒, 不含 retry) — 1.0 可选实现
```

**单线程实现**:

```python
# core/engine.py
def run(self, scenario, *, cancel_token=None, timeout_policy=None):
    timeout_policy = timeout_policy or TimeoutPolicy()

    if timeout_policy.scenario_timeout is not None:
        cancel_token = cancel_token or CancellationToken()
        # 单线程 Timer 触发
        timer = Timer(timeout_policy.scenario_timeout, cancel_token.cancel)
        timer.start()
    try:
        result = self.scenario_runner.run(scenario, cancel_token)
        return result
    finally:
        if timer:
            timer.cancel()
```

- `Engine.run()` 用单线程 `threading.Timer` 触发 `cancel_token.cancel()`
- `StepStateMachine.run_step()` 用 `signal.alarm(request_timeout)` 或 HTTP client 层 timeout 实现 `request_timeout`
- State machine 新增 `TIMEOUT` 终态

### 3. State machine 改动

- `RetryPolicy` 与 statemachine 的 `VALID_TRANSITIONS` **解耦**:
  - 单次 step 仍走 `PENDING → CALLING → VERIFYING → ...`
  - retry 是 step 的"外层 for-loop", **不是状态机内部跃迁**
- 移除现有的 retry hotfix(把 retry 编码为"跃迁到 PENDING")
- `error_phase` (calling / verifying / teardown) 由 step state machine 输出, `RetryPolicy.retry_on_phases` 决定是否重试
- `teardown` 不参与 retry, 失败单独记录到 `result.teardown_error`
- 新增 `TIMEOUT` 状态(终态), 用于被 `scenario_timeout` 中断

### 4. multi-service 显式错误

```python
# preprocessor/scenario_preprocessor.py
def preprocess(scenario):
    if scenario.services and len(scenario.services) > 1:
        raise MultiServiceNotSupportedIn1_0(
            f"Scenario 声明了 {len(scenario.services)} 个 services, "
            f"GIMBAL 1.0 仅支持单 service。Phase 5+ 才支持 multi-service。"
        )
    # 单 service 走老路径
    return PreprocessedScenario(...)
```

**改动要点**:
- 删除 `_pick_base_url` 里的静默降级逻辑
- 改用显式 `ValidationError` 抛错
- 在 README 里加一段 "1.0 单 service 限制" 公告

### 5. CLI 真正串通(单线程视角)

`cli/commands/run_launch.py`:

```python
def launch(...):
    # 并发 flag 显式报错
    if parallel or workers > 1:
        raise NotSupportedIn1_0(
            "--parallel / --workers 在 GIMBAL 1.0 不支持。"
            "GIMBAL 1.0 是单线程自动化测试框架。"
            "如需并发执行, 请开多个 CLI 进程。"
        )

    # 单线程执行参数接通
    retry_policy = RetryPolicy(
        max_attempts=retry + 1,                 # CLI --retry N
        interval_seconds=retry_interval,
        retry_on_phases=("calling", "verifying"),
    )
    timeout_policy = TimeoutPolicy(
        request_timeout=request_timeout,
        scenario_timeout=scenario_timeout,
    )

    engine = Engine(
        configuration, asset_store=asset_store,
        retry_policy=retry_policy,
        timeout_policy=timeout_policy,
    )
    result = engine.run(scenario, cancel_token=cancel_token)
```

### 6. CLI 参数补齐(单线程)

| Flag | 1.0 处置 | PR-4.3 动作 |
|---|---|---|
| `--retry N` / `--retry-interval` | 真实接通 RetryPolicy | ✅ |
| `--scenario-timeout` | 真实接通 TimeoutPolicy | ✅ |
| `--request-timeout` | 真实接通 TimeoutPolicy | ✅ |
| `--parallel` / `--workers N` | **1.0 不支持**, 接受但报错 | ✅ 显式报错 |
| `--order parallel` | **1.0 不支持**, 接受但报错 | ✅ 显式报错 |
| `--step-timeout` | 1.0 不实现, --help 隐藏 | ❌ 推到 phase5+ |

### 7. observability.logger 桥接(顺手做)

```python
# log/setup.py
def setup_logging(backend: Literal["stdout", "structured"] = "stdout"):
    if backend == "structured":
        # 桥接到 observability.logger.StructuredLogger
        from gimbal.observability.logger import StructuredLogger
        return StructuredLogger()
    return StdoutLogger()  # 原 gimbal.log 默认
```

- 1.0 默认 `backend="stdout"`, 行为不变
- 用户可显式选 `backend="structured"`, 走 observability 的 StructuredLogger
- 避免"Engine 用 gimbal.log + observability.logger 完全没接"的双重实现

### 8. 测试矩阵(单线程)

| 用例 | 验证 |
|---|---|
| `RetryPolicy.max_attempts=3, 第 2 次成功` | `result.status=passed, attempts=2` |
| `RetryPolicy.retry_on_phases=()`, verifying 失败不重试 | `result.status=failed, attempts=1` |
| `scenario_timeout=0.5, scenario 内部 sleep > 0.5` | `step.status=timeout` |
| `request_timeout=1, HTTP call 阻塞 2 秒` | `step.status=failed, error=timeout` |
| `cancel_token.cancel()` 中途触发 | 立即退, `result.status=cancelled` |
| multi-service scenario | 抛 `MultiServiceNotSupportedIn1_0` |
| `--parallel` flag | 抛 `NotSupportedIn1_0` |
| `setup_logging(backend="structured")` | 输出 StructuredLogger 格式 |
| Engine 默认值与 `BootstrapConfig` 默认值一致 | 配置兼容 |

---

## 验收 (DoD)

### 必须

- [ ] `core/retry.py` `RetryPolicy` 实现 + Engine 真实读
- [ ] `core/timeout.py` `TimeoutPolicy` 实现 + Engine 真实读
- [ ] State machine hotfix 移除, retry 走外层 for-loop
- [ ] State machine 加 `TIMEOUT` 终态
- [ ] CLI `--retry / --scenario-timeout / --request-timeout` 真实生效
- [ ] multi-service 抛 `MultiServiceNotSupportedIn1_0`, 不再静默降级
- [ ] `--parallel / --workers / --order parallel` 抛 `NotSupportedIn1_0`
- [ ] `setup_logging(backend="structured")` 桥接到 `observability.logger`
- [ ] `tests/unit/test_engine_retry.py + test_engine_timeout.py + test_engine_multi_service.py + test_engine_concurrency_flag.py`
- [ ] DECISIONS D31 / D31c / D39 / CHANGELOG

### Nice to have

- [ ] exp backoff (`backoff=exponential, max_interval=30`)
- [ ] `--step-timeout`(单 step, 不含 retry)
- [ ] 跨 scenario 并发(留 phase5)

---

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| retry-on-teardown 让 reporter 误判通过 | teardown 失败仍记 failed, 不被 retry 覆盖 | 关闭 `retry_on_phases` |
| `scenario_timeout` 与 `cancel_token` 重叠 | Engine 内部二者协同, 不冲突 | 关闭 scenario_timeout, 走 cancel_token |
| multi-service 报错让现有用户脚本炸 | README 公告 + migration guide | 暂时退回静默降级 |
| Schema `RetryPolicy` 字段集与本 PR 重定义不一致 | D31c 决定 schema 是否 deprecated | 兼容 adapter |
| observability.logger 桥接导致日志格式变化 | 默认 backend="stdout", 不破坏行为 | 删除 backend 选项 |

---

## 任务清单

- [ ] T1 `core/retry.py` `RetryPolicy` 实现
- [ ] T2 `core/timeout.py` `TimeoutPolicy` 实现
- [ ] T3 State machine 删 retry hotfix + 加 `TIMEOUT` 终态
- [ ] T4 Engine / ScenarioRunner 接入 RetryPolicy + TimeoutPolicy(单线程)
- [ ] T5 multi-service 显式错误(`MultiServiceNotSupportedIn1_0`)
- [ ] T6 CLI `--parallel / --workers` 显式报错(`NotSupportedIn1_0`)
- [ ] T7 CLI `--retry / --scenario-timeout / --request-timeout` 接通
- [ ] T8 observability.logger 桥接(`setup_logging(backend=...)`)
- [ ] T9 单测 4 件套(retry / timeout / multi-service / concurrency flag)
- [ ] T10 DECISIONS D31 / D31c / D39 / CHANGELOG

---

## 依赖与并行

- **依赖**: PR-4.2 (cancel token)
- **被依赖**: PR-4.5 (测试), PR-4.7 (docs)
- **可并行**: PR-4.1 (GC), PR-4.4 (preprocessor, 已推迟)

---

## 与 phase5+ 的边界

PR-4.3 完成后, 以下事项**显式不做**:

- Scheduler Protocol 抽象
- ParallelScheduler / ProcessPoolScheduler
- 跨 scenario / 跨 suite 并发
- ThreadPool / Backpressure / rate-limit
- 多 service 真实执行

这些都推到 phase5+。如果未来要做, 应另立 phase(与 1.0 解耦), 不在 GIMBAL 主线路上叠加。