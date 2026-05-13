"""策略分发器（Dispatcher / Registry）。

维护 kind → StrategyExecutor 的映射，对外提供 dispatch() 接口。
框架内置 executor 在模块加载时自动注册；外部插件通过 register() 注入。
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .executor_base import StrategyExecutor, StrategyResult, StrategyStatus

if TYPE_CHECKING:
    from gimbal.context.views import StrategyContextView
    from gimbal.schema.strategy import StrategyBase


class StrategyDispatcher:
    """策略分发器。

    用法::

        dispatcher = StrategyDispatcher()
        dispatcher.register(ExtractExecutor())
        dispatcher.register(AssignExecutor())
        dispatcher.register(AssertionExecutor())

        result = dispatcher.dispatch(spec, view)
    """

    def __init__(self) -> None:
        self._registry: dict[str, StrategyExecutor] = {}

    def register(self, executor: StrategyExecutor) -> None:
        """注册一个 executor，以其 kind 为键。"""
        if not executor.kind:
            raise ValueError(f"{type(executor).__name__} must declare a non-empty `kind`")
        self._registry[executor.kind] = executor

    def dispatch(
        self,
        spec: "StrategyBase",
        view: "StrategyContextView",
    ) -> StrategyResult:
        """根据 spec.kind 找到对应 executor，执行并返回结果。

        框架在这里统一做：
          - 跳过 disabled 的策略
          - 计时
          - 兜底异常捕获（executor 内部不应抛出，但双保险）
        """
        kind = getattr(spec, "kind", None)
        strategy_id = getattr(spec, "name", None) or kind or "unknown"

        # 1. disabled 跳过
        if not getattr(spec, "enabled", True):
            return StrategyResult(
                status=StrategyStatus.SKIPPED,
                strategy_id=strategy_id,
                message="strategy disabled",
            )

        # 2. 查找 executor
        executor = self._registry.get(kind)  # type: ignore[arg-type]
        if executor is None:
            return StrategyResult(
                status=StrategyStatus.ERROR,
                strategy_id=strategy_id,
                message=f"No executor registered for kind={kind!r}",
                error=f"UnregisteredKind: {kind}",
            )

        # 3. 执行（含计时 + 兜底捕获）
        t0 = time.monotonic()
        try:
            result = executor.execute(spec, view)
        except Exception as exc:  # noqa: BLE001
            result = StrategyResult(
                status=StrategyStatus.ERROR,
                strategy_id=strategy_id,
                message=f"Unexpected exception in executor: {exc}",
                error=repr(exc),
            )
        result.duration_ms = (time.monotonic() - t0) * 1000
        result.strategy_id = result.strategy_id or strategy_id
        return result

    def dispatch_phase(
        self,
        phase: str,
        strategies: list["StrategyBase"],
        view: "StrategyContextView",
    ) -> list[StrategyResult]:
        """执行属于指定 phase 的所有策略，按 order 排序后顺序执行。

        遇到 hard-fail（onFailure=ABORT 且结果为 FAILED/ERROR）时提前终止。
        软失败（onFailure=CONTINUE/WARN）则记录并继续。

        Returns:
            已执行策略的结果列表（包括提前终止前已完成的部分）。
        """
        from gimbal.schema.strategy import FailurePolicy

        # 过滤出属于当前阶段的策略，按 order 排序
        phase_specs = sorted(
            (s for s in strategies if getattr(s, "phase", None) == phase),
            key=lambda s: getattr(s, "order", 0),
        )

        results: list[StrategyResult] = []
        for spec in phase_specs:
            result = self.dispatch(spec, view)
            results.append(result)

            # 失败时根据 onFailure 决定是否继续
            if result.failed:
                on_failure = getattr(spec, "onFailure", FailurePolicy.ABORT)
                if on_failure == FailurePolicy.ABORT:
                    break   # 硬中止，后续策略不再执行

        return results


def build_default_dispatcher() -> StrategyDispatcher:
    """构造并注册内置所有 executor 的 dispatcher。"""
    from gimbal.strategy.builtin.extract import ExtractExecutor
    from gimbal.strategy.builtin.assign import AssignExecutor
    from gimbal.strategy.builtin.assertion import AssertionExecutor
    from gimbal.strategy.builtin.call import CallExecutor

    d = StrategyDispatcher()
    d.register(ExtractExecutor())
    d.register(AssignExecutor())
    d.register(AssertionExecutor())
    d.register(CallExecutor())
    return d