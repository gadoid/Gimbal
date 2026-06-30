# PR-4.2 CLI Cancel Flag 与 scenario_runner 反向耦合解除

> Phase 4 / PR 2 of 9
> 优先级: 🔴 P0 基础
> 估计工作量: 1 PD
> 阻塞: PR-4.3

## 一句话目标

把"取消"做成 **per-Execution 的弱引 token**, 而不是模块级全局; 同时删除 `scenario_runner → cli.main` 的反向 import。

---

## 背景与动机

### 现状 finding (P0 基础债务)

**Finding A — 全局 cancel flag**:

```python
# src/gimbal/cli/main.py:24
_cancelled = False

def _set_cancelled(signum, frame):
    global _cancelled
    if not _cancelled:
        _cancelled = True
        ...
    else:
        raise KeyboardInterrupt()

def is_cancelled() -> bool:
    return _cancelled
```

问题:
1. 模块级 `global _cancelled` 在 `python -m gimbal run server --workers=8` 场景下, 所有 worker **共享** 同一 flag (fork 后仍相同内存, 除非 OS 强制 COW 失效)
2. 库使用者 (`from gimbal.cli.main import is_cancelled`) 不一定能预期全局副作用
3. 多进程 server 不能正确执行"主进程 SIGINT → 所有 worker 平滑退出"

**Finding B — 反向 import**:

`src/gimbal/core/scenario_runner.py:260-265`(原 review 表述):

```python
try:
    from gimbal.cli.main import is_cancelled
    _is_cancelled = is_cancelled
except Exception:
    _is_cancelled = lambda: False
```

后果:
- `core/` (业务内核) 反向依赖 `cli/` (用户界面), **违反分层依赖** (高层依赖低层)
- 测试 `core/` 时也会加载 `cli/main`, 进一步 install 副作用 (signal handler)
- 库使用者 `Engine(cfg, asset_store).run(scenario)` 在嵌入到主进程中时, **不应** 自动注册 SIGINT

## 范围与非目标

**In scope**:

- 引入 `gimbal/core/cancellation.py`,提供 `CancellationToken / CancellationSource`
- `Engine.run()` 接受 `cancel_token: CancellationToken | None = None` 参数
- `ScenarioRunner` 用 token 替换 `_is_cancelled` 调用
- `cli/main.py` 仍保留 SIGINT handler, 但它**创建 token 并通过 ctx 传给 Engine**, 而不是修改全局 flag
- `cli/main.py:24` 移除 `_cancelled` 全局变量
- 增加测试: 主进程 + 2 worker (multiprocessing) SIGINT 平滑退出

**Out of scope**:

- 取消 HTTP 长请求(需要 `httpx.AsyncClient` + async engine, 不在本 PR)
- 取消后台任务(Scheduled task)
- multi-Engine 共享 cancel(单 Engine per token)

---

## 设计

### 1. core/cancellation.py

```python
"""Per-Execution cancellation token, 替代 cli.main 的全局 _cancelled."""
from __future__ import annotations
import threading
from typing import Callable


class CancellationToken:
    """不可变取消句柄(可被多个调用方持有)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled = False
        self._callbacks: list[Callable[[], None]] = []

    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        with self._lock:
            if self._cancelled:
                return
            self._cancelled = True
            cbs = list(self._callbacks)
        for cb in cbs:
            try:
                cb()
            except Exception:
                pass

    def on_cancel(self, cb: Callable[[], None]) -> None:
        with self._lock:
            self._callbacks.append(cb)


class CancellationSource:
    """Token 的 owner: 触发 cancel."""
    def __init__(self) -> None:
        self._token = CancellationToken()

    @property
    def token(self) -> CancellationToken:
        return self._token

    def cancel(self) -> None:
        self._token.cancel()
```

> 注意: 进程级 cancel 仍需 OS signal + multiprocessing.Event; 这里只做 in-process 取消. 进程级 cancel 涉及 multiprocessing 在 phase5 处理.

### 2. Engine.run 接受 token

```python
class Engine:
    def run(
        self,
        target: Scenario | Suite,
        *,
        cancel_token: CancellationToken | None = None,
        ...
    ) -> RunResult:
        token = cancel_token or CancellationToken()
        # 透传给 ScenarioRunner
        ...
```

`ScenarioRunner.__init__` 同步加 `cancel_token` 字段.

### 3. CLI 改为 owner

