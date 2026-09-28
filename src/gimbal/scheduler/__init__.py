"""scheduler —— v2.1 多线程分派（PlanScheduler）。

历史 SuiteScheduler/dispatch_parallel 已随残留清理 #7 删除（批次 C 被
scheduler/plan.py 的 PlanScheduler 取代）。
"""
from gimbal.scheduler.plan import PlanScheduler

__all__ = ["PlanScheduler"]
