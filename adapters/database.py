"""DbClient - 数据库客户端适配器"""
from typing import Any, Optional
import sqlite3


class DbClient:
    """数据库客户端，隔离所有数据库 IO 操作"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._connection: Optional[sqlite3.Connection] = None

    def connect(self):
        """建立数据库连接"""
        self._connection = sqlite3.connect(self.connection_string)
        self._connection.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """执行 SQL 查询"""
        if not self._connection:
            self.connect()

        cursor = self._connection.cursor()
        cursor.execute(sql, params)

        if sql.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        else:
            self._connection.commit()
            return [{"affected_rows": cursor.rowcount}]

    def close(self):
        """关闭数据库连接"""
        if self._connection:
            self._connection.close()
            self._connection = None
