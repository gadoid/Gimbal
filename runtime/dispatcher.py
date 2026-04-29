"""ActionDispatcher - 动作调度器"""
from typing import Any
from schema.actions import Action, ActionType
from handlers import (
    ActionHandler,
    SqlHandler,
    ExtractHandler,
    AssignHandler,
    AssertHandler,
)
from runtime.context import ExecutionContext


class ActionDispatcher:
    """动作调度器，根据动作类型分发到对应的处理器"""

    def __init__(self):
        self._handlers: dict[ActionType, ActionHandler] = {
            ActionType.SQL: SqlHandler(),
            ActionType.EXTRACT: ExtractHandler(),
            ActionType.ASSIGN: AssignHandler(),
            ActionType.ASSERT: AssertHandler(),
        }

    def register_handler(self, action_type: ActionType, handler: ActionHandler):
        """注册动作处理器"""
        self._handlers[action_type] = handler

    def dispatch(self, action: Action, context: ExecutionContext) -> Any:
        """分发动作到对应处理器"""
        handler = self._handlers.get(action.type)
        if handler is None:
            raise ValueError(f"No handler registered for action type: {action.type}")
        return handler.execute(action, context)
