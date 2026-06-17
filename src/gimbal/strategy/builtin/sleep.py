"""SleepExecutor - 等待策略执行器（占位实现）。"""
from __future__ import annotations

import logging
import time
import traceback
from typing import Any, TYPE_CHECKING

from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus

if TYPE_CHECKING:
    from gimbal.context.views import StrategyContextView
    from gimbal.schema.strategy import StrategyBase

from gimbal.log import get_logger
logger = get_logger(__name__)


class SleepExecutor(StrategyExecutor):
    """等待指定时间后继续执行。

    占位实现，实际使用时需要完成。
    """

    kind = "sleep"

    def execute(self, spec: "StrategyBase", view: "StrategyContextView") -> StrategyResult:
        """执行等待策略：调用 time.sleep(spec.duration) 等待指定秒数后返回 PASSED。"""
        try:
            duration = getattr(spec, "duration", 1.0)
            logger.info("[SleepExecutor] 等待 {} 秒...", duration)
            time.sleep(duration)
            logger.info("[SleepExecutor] 等待完成")
            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"Slept for {duration}s",
            )
        except Exception as exc:
            logger.exception("[SleepExecutor] 等待异常")
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )
