"""Step 状态枚举与合法跃迁表。

状态机只负责维护当前状态、校验跃迁合法性，不持有业务逻辑。
业务逻辑全部在 engine.py 的驱动循环里。
"""
from __future__ import annotations

from enum import Enum


class StepState(str, Enum):
    """Step 生命周期状态。"""

    # ── 等待/就绪 ──────────────────────────────
    PENDING = "pending"          # 创建但尚未调度

    # ── 执行阶段（对应 StrategyPhase）──────────
    BEFORE_REQUEST = "before_request"   # Assign / SQL 注入
    CALLING = "calling"                 # HTTP 发出、等待响应
    AFTER_REQUEST = "after_request"     # Extract 提取字段
    VERIFYING = "verifying"             # Assertion / DBChecker
    TEARDOWN = "teardown"               # SQL 清理 / Chaos 恢复

    # ── 终态 ───────────────────────────────────
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"      # 框架级异常，区别于业务 FAILED
    SKIPPED = "skipped"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_STATES

    @property
    def is_running(self) -> bool:
        return self in _RUNNING_STATES


_TERMINAL_STATES = frozenset({
    StepState.PASSED,
    StepState.FAILED,
    StepState.ERROR,
    StepState.SKIPPED,
})

_RUNNING_STATES = frozenset({
    StepState.BEFORE_REQUEST,
    StepState.CALLING,
    StepState.AFTER_REQUEST,
    StepState.VERIFYING,
    StepState.TEARDOWN,
})

# ── 合法跃迁表 ────────────────────────────────────────────────────────────────
# key: 当前状态   value: 允许跃迁到的目标状态集合
VALID_TRANSITIONS: dict[StepState, frozenset[StepState]] = {
    StepState.PENDING: frozenset({
        StepState.BEFORE_REQUEST,
        StepState.SKIPPED,
    }),
    StepState.BEFORE_REQUEST: frozenset({
        StepState.CALLING,
        StepState.FAILED,   # 前置策略失败 → 直接 FAILED（跳过 HTTP 调用）
        StepState.TEARDOWN, # 前置失败且有 teardown 时
        StepState.ERROR,
    }),
    StepState.CALLING: frozenset({
        StepState.AFTER_REQUEST,
        StepState.FAILED,
        StepState.TEARDOWN,
        StepState.ERROR,
    }),
    StepState.AFTER_REQUEST: frozenset({
        StepState.VERIFYING,
        StepState.TEARDOWN,
        StepState.FAILED,
        StepState.ERROR,
    }),
    StepState.VERIFYING: frozenset({
        StepState.TEARDOWN,
        StepState.PASSED,   # 没有 teardown 时直接 PASSED
        StepState.FAILED,
        StepState.ERROR,
    }),
    StepState.TEARDOWN: frozenset({
        StepState.PASSED,
        StepState.FAILED,
        StepState.ERROR,
    }),
    # 终态不允许再跃迁
    StepState.PASSED: frozenset(),
    StepState.FAILED: frozenset(),
    StepState.ERROR: frozenset(),
    StepState.SKIPPED: frozenset(),
}