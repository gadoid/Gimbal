"""AssignHandler - 变量赋值处理器"""
from typing import Any
from schema.actions import Action
from handlers.base import ActionHandler
from runtime.context import ExecutionContext


class AssignHandler(ActionHandler):
    """变量赋值处理器"""

    def execute(self, action: Action, context: ExecutionContext) -> Any:
        """将 value 赋值给 target 变量"""
        target = action.target
        value = action.params.get("value")

        if not target:
            raise ValueError("target variable name is required for assign action")

        context.set_variable(target, value)
        return value
