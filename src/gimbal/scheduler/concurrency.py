"""scheduler/concurrency.py — worker 数收敛工具。

dispatch_parallel 已随残留清理 #7 删除(并发分派由 scheduler/plan.py 的
PlanScheduler 自持线程池承担)。
"""
from __future__ import annotations

DEFAULT_MAX_WORKERS = 4
MAX_WORKERS_LIMIT = 64


def clamp_workers(max_workers: Optional[int]) -> int:
    """把用户给的 maxWorkers 钳制到 [1, 64]；None → 默认 4。"""
    if max_workers is None:
        return DEFAULT_MAX_WORKERS
    return max(1, min(int(max_workers), MAX_WORKERS_LIMIT))
