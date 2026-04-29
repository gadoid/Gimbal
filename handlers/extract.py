"""ExtractHandler - 数据提取处理器"""
from typing import Any
from schema.actions import Action
from handlers.base import ActionHandler
from runtime.context import ExecutionContext
from interpolation.path import JsonPath


class ExtractHandler(ActionHandler):
    """数据提取处理器 - 从响应中提取数据存入变量"""

    def execute(self, action: Action, context: ExecutionContext) -> Any:
        """从 source 中提取数据到 target 变量"""
        source = action.params.get("source")
        expression = action.params.get("expression")
        target = action.target

        if not all([source, expression, target]):
            raise ValueError("source, expression, and target are required for extract action")

        # 使用 JsonPath 从 source 中提取数据
        value = JsonPath.get(source, expression)

        # 存入上下文变量
        context.set_variable(target, value)

        return value
