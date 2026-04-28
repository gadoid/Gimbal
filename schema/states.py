"""StepState 枚举定义"""
from enum import Enum


class StepState(str, Enum):
    """步骤执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
