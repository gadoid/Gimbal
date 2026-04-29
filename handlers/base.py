"""ActionHandler 基类"""
from abc import ABC, abstractmethod
from typing import Any
from schema.actions import Action
from runtime.context import ExecutionContext


class ActionHandler(ABC):
    """动作处理器抽象基类"""

    @abstractmethod
    def execute(self, action: Action, context: ExecutionContext) -> Any:
        """执行动作，返回结果"""
        pass