```python
# cli/commands/run_launch.py (示意)
def launch(...):
    cli_ctx: CLIContext = ctx.obj
    configuration = bootstrap(cli_ctx)
    cancel_source = CancellationSource()
    _register_sigint_to_cancel(cancel_source)   # ← 取代全局 _set_cancelled
    asset_store = ...
    engine = Engine(configuration, asset_store=asset_store)
    try:
        result = engine.run(scenario, cancel_token=cancel_source.token)
    finally:
        shutdown(configuration)
```

```python
# cli/main.py
def _register_sigint_to_cancel(source: CancellationSource) -> None:
    """SIGINT 首次 → source.cancel(); 第二次 → raise KeyboardInterrupt."""
    def handler(signum, frame):
        if not source.token.is_cancelled():
            source.cancel()
            print("\n[gimbal] SIGINT 将在当前 step 完成后退出...")
        else:
            raise KeyboardInterrupt()
    try:
        signal.signal(signal.SIGINT, handler)
    except (ValueError, AttributeError):
        pass
```

cli/main.py 暴露的 **public API**:

| 旧 | 新 |
|---|---|
| `is_cancelled()` | 移除; 用户应持有 token |
| `reset_cancelled()` | 移除 |
| `_cancelled` | 移除 |

> 向后兼容性: 本 PR 不暴露给第三方 public API; Cli 内被替换即可.

### 4. 多 worker 取消 (跨进程)

server 模式的 `--workers=4` 含义 = multiprocessing. SIGINT 进到主进程会转发给 worker; 单进程 in-memory cancel 不能跨进程 —— 这块交由后续 phase5 处理, 本 PR **仅修正 in-process 取消**.

> **约定**: 本 PR 范围内, `--workers=1` 的 server 必须正确取消; `--workers>1` 仅取消主进程 worker (phase5 补救).

### 5. 测试

| 用例 | 验证 |
|---|---|
| CancellationToken.cancel() 单次有效 | idempotent |
| on_cancel 回调触发顺序 | LIFO 不要求, 仅正向 |
| Engine.run 接受 cancel_token, 完成后释放 | 副作用隔离 |
| ScenarioRunner 每 step 后检查 token | 行为可观察 |
| CLI SIGINT 二次触发 KeyboardInterrupt | 与旧行为一致 |
| 多线程并发 `is_cancelled` 读 | 读一致(读 lock-free) |

## 验收 (DoD)

### 必须

- [ ] `src/gimbal/core/cancellation.py` 实现
- [ ] `Engine.run(target, *, cancel_token=None)` 接受 token 参数
- [ ] `ScenarioRunner.__init__` 用 token 替代 lambda
- [ ] `cli/main.py` 删除 `_cancelled`, 全局 cancel 标志不再存在
- [ ] `cli/*commands/run_launch.py` 等所有 run 命令改为构造 `CancellationSource`
- [ ] 回归 `gimbal run launch`(无 cancel)行为一致
- [ ] `tests/unit/test_cancellation.py` 与 `tests/integration/test_cancel_sigint.py` 新增
- [ ] DECISIONS D30 / CHANGELOG

### Nice to have

- [ ] `docs/cli.md` 加 "Cancellation Token" 小节
- [ ] 跨进程 cancel (在 phase5 处理) 写 TODO comment

---

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 旧 `from gimbal.cli.main import is_cancelled` 引用残留 | conftest scan; 发 deprecation warning | 暂提供 shim, throw warning |
| token 在 callback 抛异常时是否影响 cancel 完整性 | try/except 包 callback, log warning | 调成"忽略异常" |
| Engine.run 默认 token 被 garbage collected 后 race | 本 PR 不跨 Engine 共享, 忽略 | 不回滚; 用户传 None 由 Engine 自建 |
| server 多 worker 仍无法 cancel | 加明文 TODO + phase5 引 `multiprocessing.Event` | 不回滚 |

---

## 任务清单

- [ ] T1 写 `core/cancellation.py` + 单测
- [ ] T2 Engine.run / ScenarioRunner 加 token 参数
- [ ] T3 cli/main.py 删全局 flag + 改 SIGINT handler
- [ ] T4 各 run 命令改为构造 CancellationSource
- [ ] T5 tests (单测 + 集成测)
- [ ] T6 DECISIONS D30 / CHANGELOG

---

## 依赖与并行

- **依赖**: PR-4.0 (不冲突, 但先 P0)
- **被依赖**: PR-4.3 (Engine 内部需要 token)
- **可并行**: PR-4.1 (asset store 独立)
