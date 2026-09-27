"""context/archive.py  —  Context 归档抽象与默认实现。

`Archive` 负责把 framework / suite / scenario / step 四个层级的 Context
（以及 step 的 exchange 快照）持久化下来，供 reporter / debugger 后续使用。

本模块只关心"Context 归档"（保存执行历史，按 suite_id / scenario_id /
step_id 寻址，进程内或外部 DB），不承载任何可复用资产的存取。

当前仅提供 `InMemoryArchive` 一个实现（开发/测试用）。
生产实现可替换为 MongoArchive / PostgresArchive / S3Archive 等，
只要满足同样的 4 个 save_* 方法即可。

线程安全 + 键空间化（2026-09-27 多线程分派）：
  - 全部 save_*/get_*/stats 在 RLock 内执行；
  - step / exchange 的键空间化为 ``(scenario_id, step_id)`` ——
    并行执行的多个 scenario 各自都有 step-000，裸 step_id 会互相覆盖，
    纯加锁解决不了键冲突，必须键空间化。get_step 先查带命名空间的键，
    再回落裸 step_id（兼容单线程时代的旧用法）。
"""
from __future__ import annotations

import threading
from typing import Any, Optional, Protocol

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


def _step_key_prefix(ctx: Any) -> str:
    """从 step ctx 推导键前缀（scenario_id）；推不出时退化为空串（单线程旧语义）。"""
    parent = getattr(ctx, "parent", None)
    scenario_id = getattr(parent, "scenario_id", None)
    return f"{scenario_id}:" if scenario_id else ""


class InMemoryArchive:
    """将 Context 归档到内存字典，仅用于开发/测试。

    用法::

        archive = InMemoryArchive()
        ctx_manager = ContextManager(archive=archive, event_bus=event_bus)

    线程安全：2026-09-27 起线程安全（RLock + step/exchange 键空间化），
    可用于并行 suite 执行；键空间见模块 docstring。
    """

    def __init__(self) -> None:
        self._suites: dict[str, Any] = {}
        self._scenarios: dict[str, Any] = {}
        self._steps: dict[str, Any] = {}
        self._lock = threading.RLock()
        logger.debug("[Archive] InMemoryArchive initialized (in-memory storage)")

    def save_suite(self, ctx: Any) -> None:
        key = getattr(ctx, "suite_id", str(id(ctx)))
        status = getattr(ctx, "status", "unknown")
        with self._lock:
            self._suites[key] = ctx
        logger.info(
            "[Archive] Suite saved: suite_id={} status={} total_suites={}",
            key, status, len(self._suites),
        )

    def save_scenario(self, ctx: Any) -> None:
        key = getattr(ctx, "scenario_id", str(id(ctx)))
        status = getattr(ctx, "status", "unknown")
        step_count = len(getattr(ctx, "step_refs", []))
        with self._lock:
            self._scenarios[key] = ctx
        logger.info(
            "[Archive] Scenario saved: scenario_id={} status={} step_count={} total_scenarios={}",
            key, status, step_count, len(self._scenarios),
        )

    def save_step(self, ctx: Any) -> None:
        key = getattr(ctx, "step_id", str(id(ctx)))
        status = getattr(ctx.outcome, "status", "unknown") if hasattr(ctx, "outcome") else "unknown"
        duration_ms = getattr(ctx.outcome, "duration_ms", 0.0) if hasattr(ctx, "outcome") else 0.0
        # 键空间化：并行 scenario 的同名 step_id 不互踩
        store_key = f"{_step_key_prefix(ctx)}{key}"
        with self._lock:
            self._steps[store_key] = ctx
        logger.debug(
            "[Archive] Step saved: key={} status={} duration_ms={:.2f} total_steps={}",
            store_key, status, duration_ms, len(self._steps),
        )

    def save_exchange(self, exchange: Any, step_id: str, *, scenario_id: Optional[str] = None) -> None:
        """将 scratch 快照归档，按 (scenario_id, step_id) 关联。

        scenario_id 显式传入优先；缺省时尝试从 step ctx 反查
        （ContextManager.finalize_step 调用点已知 scenario，直接传入）。
        """
        store_key = f"{scenario_id}:{step_id}" if scenario_id else step_id
        with self._lock:
            self._steps[f"{store_key}_exchange"] = exchange
        logger.debug("[Archive] Exchange saved for step: {}", store_key)

    # ── 便利方法（仅供测试 / debugger 使用） ──
    def get_suite(self, suite_id: str) -> Any:
        with self._lock:
            return self._suites.get(suite_id)

    def get_scenario(self, scenario_id: str) -> Any:
        with self._lock:
            return self._scenarios.get(scenario_id)

    def get_step(self, step_id: str, *, scenario_id: Optional[str] = None) -> Any:
        """按 step_id 取归档的 StepContext。

        先查键空间化键（scenario_id 显式给定或任意 scenario 的同名 step），
        找不到再回落裸 step_id（单线程时代语义）。
        """
        with self._lock:
            if scenario_id:
                hit = self._steps.get(f"{scenario_id}:{step_id}")
                if hit is not None:
                    return hit
            hit = self._steps.get(step_id)
            if hit is not None:
                return hit
            # 回落：任意 scenario 命名空间下的该 step（并行归档后最常见形态）
            suffix = f":{step_id}"
            for key, value in self._steps.items():
                if key.endswith(suffix):
                    return value
            return None

    def get_exchange(self, step_id: str, *, scenario_id: Optional[str] = None) -> Any:
        """按 (scenario_id, step_id) 取归档的 exchange 快照（get_step 的 exchange 对应物）。"""
        with self._lock:
            if scenario_id:
                hit = self._steps.get(f"{scenario_id}:{step_id}_exchange")
                if hit is not None:
                    return hit
            hit = self._steps.get(f"{step_id}_exchange")
            if hit is not None:
                return hit
            suffix = f":{step_id}_exchange"
            for key, value in self._steps.items():
                if key.endswith(suffix):
                    return value
            return None

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "suites": len(self._suites),
                "scenarios": len(self._scenarios),
                "steps": len(self._steps),
            }
