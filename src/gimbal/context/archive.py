"""context/archive.py  —  Context 归档抽象与默认实现。

`Archive` 负责把 framework / suite / scenario / step 四个层级的 Context
（以及 step 的 exchange 快照）持久化下来，供 reporter / debugger 后续使用。

本模块只关心"Context 归档"，与"asset 仓库"（`gimbal.repository`）完全无关：
- Archive  → 保存执行历史（按 suite_id / scenario_id / step_id 寻址，进程内或外部 DB）
- Repository → 保存可复用的资产（按 namespace/name:tag 寻址，content-addressable）

当前仅提供 `InMemoryArchive` 一个实现（开发/测试用）。
生产实现可替换为 MongoArchive / PostgresArchive / S3Archive 等，
只要满足同样的 4 个 save_* 方法即可。
"""
from __future__ import annotations

from typing import Any, Protocol

from gimbal.log import get_logger
logger = get_logger(__name__)


class Archive(Protocol):
    """Context 归档的最小接口契约。

    ContextManager 依赖此 Protocol 而非具体类，因此后端（内存 / Mongo / PG）
    可以透明替换，ContextManager 不需要改。
    """

    def save_suite(self, ctx: Any) -> None: ...
    def save_scenario(self, ctx: Any) -> None: ...
    def save_step(self, ctx: Any) -> None: ...
    def save_exchange(self, exchange: Any, step_id: str) -> None: ...


class InMemoryArchive:
    """将 Context 归档到内存字典，仅用于开发/测试。

    用法：
        archive = InMemoryArchive()
        ctx_manager = ContextManager(archive=archive, event_bus=event_bus)

    线程安全：本实现**不是**线程安全的，仅适合单线程 / 串行运行。
    并行执行场景下应替换为线程安全的实现。
    """

    def __init__(self) -> None:
        self._suites: dict[str, Any] = {}
        self._scenarios: dict[str, Any] = {}
        self._steps: dict[str, Any] = {}
        logger.debug("[Archive] InMemoryArchive initialized (in-memory storage)")

    def save_suite(self, ctx: Any) -> None:
        key = getattr(ctx, "suite_id", str(id(ctx)))
        status = getattr(ctx, "status", "unknown")
        self._suites[key] = ctx
        logger.info(
            "[Archive] Suite saved: suite_id={} status={} total_suites={}",
            key, status, len(self._suites),
        )

    def save_scenario(self, ctx: Any) -> None:
        key = getattr(ctx, "scenario_id", str(id(ctx)))
        status = getattr(ctx, "status", "unknown")
        step_count = len(getattr(ctx, "step_refs", []))
        self._scenarios[key] = ctx
        logger.info(
            "[Archive] Scenario saved: scenario_id={} status={} step_count={} total_scenarios={}",
            key, status, step_count, len(self._scenarios),
        )

    def save_step(self, ctx: Any) -> None:
        key = getattr(ctx, "step_id", str(id(ctx)))
        status = getattr(ctx.outcome, "status", "unknown") if hasattr(ctx, "outcome") else "unknown"
        duration_ms = getattr(ctx.outcome, "duration_ms", 0.0) if hasattr(ctx, "outcome") else 0.0
        self._steps[key] = ctx
        logger.debug(
            "[Archive] Step saved: step_id={} status={} duration_ms={:.2f} total_steps={}",
            key, status, duration_ms, len(self._steps),
        )

    def save_exchange(self, exchange: Any, step_id: str) -> None:
        """将 scratch 快照归档，按 step_id 关联。"""
        self._steps[f"{step_id}_exchange"] = exchange
        logger.debug("[Archive] Exchange saved for step: {}", step_id)

    # ── 便利方法（仅供测试 / debugger 使用） ──
    def get_suite(self, suite_id: str) -> Any:
        return self._suites.get(suite_id)

    def get_scenario(self, scenario_id: str) -> Any:
        return self._scenarios.get(scenario_id)

    def get_step(self, step_id: str) -> Any:
        return self._steps.get(step_id)

    def stats(self) -> dict[str, int]:
        return {
            "suites": len(self._suites),
            "scenarios": len(self._scenarios),
            "steps": len(self._steps),
        }
