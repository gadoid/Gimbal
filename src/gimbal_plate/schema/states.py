"""schema.states —— StepState 枚举定义(从 gimbal.schema.states 平移)。"""
from __future__ import annotations

from enum import Enum


class StepState(str, Enum):
    """步骤执行状态。"""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"