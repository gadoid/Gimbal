"""gimbal.scheduler — Suite 调度（串行 / scenario 级并行分派）。

公开面：SuiteScheduler.run_all（Engine._run_suite 使用）。
依赖 retry / dependency（重试策略、依赖图）留 suite 编排批次（总案 D5）。
"""
from gimbal.scheduler.scheduler import SuiteScheduler
from gimbal.scheduler.concurrency import clamp_workers, dispatch_parallel

__all__ = ["SuiteScheduler", "clamp_workers", "dispatch_parallel"]
