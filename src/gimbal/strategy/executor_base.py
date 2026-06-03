"""策略执行器基类与执行结果。

每种策略（Extract / Assign / Assertion / Call / SQL …）对应一个 Executor 实现。
Executor 只做一件事：拿到策略 spec + context view，执行，返回 StrategyResult。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from gimbal.context.views import StrategyContextView
    from gimbal.schema.strategy import StrategyBase


class StrategyStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"    # executor 内部抛出未预期异常


@dataclass
class StrategyResult:
    """单条策略的执行结果。

    Attributes:
        status:      执行结论。
        strategy_id: 对应策略的 name 或自动生成的 id。
        message:     人类可读的描述（断言失败原因、提取路径等）。
        extracted:   本次提取/赋值写入 context 的键值（用于日志回放）。
        error:       非预期异常信息。
        duration_ms: 本条策略耗时。
        soft:        是否为软失败（spec.onFailure != ABORT 时由 dispatcher 置 True），
                     用于 PhaseResult.hard_failed 区分 hard/abort 失败。
                     注意：ERROR（系统异常）永远不是 soft。
    """

    status: StrategyStatus
    strategy_id: str = ""
    message: str = ""
    extracted: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    soft: bool = False

    @property
    def passed(self) -> bool:
        return self.status == StrategyStatus.PASSED

    @property
    def failed(self) -> bool:
        return self.status in (StrategyStatus.FAILED, StrategyStatus.ERROR)

    @property
    def hard_failed(self) -> bool:
        """硬失败：失败且非软。"""
        return self.failed and not self.soft


@dataclass
class PhaseResult:
    """一个阶段（phase）内所有策略执行结果的汇总。"""

    phase: str
    results: list[StrategyResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def any_failed(self) -> bool:
        return any(r.failed for r in self.results)

    @property
    def hard_failed(self) -> bool:
        """存在非软断言失败 → 必须中止。

        与 any_failed 的区别：CONTINUE/WARN 策略即使失败也不会触发 hard_failed。
        """
        return any(r.hard_failed for r in self.results)


class StrategyExecutor(ABC):
    """策略执行器抽象基类。

    子类只需实现 execute()，框架负责计时、异常捕获、日志。
    """

    # 子类声明自己处理哪种 kind
    kind: str = ""

    @abstractmethod
    def execute(
        self,
        spec: "StrategyBase",
        view: "StrategyContextView",
    ) -> StrategyResult:
        """执行策略，返回结果。不允许抛出异常——异常应被包裹进 StrategyResult。"""
        ...