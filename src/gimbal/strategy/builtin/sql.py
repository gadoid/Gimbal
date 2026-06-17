"""SqlExecutor - SQL 执行策略（占位实现）。"""
from __future__ import annotations

import logging
import traceback
from typing import Any, TYPE_CHECKING

from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus

if TYPE_CHECKING:
    from gimbal.context.views import StrategyContextView
    from gimbal.schema.strategy import StrategyBase
    
from gimbal.log import get_logger
logger = get_logger(__name__)


class SqlExecutor(StrategyExecutor):
    """执行 SQL 语句。

    占位实现，实际使用时需要接入数据库连接。
    """

    kind = "sql"

    def execute(self, spec: "StrategyBase", view: "StrategyContextView") -> StrategyResult:
        """执行 SQL 策略（占位实现）：目前仅记录日志并返回 PASSED，未实际连接数据库。"""
        try:
            sql = getattr(spec, "sql", "")
            logger.info("[SqlExecutor] 执行 SQL: {}", sql)
            # TODO: 接入数据库执行
            logger.warning("[SqlExecutor] SQL 执行器为占位实现，实际未执行 SQL")
            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"SQL executed (placeholder): {sql}",
            )
        except Exception as exc:
            logger.exception("[SqlExecutor] SQL 执行异常")
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )
