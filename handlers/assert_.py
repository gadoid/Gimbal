"""AssertHandler - 断言处理器"""
from typing import Any
from schema.actions import Action
from handlers.base import ActionHandler
from runtime.context import ExecutionContext


class AssertHandler(ActionHandler):
    """断言处理器"""

    def execute(self, action: Action, context: ExecutionContext) -> Any:
        """执行断言验证"""
        actual = action.params.get("actual")
        expected = action.params.get("expected")
        operator = action.params.get("operator", "equals")
        message = action.params.get("message", "")

        passed = self._evaluate_assertion(actual, expected, operator)

        context.add_assertion(passed=passed, expected=expected, actual=actual, message=message)

        if not passed:
            raise AssertionError(f"{message} - Expected {expected} {operator} {actual}")

        return passed

    def _evaluate_assertion(self, actual: Any, expected: Any, operator: str) -> bool:
        """根据操作符评估断言"""
        if operator == "equals":
            return actual == expected
        elif operator == "not_equals":
            return actual != expected
        elif operator == "contains":
            return expected in actual
        elif operator == "greater_than":
            return actual > expected
        elif operator == "less_than":
            return actual < expected
        else:
            raise ValueError(f"Unknown operator: {operator}")
