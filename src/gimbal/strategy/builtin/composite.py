"""CompositeExecutor - 组合策略执行器（占位实现）。"""
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


class CompositeExecutor(StrategyExecutor):
    """组合多个策略顺序执行。

    占位实现，实际使用时需要支持子策略列表的执行和结果聚合。
    """

    kind = "composite"

    def execute(self, spec: "StrategyBase", view: "StrategyContextView") -> StrategyResult:
        """执行组合策略（占位实现）：目前仅记录日志并返回 PASSED，未真正顺序执行子策略。"""
        try:
            name = getattr(spec, "name", "unnamed")
            logger.info("[CompositeExecutor] 执行组合策略: name={}", name)
            # TODO: 实现子策略列表的顺序执行和结果聚合
            logger.warning("[CompositeExecutor] 组合执行器为占位实现，实际未执行子策略")
            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"Composite executed (placeholder): {name}",
            )
        except Exception as exc:
            logger.exception("[CompositeExecutor] 组合策略异常")
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )
