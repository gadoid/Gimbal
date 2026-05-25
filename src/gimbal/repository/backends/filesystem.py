"""repository/backends/filesystem.py  —  内存归档（开发/测试用）。

生产环境替换为 MongoArchive + MinIO 实现，ContextManager 无需修改。
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InMemoryArchive:
    """将 Context 归档到内存字典，仅用于开发/测试。"""

    def __init__(self) -> None:
        self._suites: dict[str, Any] = {}
        self._scenarios: dict[str, Any] = {}
        self._steps: dict[str, Any] = {}

    def save_suite(self, ctx: Any) -> None:
        key = getattr(ctx, "suite_id", str(id(ctx)))
        self._suites[key] = ctx
        logger.debug("[Archive] Suite saved: %s", key)

    def save_scenario(self, ctx: Any) -> None:
        key = getattr(ctx, "scenario_id", str(id(ctx)))
        self._scenarios[key] = ctx
        logger.debug("[Archive] Scenario saved: %s", key)

    def save_step(self, ctx: Any) -> None:
        key = getattr(ctx, "step_id", str(id(ctx)))
        self._steps[key] = ctx
        logger.debug("[Archive] Step saved: %s", key)

    def save_exchange(self, exchange: Any, step_id: str) -> None:
        """将 HttpExchange 归档，按 step_id 关联。"""
        self._steps[f"{step_id}_exchange"] = exchange
        logger.debug("[Archive] Exchange saved for step: %s", step_id)