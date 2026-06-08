"""reporter/runtime.py — ReporterRuntime 调度器。

统一管理一组 Reporter 的生命周期：
    setup(...)       — bootstrap 阶段构造
    begin_all()      — Engine.run() 启动前调用，begin + 自动订阅
    notify(event)    — Engine/Runner 转发事件给所有 reporter（带错误隔离）
    finalize_all()   — Engine.run() 结束时调用，逐个 finalize
    shutdown()       — shutdown() 中调用，unsubscribe 全部订阅、记录错误

设计原则：
    - 单个 reporter 的任何异常（begin/on_event/finalize）都不影响其他 reporter。
    - 所有错误累积到 ReportErrorLog，最后打印到日志。
    - on_event 走 SYNC 订阅，reporter 不应阻塞主流程。
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from gimbal.core.runner import RunResult
from gimbal.context.framework import FrameworkContext
from gimbal.events.types import FrameworkEvent
from gimbal.events.subscription import SubscriptionMode
from gimbal.log import get_logger
from gimbal.reporter.base import ReportArtifact
from gimbal.reporter.protocol import ReportContext
from gimbal.reporter.registry import ReporterRegistry

logger = get_logger(__name__)


# ── ReportErrorLog ─────────────────────────────────────────────────────────────

@dataclass
class ReportErrorEntry:
    """单个 reporter 失败的记录。"""

    reporter_name: str
    phase: str                # "begin" / "on_event" / "finalize" / "shutdown"
    error_type: str
    error_message: str
    traceback: Optional[str] = None

    def short(self) -> str:
        return f"[{self.phase}] {self.reporter_name}: {self.error_type}: {self.error_message}"


@dataclass
class ReportErrorLog:
    """Reporter 错误累积容器。"""

    entries: list[ReportErrorEntry] = field(default_factory=list)

    def add(
        self,
        reporter_name: str,
        phase: str,
        exc: BaseException,
    ) -> None:
        self.entries.append(ReportErrorEntry(
            reporter_name=reporter_name,
            phase=phase,
            error_type=type(exc).__name__,
            error_message=str(exc),
            traceback=traceback.format_exc(),
        ))

    @property
    def has_errors(self) -> bool:
        return bool(self.entries)

    def summary(self) -> str:
        if not self.entries:
            return "ReportErrorLog: 0 errors"
        lines = [f"ReportErrorLog: {len(self.entries)} error(s)"]
        for e in self.entries:
            lines.append(f"  - {e.short()}")
        return "\n".join(lines)


# ── ReporterRuntime ────────────────────────────────────────────────────────────

class ReporterRuntime:
    """Reporter 调度器。

    状态机：
        new
         │ setup()
         ▼
        ready
         │ begin_all()
         ▼
        running
         │ notify() × N
         ▼
        running
         │ finalize_all()
         ▼
        finalized
         │ shutdown()
         ▼
        closed

    setup / begin_all / finalize_all 各自幂等：重复调用只生效一次。
    """

    def __init__(self, registry: ReporterRegistry) -> None:
        self._registry = registry
        self._bus: Any = None
        self._framework_ctx: Optional[FrameworkContext] = None
        self._config: Any = None
        self._reporters: list[Any] = []
        self._contexts: dict[str, ReportContext] = {}
        self._error_log = ReportErrorLog()
        self._state: str = "new"

    # ── 阶段 1：装配 ─────────────────────────────────────────────────────

    def setup(
        self,
        bus: Any,
        config: Any,
    ) -> None:
        """绑定 bus 与 config。在 bootstrap 末尾、Engine.run 之前调用。"""
        if self._state != "new":
            logger.debug("[ReporterRuntime] setup 已调用过，跳过")
            return
        self._bus = bus
        self._config = config
        self._state = "ready"
        logger.info("[ReporterRuntime] setup 完成: bus={}", type(bus).__name__)

    # ── 阶段 2：启动 ─────────────────────────────────────────────────────

    def begin_all(
        self,
        framework_ctx: FrameworkContext,
        reporter_names: list[str],
        report_dir: Path,
        plugin_configs: dict[str, dict[str, Any]],
    ) -> None:
        """实例化 reporters + 调 begin() + 调 ReporterBase.begin 自动订阅事件。

        Args:
            framework_ctx:  框架级 Context（在 Engine.run 内创建）
            reporter_names: BootstrapConfig.reporters 列表
            report_dir:     BootstrapConfig.report_dir 解析后的 Path
            plugin_configs: BootstrapConfig.plugin_configs（按 reporter.name 取子字典）
        """
        if self._state not in ("ready", "running"):
            logger.warning("[ReporterRuntime] begin_all 在 state=%s 下被调用，跳过", self._state)
            return
        self._framework_ctx = framework_ctx
        report_dir = Path(report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir = report_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._reporters = self._registry.create(reporter_names, plugin_configs or {})
        except Exception as exc:  # noqa: BLE001
            self._error_log.add("<registry>", "create", exc)
            logger.exception("[ReporterRuntime] reporter 实例化失败: {}", exc)
            self._state = "running"  # 仍然进入 running，但 _reporters 为空
            return

        for r in self._reporters:
            name = getattr(r, "name", type(r).__name__) or type(r).__name__
            ctx = ReportContext(
                framework_ctx=framework_ctx,
                bus=self._bus,
                config=self._config,
                report_dir=report_dir,
                user_config=(plugin_configs or {}).get(name, {}),
                artifacts_dir=artifacts_dir,
                subscription_mode=SubscriptionMode.SYNC,
            )
            self._contexts[name] = ctx
            try:
                r.begin(ctx)
            except Exception as exc:  # noqa: BLE001
                self._error_log.add(name, "begin", exc)
                logger.exception("[ReporterRuntime] reporter.begin 失败: name={}", name)

        self._state = "running"
        logger.info(
            "[ReporterRuntime] begin_all: reporters={} subscriptions={}",
            [getattr(r, "name", "?") for r in self._reporters],
            sum(len(c.subscription_ids) for c in self._contexts.values()),
        )

    # ── 阶段 3：流式事件转发（可由 Engine / Runner 主动调用） ────────────

    def notify(self, event: FrameworkEvent) -> None:
        """转发一个事件到所有 reporter（带错误隔离）。

        注意：通常情况下 reporter 通过 EventBus 自己订阅，**不需要** Engine
        主动 notify；此方法保留是为了让 Engine 在没有 bus 的场景（例如离线
        replay）也能驱动 reporter。
        """
        if self._state != "running":
            return
        for r in self._reporters:
            name = getattr(r, "name", type(r).__name__)
            try:
                r.on_event(event)
            except Exception as exc:  # noqa: BLE001
                self._error_log.add(name, "on_event", exc)
                logger.exception("[ReporterRuntime] reporter.on_event 失败: name={}", name)

    # ── 阶段 4：终结 ─────────────────────────────────────────────────────

    def finalize_all(self, run_result: RunResult) -> list[ReportArtifact]:
        """逐个 finalize reporter，产出 ReportArtifact 列表。

        异常隔离：单个 reporter 失败不会影响其他 reporter，错误入 error_log。
        """
        if self._state not in ("running", "ready"):
            logger.warning("[ReporterRuntime] finalize_all 在 state=%s 下被调用", self._state)

        artifacts: list[ReportArtifact] = []
        for r in self._reporters:
            name = getattr(r, "name", type(r).__name__)
            ctx = self._contexts.get(name)
            if ctx is None:
                # reporter 已经被 begin_all 跳过，不参与 finalize
                continue
            try:
                art = r.finalize(run_result, ctx)
            except Exception as exc:  # noqa: BLE001
                self._error_log.add(name, "finalize", exc)
                logger.exception("[ReporterRuntime] reporter.finalize 失败: name={}", name)
                continue
            if art is None:
                logger.warning("[ReporterRuntime] reporter.finalize 返回 None: name={}", name)
                continue
            # 兜底：补 name
            if not art.name:
                object.__setattr__(art, "name", name) if art.__class__ is ReportArtifact else None
            artifacts.append(art)
            logger.info(
                "[ReporterRuntime] reporter.finalize 完成: name={} path={} media={}",
                art.name,
                art.path,
                art.media_type,
            )

        self._state = "finalized"
        if self._error_log.has_errors:
            logger.warning(self._error_log.summary())
        return artifacts

    # ── 阶段 5：关闭 ─────────────────────────────────────────────────────

    def shutdown(self) -> ReportErrorLog:
        """unsubscribe 全部订阅，返回错误日志（调用方决定是否再处理）。"""
        if self._bus is None:
            self._state = "closed"
            return self._error_log
        for name, ctx in self._contexts.items():
            for sid in ctx.subscription_ids:
                try:
                    self._bus.unsubscribe(sid)
                except Exception as exc:  # noqa: BLE001
                    self._error_log.add(name, "shutdown", exc)
                    logger.exception("[ReporterRuntime] unsubscribe 失败: sub_id={}", sid)
        self._state = "closed"
        logger.info(
            "[ReporterRuntime] shutdown 完成: errors={}",
            len(self._error_log.entries),
        )
        return self._error_log

    # ── 辅助 ────────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def error_log(self) -> ReportErrorLog:
        return self._error_log

    @property
    def reporters(self) -> list[Any]:
        return list(self._reporters)
