"""状态机相关异常。"""
from __future__ import annotations


class StateMachineError(Exception):
    """状态机基类异常。"""


class InvalidTransitionError(StateMachineError):
    """非法状态跃迁。"""

    def __init__(self, from_state: str, to_state: str) -> None:
        super().__init__(
            f"Invalid transition: {from_state!r} → {to_state!r}"
        )
        self.from_state = from_state
        self.to_state = to_state


class AlreadyTerminalError(StateMachineError):
    """对已处于终态的状态机发起跃迁。"""

    def __init__(self, state: str) -> None:
        super().__init__(f"State machine is already in terminal state: {state!r}")
        self.state = state