"""gimbal_collector/plugin.py

CollectorPlugin：订阅框架事件 → 聚合到 ReportStore → run.end 时落盘 JSON。

设计决策：
- 不继承 Reporter（当前是 stub），直接继承 Plugin
- 单一职责：只生成 JSON；多格式由用户开多个 plugin 实例
- 9 个事件订阅，每个 handler 不抛错（EventBus._safe_call 也会兜一层）
- on_run_end 时触发 flush：先于框架关闭、写完盘再返回
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List

from gimbal.core.plugin import Plugin, PluginContext, PluginManifest

from .report_data import RunReport
from .renderers.json_renderer import JsonRenderer
from .store import ReportStore

logger = logging.getLogger(__name__)


class CollectorPlugin(Plugin):
    """收集测试执行过程信息，run 结束时写 JSON 报告。"""

    manifest = PluginManifest(
        name="gimbal-collector",
        version="0.1.0",
        entry_point="gimbal_collector.plugin:CollectorPlugin",
        description="Collect run/scenario/step/http/promotion events; emit JSON report on run.end.",
        capabilities=["reporter"],
        default_config={
            "output_dir": "./reports",
        },
    )

    def __init__(self) -> None:
        super().__init__()
        self._store = ReportStore()
        self._renderer = JsonRenderer()

    # ── 生命周期 ──────────────────────────────────────

    def on_activate(self, ctx: PluginContext) -> None:
        # 9 个事件订阅
        ctx.register_event("run.start",         self._handle_run_start)
        ctx.register_event("run.end",           self._handle_run_end,    priority=1)   # 最晚跑
        ctx.register_event("scenario.start",    self._handle_scenario_start)
        ctx.register_event("scenario.end",      self._handle_scenario_end)
        ctx.register_event("step.start",        self._handle_step_start)
        ctx.register_event("step.end",          self._handle_step_end)
        ctx.register_event("http.request",      self._handle_http_request)
        ctx.register_event("http.response",     self._handle_http_response)
        ctx.register_event("variable.promoted", self._handle_variable_promoted)

        # 重建 store（on_deactivate 之后会重置；activate 重新开）
        self._store = ReportStore()
        logger.info("[CollectorPlugin] activated")

    def on_deactivate(self) -> None:
        # 框架会负责 event_bus.unsubscribe_plugin(name)，这里只清状态
        self._store = ReportStore()
        logger.info("[CollectorPlugin] deactivated")

    # ── handler 转发（每个走同一 _safe 包裹） ──────────

    def _handle_run_start(self, event: Any) -> None:
        self._store.on_run_start(event)

    def _handle_run_end(self, event: Any) -> None:
        # 注意：run.end 同一个事件被订阅了两次（store + flush）
        # 这里用同一 store 实例，run.end 处理幂等
        self._store.on_run_end(event)
        self._flush(event)

    def _handle_scenario_start(self, event: Any) -> None:
        self._store.on_scenario_start(event)

    def _handle_scenario_end(self, event: Any) -> None:
        self._store.on_scenario_end(event)

    def _handle_step_start(self, event: Any) -> None:
        self._store.on_step_start(event)

    def _handle_step_end(self, event: Any) -> None:
        self._store.on_step_end(event)

    def _handle_http_request(self, event: Any) -> None:
        self._store.on_http_request(event)

    def _handle_http_response(self, event: Any) -> None:
        self._store.on_http_response(event)

    def _handle_variable_promoted(self, event: Any) -> None:
        self._store.on_variable_promoted(event)

    # ── 落盘 ──────────────────────────────────────────

    def _flush(self, _event: Any) -> None:
        if self.ctx is None:
            return
        report: RunReport | None = self._store.snapshot()
        if report is None:
            logger.warning("[CollectorPlugin] flush skipped: no run in store")
            return
        output_dir = Path(self.ctx.config.get("output_dir", "./reports"))
        try:
            paths: List[Path] = self._renderer.render(report, output_dir)
            logger.info(
                "[CollectorPlugin] report emitted: run_id=%s files=%s",
                report.run_id,
                [str(p) for p in paths],
            )
        except Exception as e:                       # noqa: BLE001
            logger.exception("[CollectorPlugin] flush failed: %s", e)
