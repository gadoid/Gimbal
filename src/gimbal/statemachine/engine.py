"""状态机引擎。

职责：
  - 持有单个 Step 的当前状态
  - 校验每次跃迁的合法性
  - 提供 advance() 驱动接口，由 Runner 在执行循环中调用

设计原则：
  - 状态机本身 **无副作用**：它不知道"如何执行策略"，
    只负责"我现在处于哪个状态、下一步可以去哪里"。
  - 具体的策略执行由 StrategyExecutor 完成，
    执行结果通知状态机应该跃迁到哪个状态。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from .exceptions import AlreadyTerminalError, InvalidTransitionError
from .states import VALID_TRANSITIONS, StepState


# 跃迁回调类型：每次状态变化时通知外部（用于日志/事件）
TransitionHook = Callable[[StepState, StepState, str], None]


@dataclass
class TransitionRecord:
    """一次跃迁的审计记录。"""

    from_state: StepState
    to_state: StepState
    reason: str
    at: datetime = field(default_factory=datetime.utcnow)


class StepStateMachine:
    """单个 Step 的状态机。

    用法::

        sm = StepStateMachine(step_id="step-001")
        sm.advance(StepState.BEFORE_REQUEST, reason="start")
        sm.advance(StepState.CALLING, reason="before_request done")
        ...
        sm.advance(StepState.PASSED, reason="all assertions passed")
        assert sm.is_terminal
    """

    def __init__(
        self,
        step_id: str,
        *,
        on_transition: Optional[TransitionHook] = None,
    ) -> None:
        self.step_id = step_id
        self._state: StepState = StepState.PENDING
        self._history: list[TransitionRecord] = []
        self._hook = on_transition

    # ── 只读属性 ──────────────────────────────────────────────────────────────

    @property
    def state(self) -> StepState:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state.is_terminal

    @property
    def history(self) -> tuple[TransitionRecord, ...]:
        return tuple(self._history)

    # ── 驱动接口 ──────────────────────────────────────────────────────────────

    def advance(self, to: StepState, *, reason: str = "") -> None:
        """将状态机推进到 `to` 状态。

        Args:
            to:     目标状态。
            reason: 简短说明（写入审计日志）。

        Raises:
            AlreadyTerminalError:   当前已是终态。
            InvalidTransitionError: 目标状态不在合法跃迁集合内。
        """
        if self._state.is_terminal:
            raise AlreadyTerminalError(self._state.value)

        allowed = VALID_TRANSITIONS.get(self._state, frozenset())
        if to not in allowed:
            raise InvalidTransitionError(self._state.value, to.value)

        record = TransitionRecord(
            from_state=self._state,
            to_state=to,
            reason=reason,
        )
        self._history.append(record)

        if self._hook:
            try:
                self._hook(self._state, to, reason)
            except Exception:
                pass  # hook 异常不影响主流程

        self._state = to

    def try_advance(self, to: StepState, *, reason: str = "") -> bool:
        """尝试跃迁，失败时返回 False 而不抛异常。适合在 teardown 等容错场景使用。"""
        try:
            self.advance(to, reason=reason)
            return True
        except (AlreadyTerminalError, InvalidTransitionError):
            return False

    def __repr__(self) -> str:
        return f"StepStateMachine(step_id={self.step_id!r}, state={self._state.value!r})"