"""scheduler/scheduler.py — Suite 调度器（串行 / 并行两模式）。

2026-09-27 落地：Engine._run_suite 的调度逻辑抽到此处的 SuiteScheduler，
支持 suite.execution.parallel=True 时按 scenario 级线程池分派
（每个 scenario 一个单元；一进程一 run）。

串行模式 = 历史 for 循环逐字节等价（fail_fast 即 break）；
并行模式 = dispatch_parallel（结果按提交序汇总，fail-fast 尽力取消未开始单元）。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from gimbal.log import get_logger
from gimbal.scheduler.concurrency import dispatch_parallel

logger = get_logger(__name__)


class SuiteScheduler:
    """Suite 内 scenario 的分派器。

    用法::

        scheduler = SuiteScheduler()
        results = scheduler.run_all(
            scenarios,
            run_one=runner.run_one,          # (scenario) -> ScenarioRunResult
            parallel=suite.execution and suite.execution.parallel,
            max_workers=...,
            fail_fast=cfg.fail_fast,
        )
        # results 与 scenarios 等长同序（fail-fast 取消的项为 None）
    """

    def run_all(
        self,
        scenarios: list,
        run_one: Callable[[Any], Any],
        *,
        parallel: bool = False,
        max_workers: Optional[int] = None,
        fail_fast: bool = False,
    ) -> list[Optional[Any]]:
        """按指定模式执行全部 scenario，返回与 scenarios 等长同序的结果列表。

        串行：逐个执行；fail_fast 时首个不通过即停止（后续项 None）。
        并行：线程池分派；fail_fast 尽力取消未开始单元（在跑的不中断）。
        """
        if parallel:
            logger.info(
                "[SuiteScheduler] 并行分派: units={} max_workers={}",
                len(scenarios), max_workers or 4,
            )

            def _stop(result: Any) -> bool:
                if not fail_fast:
                    return False
                # 异常 / 结果不通过（passed 属性缺省视为通过）都触发收敛
                if isinstance(result, Exception):
                    return True
                return getattr(result, "passed", True) is False

            return dispatch_parallel(
                scenarios, run_one, max_workers=max_workers, stop_when=_stop,
            )

        # ── 串行（历史行为等价；额外保证结果与 scenarios 等长，取消项 None 占位）──
        results: list[Optional[Any]] = []
        stopped = False
        for scenario in scenarios:
            if stopped:
                results.append(None)
                continue
            try:
                results.append(run_one(scenario))
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "[SuiteScheduler] 单元执行异常: scenario_id={}",
                    getattr(scenario, "scenarioId", "?"),
                )
                results.append(exc)
                if fail_fast:
                    stopped = True
                continue
            if fail_fast and getattr(results[-1], "passed", True) is False:
                stopped = True
        return results
