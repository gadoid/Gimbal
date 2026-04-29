"""SqlHandler - SQL 执行处理器"""
from typing import Any
from schema.actions import Action
from handlers.base import ActionHandler
from runtime.context import ExecutionContext


class SqlHandler(ActionHandler):
    """SQL 执行处理器"""

    def execute(self, action: Action, context: ExecutionContext) -> Any:
        """执行 SQL 查询"""
        sql = action.params.get("sql")
        if not sql:
            raise ValueError("SQL parameter is required")

        # TODO: 集成数据库适配器执行 SQL
        # result = db_client.execute(sql)
        # return result
        raise NotImplementedError("Database adapter not yet integrated")
