"""事件类型定义"""
from enum import Enum
from dataclasses import dataclass
from typing import Any


class EventType(str, Enum):
    """事件类型枚举"""

    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    SCENARIO_STARTED = "scenario_started"
    SCENARIO_COMPLETED = "scenario_completed"
    ASSERTION_PASSED = "assertion_passed"
    ASSERTION_FAILED = "assertion_failed"


@dataclass
class Event:
    """事件基类"""

    type: EventType
    data: dict[str, Any]
    timestamp: str = ""  # ISO format timestamp
