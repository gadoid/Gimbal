"""sleep 策略 —— 生命周期条目的第一个内置动作（setup/teardown 等待）。

kind="sleep",params: {seconds: float}。经 dispatcher 分派；当前主要消费面
是 setup/teardown LifecycleEntry（step.strategy 的 StrategyUnion 为封闭联合,
不收 sleep——生命周期槽位是其设计消费点）。
"""
from __future__ import annotations

import time

from pydantic import BaseModel, ConfigDict, Field

from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus


class SleepParams(BaseModel):
    """sleep 的参数模型（编译期校验 / ext 导出）。"""

    model_config = ConfigDict(extra="forbid")

    seconds: float = Field(default=1.0, ge=0, le=600,
                           description="等待秒数（0-600）")


class SleepExecutor(StrategyExecutor):
    kind = "sleep"

    def execute(self, spec, view) -> StrategyResult:
        seconds = float(getattr(spec, "seconds", 1.0) or 0.0)
        time.sleep(seconds)
        return StrategyResult(
            status=StrategyStatus.PASSED,
            strategy_id="sleep",
            message=f"slept {seconds}s",
        )
