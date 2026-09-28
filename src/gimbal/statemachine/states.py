"""Step 状态枚举与合法跃迁表。

状态机只负责维护当前状态、校验跃迁合法性，不持有业务逻辑。
业务逻辑全部在 engine.py 的驱动循环里。

协议中立化（2026-09-27）：执行阶段状态命名协议中立（PREPARE/INVOKING/
EXTRACTING）。历史同值别名（BEFORE_REQUEST/CALLING/AFTER_REQUEST）已随
残留清理退役（评审残留 #1）—— 枚举 value 不变，序列化零回归。

流转：
  PENDING
    └─→ PREPARE                    执行前置策略（Assign 等，协议无关）
          ├─→ INVOKING / CALLING     前置策略全部通过
          └─→ TEARDOWN               hard-fail，跳过协议调用
    INVOKING / CALLING             发出协议调用（由 ProtocolRegistry 分派）
          ├─→ EXTRACTING / AFTER_REQUEST  调用成功
          └─→ TEARDOWN               调用失败
    EXTRACTING / AFTER_REQUEST     执行后置策略（Extract 提取字段）
          ├─→ VERIFYING              策略全部通过
          └─→ TEARDOWN               hard-fail
    VERIFYING                      执行 Assertion
          ├─→ PASSED                 无 teardown 且全部通过
          ├─→ FAILED                 无 teardown 且有失败
          └─→ TEARDOWN               有 teardown 策略（无论结果）
    TEARDOWN                       执行清理策略
          ├─→ PASSED
          └─→ FAILED
"""
from __future__ import annotations

from enum import Enum


class StepState(str, Enum):
    """Step 生命周期状态。

    执行阶段状态为协议中立名（历史别名已退役，评审残留 #1）。
    """

    # ── 等待/就绪 ──────────────────────────────
    PENDING = "pending"          # 创建但尚未调度

    # ── 执行阶段（对应 StrategyPhase，协议无关）──
    PREPARE = "before_request"         # 协议前置准备（Assign / SQL 注入）
    INVOKING = "calling"               # 协议调用发出、等待结果
    EXTRACTING = "after_request"       # 调用结果后处理（Extract 提取字段）
    VERIFYING = "verifying"            # Assertion / DBChecker
    TEARDOWN = "teardown"              # SQL 清理 / Chaos 恢复

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
    StepState.PREPARE,
    StepState.INVOKING,
    StepState.EXTRACTING,
    StepState.VERIFYING,
    StepState.TEARDOWN,
})

# ── 合法跃迁表 ────────────────────────────────────────────────────────────────
# key: 当前状态   value: 允许跃迁到的目标状态集合
# （键用中立名；别名与中立名是同一成员，查表互通）
VALID_TRANSITIONS: dict[StepState, frozenset[StepState]] = {
    StepState.PENDING: frozenset({
        StepState.PREPARE,
        StepState.SKIPPED,
    }),
    StepState.PREPARE: frozenset({
        StepState.INVOKING,
        StepState.FAILED,   # 前置策略失败 → 直接 FAILED（跳过协议调用）
        StepState.TEARDOWN, # 前置失败且有 teardown 时
        StepState.ERROR,
    }),
    StepState.INVOKING: frozenset({
        StepState.EXTRACTING,
        StepState.FAILED,
        StepState.TEARDOWN,
        StepState.ERROR,
    }),
    StepState.EXTRACTING: frozenset({
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
