"""test_report/plugin.py
``ReportPlugin`` — 自动激活的测试报告插件。

设计目标（重申用户需求）：
  1. 提供 ``plugin.yaml`` 作为唯一配置文件
  2. ``gimbal-bootstrap`` 时由 ``PluginLoader.discover`` 自动发现，不需要
     用户在 CLI 传任何参数
  3. ``run.end`` 事件触发时，根据 ``default_config.output_path`` 把累积的
     run/suite/scenario/step/http/promotion 全量数据渲染为单文件 HTML 报告

设计原则：
  - 与 ``gimbal-collector`` 一样的扁平订阅：聚合在 ``ReportStore``，渲染
    在 ``HtmlRenderer``，flush 在 plugin 自身 —— 单一 ``Plugin`` 类承担，
    不去注册为 ``Reporter``（CI 摘要里不会出现；这符合"默默生成"语义）
  - ``run.end`` 用 ``priority=1``（最晚跑）保证所有 step / http / promotion
    事件先入库
  - flush 失败用 ``logger.exception`` 兜底，绝不影响 framework 退出码
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List

from gimbal.core.plugin import Plugin, PluginContext, PluginManifest

from .renderers import HtmlRenderer
from .store import ReportStore

logger = logging.getLogger(__name__)


class ReportPlugin(Plugin):
    """订阅框架事件 → 累积到 ReportStore → run.end 时落盘 HTML。"""

    manifest = PluginManifest(
        name="gimbal-test-report",
        version="0.2.0",
        entry_point="test_report.plugin:ReportPlugin",
        description=(
            "Auto-activates on bootstrap and emits a single-file HTML test "
            "report at run.end. Zero CLI args required. v2 collects full "
            "process information: HTTP exchanges, variable promotions, "
            "suite grouping, framework version, and run meta."
        ),
        capabilities=["reporter"],
        default_config={
            "output_path": "./reports/test-report.html",
            "title": "Gimbal Test Report",
            "include_passed": True,
            "include_http_body": False,
            "max_body_chars": 4096,
        },
    )

    def __init__(self) -> None:
        super().__init__()
        self._store = ReportStore()
        self._renderer = HtmlRenderer()

    # ── 生命周期 ─────────────────────────────────────────

    def on_activate(self, ctx: PluginContext) -> None:
        # 重置 store（避免上次 deactivate 残留）
        self._store = ReportStore()

        # 14 个事件订阅。run.end 用 priority=1 让它最后执行
        # 这样所有 step / http / promotion 事件都已入库。
        ctx.register_event("framework.init",     self._handle_framework_init)
        ctx.register_event("run.start",          self._handle_run_start)
        ctx.register_event("run.meta",           self._handle_run_meta)
        ctx.register_event("run.end",            self._handle_run_end, priority=1)
        ctx.register_event("suite.start",        self._handle_suite_start)
        ctx.register_event("suite.end",          self._handle_suite_end)
        ctx.register_event("scenario.start",     self._handle_scenario_start)
        ctx.register_event("scenario.end",       self._handle_scenario_end)
        ctx.register_event("step.start",         self._handle_step_start)
        ctx.register_event("step.end",           self._handle_step_end)
        ctx.register_event("step.failed",        self._handle_step_failed)
        ctx.register_event("http.request",       self._handle_http_request)
        ctx.register_event("http.response",      self._handle_http_response)
        ctx.register_event("variable.promoted",  self._handle_variable_promoted)

        logger.info(
            "[TestReportPlugin] activated, output=%s",
            ctx.config.get("output_path", "<unset>"),
        )

    def on_deactivate(self) -> None:
        # 框架会负责 event_bus.unsubscribe_plugin(name) / hook_registry 清理
        # 这里只清本地状态
        self._store = ReportStore()
        logger.info("[TestReportPlugin] deactivated")

    # ── handler（直接转发到 store） ────────────────────────

    def _handle_framework_init(self, event: Any) -> None:
        self._store.on_framework_init(event)

    def _handle_run_start(self, event: Any) -> None:
        self._store.on_run_start(event)

    def _handle_run_meta(self, event: Any) -> None:
        self._store.on_run_meta(event)

    def _handle_run_end(self, event: Any) -> None:
        self._store.on_run_end(event)
        self._flush(event)

    def _handle_suite_start(self, event: Any) -> None:
        self._store.on_suite_start(event)

    def _handle_suite_end(self, event: Any) -> None:
        self._store.on_suite_end(event)

    def _handle_scenario_start(self, event: Any) -> None:
        self._store.on_scenario_start(event)

    def _handle_scenario_end(self, event: Any) -> None:
        self._store.on_scenario_end(event)

    def _handle_step_start(self, event: Any) -> None:
        self._store.on_step_start(event)

    def _handle_step_end(self, event: Any) -> None:
        self._store.on_step_end(event)

    def _handle_step_failed(self, event: Any) -> None:
        self._store.on_step_failed(event)

    def _handle_http_request(self, event: Any) -> None:
        self._store.on_http_request(event)

    def _handle_http_response(self, event: Any) -> None:
        self._store.on_http_response(event)

    def _handle_variable_promoted(self, event: Any) -> None:
        self._store.on_variable_promoted(event)

    # ── 落盘 ────────────────────────────────────────────────

    def _flush(self, _event: Any) -> None:
        # ctx 可能为 None（仅当手工单测时未调 activate）。框架路径必非 None。
        if self.ctx is None:
            logger.debug("[TestReportPlugin] flush skipped: ctx is None")
            return

        report = self._store.snapshot()
        if report is None:
            logger.warning(
                "[TestReportPlugin] flush skipped: no run captured "
                "(run.start not seen before run.end?)"
            )
            return

        cfg = self.ctx.config or {}
        output_path_str = str(cfg.get("output_path") or "./reports/test-report.html")
        title = str(cfg.get("title") or "Gimbal Test Report")
        include_passed = bool(cfg.get("include_passed", True))
        include_http_body = bool(cfg.get("include_http_body", False))
        max_body_chars = int(cfg.get("max_body_chars", 4096) or 4096)

        try:
            output_path = Path(output_path_str)
            paths: List[Path] = self._renderer.render(
                report,
                output_path,
                title=title,
                include_passed=include_passed,
                include_http_body=include_http_body,
                max_body_chars=max_body_chars,
            )
            logger.info(
                "[TestReportPlugin] report emitted: run_id=%s files=%s",
                report.run_id,
                [str(p) for p in paths],
            )
        except Exception as e:  # noqa: BLE001 — fail-safe: 报告失败不影响 framework
            logger.exception("[TestReportPlugin] flush failed: %s", e)
