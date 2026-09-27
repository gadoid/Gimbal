"""scheduler/concurrency.py — 并发控制原语（suite 多线程分派用）。

2026-09-27 落地总案决策 6：一进程一 run；单元级线程池（当前 Suite 是扁平
Scenario 列表，单元 = scenario）。max_workers 由 Suite.execution.maxWorkers
控制；suite 默认串行（parallel=False）与历史行为逐字节一致（零回归护栏）。

线程安全前提（总案批次 4 六锁点，均已落地）：
  事件总线 publish/subscribe 加锁；Archive 加锁 + 键空间化；Channels
  promote 复合操作加锁；HookRegistry 加锁；AuthRegistry 加锁；
  dispatcher/协议注册表运行期只读。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

from gimbal.log import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_WORKERS = 4
MAX_WORKERS_LIMIT = 64


def clamp_workers(max_workers: Optional[int]) -> int:
    """把用户给的 maxWorkers 钳制到 [1, 64]；None → 默认 4。"""
    if max_workers is None:
        return DEFAULT_MAX_WORKERS
    return max(1, min(int(max_workers), MAX_WORKERS_LIMIT))


def dispatch_parallel(
    items: list,
    run_one: Callable[[Any], Any],
    *,
    max_workers: Optional[int] = None,
    stop_when: Optional[Callable[[Any], bool]] = None,
) -> list[Any]:
    """把 items 全部提交到单元级线程池执行 run_one(item)，按**提交顺序**返回结果。

    stop_when(result) 返回 True 时进入 fail-fast 收敛：
      - 已在跑的任务不可中断（等待其自然结束，结果照常收集）；
      - 未开始的任务尽量取消（future.cancel）；
      - 结果列表长度恒等于 items（被取消的项以 None 占位，调用方跳过）。

    顺序保证：结果按提交序排列 —— 与串行输出的 details 顺序一致，可对账。
    事件顺序：各线程发布的事件经总线锁串行化（到达序=竞争序，非提交序）；
    台账按事件内容寻址，不依赖跨单元顺序。
    """
    results: list[Any] = [None] * len(items)
    if not items:
        return results

    workers = clamp_workers(max_workers)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="gimbal-unit") as pool:
        futures = {pool.submit(run_one, item): i for i, item in enumerate(items)}
        stopped = False
        for future in list(futures):
            idx = futures[future]
            if stopped:
                future.cancel()
                continue
            try:
                results[idx] = future.result()
            except Exception as exc:  # noqa: BLE001
                logger.exception("[Scheduler] 单元执行异常: index={} error={}", idx, exc)
                results[idx] = exc
                # 异常视为失败，交给 stop_when 判定是否收敛
                if stop_when is not None and stop_when(exc):
                    stopped = True
            else:
                if stop_when is not None and stop_when(results[idx]):
                    stopped = True
                    logger.warning(
                        "[Scheduler] fail-fast 触发：取消未开始单元（在跑的不中断）",
                    )
    return results
