"""ExecutionContext - 执行上下文和失败记录"""
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FailureRecord:
    """失败记录"""

    step_name: str
    action_type: str
    error_message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionContext:
    """执行上下文"""

    scenario_name: str
    variables: dict[str, Any] = field(default_factory=dict)
    failures: list[FailureRecord] = field(default_factory=list)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None

    def add_failure(self, step_name: str, action_type: str, error_message: str):
        """记录失败"""
        self.failures.append(
            FailureRecord(step_name=step_name, action_type=action_type, error_message=error_message)
        )

    def add_assertion(self, passed: bool, expected: Any, actual: Any, message: str = ""):
        """记录断言结果"""
        self.assertions.append(
            {"passed": passed, "expected": expected, "actual": actual, "message": message}
        )

    def set_variable(self, key: str, value: Any):
        """设置变量"""
        self.variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """获取变量"""
        return self.variables.get(key, default)
