"""repository/backends/filesystem.py  —  内存归档（开发/测试用）。

生产环境替换为 MongoArchive + MinIO 实现，ContextManager 无需修改。
"""
from __future__ import annotations

import logging
from typing import Any

from gimbal.log import get_logger
logger = get_logger(__name__)

class InMemoryArchive:
    """将 Context 归档到内存字典，仅用于开发/测试。"""

    def __init__(self) -> None:
        self._suites: dict[str, Any] = {}
        self._scenarios: dict[str, Any] = {}
        self._steps: dict[str, Any] = {}
        logger.debug("[Archive] InMemoryArchive initialized (in-memory storage)")

    def save_suite(self, ctx: Any) -> None:
        key = getattr(ctx, "suite_id", str(id(ctx)))
        status = getattr(ctx, "status", "unknown")
        self._suites[key] = ctx
        logger.info("[Archive] Suite saved: suite_id={} status={} total_suites={}", key, status, len(self._suites))

    def save_scenario(self, ctx: Any) -> None:
        key = getattr(ctx, "scenario_id", str(id(ctx)))
        status = getattr(ctx, "status", "unknown")
        step_count = len(getattr(ctx, "step_refs", []))
        self._scenarios[key] = ctx
        logger.info("[Archive] Scenario saved: scenario_id={} status={} step_count={} total_scenarios={}",
                    key, status, step_count, len(self._scenarios))

    def save_step(self, ctx: Any) -> None:
        key = getattr(ctx, "step_id", str(id(ctx)))
        status = getattr(ctx.outcome, "status", "unknown") if hasattr(ctx, "outcome") else "unknown"
        duration_ms = getattr(ctx.outcome, "duration_ms", 0.0) if hasattr(ctx, "outcome") else 0.0
        self._steps[key] = ctx
        logger.debug("[Archive] Step saved: step_id={} status={} duration_ms={:.2f} total_steps={}",
                     key, status, duration_ms, len(self._steps))

    def save_exchange(self, exchange: Any, step_id: str) -> None:
        """将 scratch 快照归档，按 step_id 关联。"""
        self._steps[f"{step_id}_exchange"] = exchange
        logger.debug("[Archive] Exchange saved for step: {}", step_id)