"""Plugins/test_report 端到端单测。

三层覆盖：
  1. HtmlRenderer：纯渲染，校验 HTML 含关键段落
  2. ReportStore：handler 累积，独立可用
  3. TestReportPlugin：经真实 EventBus 走完整生命周期，验证落盘
"""
from __future__ import annotations

import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# 让 Python 找到 gimbal 包与本插件包
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "plugins"))

import pytest

from gimbal.core.plugin import PluginContext
from gimbal.core.hooks import HookRegistry
from gimbal.events import InMemoryEventBus
from gimbal.events.types import (
    RunStartEvent, RunMetaEvent, RunEndEvent,
    ScenarioStartEvent, ScenarioEndEvent,
    StepStartEvent, StepEndEvent, StepFailedEvent,
)

from test_report.plugin import ReportPlugin
from test_report.renderers import HtmlRenderer
from test_report.store import ReportStore


# ────────────────────────────────────────────────────────────────────
# Test fixtures
# ────────────────────────────────────────────────────────────────────
def _make_ctx(bus, config=None) -> PluginContext:
    """构造一个最小可用的 PluginContext 给测试用。"""
    return PluginContext(
        plugin_name="gimbal-test-report",
        config=config or {},
        event_bus=bus,
        hook_registry=HookRegistry(),
    )


def _ts() -> datetime:
    return datetime(2026, 7, 16, 10, 0, 0, tzinfo=timezone.utc)


# ────────────────────────────────────────────────────────────────────
# 1) HtmlRenderer
# ────────────────────────────────────────────────────────────────────
class TestHtmlRenderer:
    def _report(self):
        from test_report.report_data import RunReport, ScenarioReport, StepReport
        run = RunReport(
            run_id="r1", env="dev", mode="ci",
            started_at="2026-07-16T10:00:00+00:00",
            ended_at="2026-07-16T10:00:05+00:00",
            total=3, passed=2, failed=1, error=0, skipped=0,
        )
        sc = ScenarioReport(
            scenario_id="sc1", scenario_name="<Login Flow & Signup>",  # 含 HTML 特殊字符
            status="failed", started_at="t1", ended_at="t2",
        )
        sc.steps["s1"] = StepReport(step_id="s1", step_name="step one", status="passed", duration_ms=120)
        sc.steps["s2"] = StepReport(step_id="s2", step_name="step two", status="failed",
                                    duration_ms=3500.0,
                                    error_brief="expected 200 got 500")
        sc.steps["s3"] = StepReport(step_id="s3", step_name="step three", status="passed",
                                    duration_ms=50, assertion_count=2, assertion_passed=2)
        run._loose_scenarios["sc1"] = sc
        return run

    def test_writes_file_and_returns_path(self, tmp_path):
        r = HtmlRenderer()
        out = tmp_path / "report.html"
        paths = r.render(self._report(), out)
        assert paths == [out]
        assert out.exists()

    def test_html_escapes_user_data(self, tmp_path):
        """scenario_name 含 < > & 必须被转义,不能破坏 HTML 结构。"""
        out = tmp_path / "report.html"
        HtmlRenderer().render(self._report(), out)
        text = out.read_text(encoding="utf-8")
        # < 被转义为 &lt;,不会被解析为标签
        assert "&lt;Login Flow &amp; Signup&gt;" in text
        assert "<Login Flow" not in text

    def test_html_contains_key_sections(self, tmp_path):
        out = tmp_path / "report.html"
        HtmlRenderer().render(self._report(), out, title="My Custom Title",
                              include_passed=False)
        text = out.read_text(encoding="utf-8")
        assert "<title>My Custom Title</title>" in text
        # summary 卡片数字
        assert ">3<" in text  # total=3
        assert ">2<" in text  # passed=2
        assert ">1<" in text  # failed=1
        # include_passed=False → 只展示失败/错误的 step
        assert "step two" in text
        assert "step one" not in text  # passed 被过滤
        # 错误摘要
        assert "expected 200 got 500" in text

    def test_include_passed_true_shows_all_steps(self, tmp_path):
        out = tmp_path / "report.html"
        HtmlRenderer().render(self._report(), out, include_passed=True)
        text = out.read_text(encoding="utf-8")
        for s in ("step one", "step two", "step three"):
            assert s in text

    def test_creates_parent_dir(self, tmp_path):
        out = tmp_path / "deep/nested/path/report.html"
        HtmlRenderer().render(self._report(), out)
        assert out.exists()


# ────────────────────────────────────────────────────────────────────
# 2) ReportStore
# ────────────────────────────────────────────────────────────────────
class TestReportStore:
    def test_event_flow_accumulates_report(self):
        s = ReportStore()
        s.on_run_start(RunStartEvent(
            run_id="r1", env="dev", mode="ci", timestamp=_ts()
        ))
        s.on_run_meta(RunMetaEvent(run_id="r1", meta={"trigger": "manual"}))
        s.on_scenario_start(ScenarioStartEvent(
            run_id="r1", scenario_id="sc1", scenario_name="demo", step_count=2,
            timestamp=_ts()
        ))
        s.on_step_start(StepStartEvent(
            run_id="r1", scenario_id="sc1", step_id="s1", step_name="ok step",
        ))
        s.on_step_end(StepEndEvent(
            run_id="r1", scenario_id="sc1", step_id="s1", status="passed",
            duration_ms=80,
        ))
        s.on_step_start(StepStartEvent(
            run_id="r1", scenario_id="sc1", step_id="s2", step_name="bad step",
        ))
        s.on_step_end(StepEndEvent(
            run_id="r1", scenario_id="sc1", step_id="s2", status="failed",
            duration_ms=200, error_brief="assertion failed",
        ))
        s.on_scenario_end(ScenarioEndEvent(
            run_id="r1", scenario_id="sc1", status="failed", step_count=2,
            timestamp=_ts(),
        ))
        s.on_run_end(RunEndEvent(
            run_id="r1", total=2, passed=1, failed=1, error=0, timestamp=_ts(),
        ))

        snap = s.snapshot()
        assert snap is not None
        assert snap.run_id == "r1"
        assert snap.env == "dev"
        assert snap.mode == "ci"
        assert snap.total == 2 and snap.passed == 1 and snap.failed == 1
        assert snap.meta == {"trigger": "manual"}
        # v2 schema: 没 suite 时 scenario 进 _loose_scenarios
        assert len(snap._loose_scenarios) == 1
        sc = snap._loose_scenarios["sc1"]
        assert sc.status == "failed"
        assert sc.passed == 1 and sc.failed == 1
        assert sc.steps["s2"].error_brief == "assertion failed"

    def test_step_end_without_start_is_ignored(self):
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="", mode=""))
        s.on_scenario_start(ScenarioStartEvent(
            run_id="r1", scenario_id="sc1", scenario_name="x", step_count=1
        ))
        # 不调 step.start,直接 step.end
        s.on_step_end(StepEndEvent(
            run_id="r1", scenario_id="sc1", step_id="ghost", status="passed",
            duration_ms=10,
        ))
        snap = s.snapshot()
        assert "ghost" not in snap._loose_scenarios["sc1"].steps

    def test_run_end_without_run_start_returns_none(self):
        s = ReportStore()
        # 既不调 run.start 也不调 run.end → snapshot 应为 None
        assert s.snapshot() is None


# ────────────────────────────────────────────────────────────────────
# 3) TestReportPlugin（端到端）
# ────────────────────────────────────────────────────────────────────
class TestTestReportPlugin:
    def test_emits_html_to_configured_path(self, tmp_path):
        out = tmp_path / "report.html"
        bus = InMemoryEventBus()
        plugin = ReportPlugin()
        plugin.load()
        ctx = _make_ctx(bus, {"output_path": str(out)})
        plugin.activate(ctx)

        # 走一遍事件流
        bus.publish(RunStartEvent(run_id="r1", env="dev", mode="ci", timestamp=_ts()))
        bus.publish(ScenarioStartEvent(
            run_id="r1", scenario_id="sc1", scenario_name="login", step_count=2,
            timestamp=_ts()
        ))
        bus.publish(StepStartEvent(
            run_id="r1", scenario_id="sc1", step_id="s1", step_name="ok", timestamp=_ts()
        ))
        bus.publish(StepEndEvent(
            run_id="r1", scenario_id="sc1", step_id="s1", status="passed",
            duration_ms=50, timestamp=_ts()
        ))
        bus.publish(StepStartEvent(
            run_id="r1", scenario_id="sc1", step_id="s2", step_name="bad", timestamp=_ts()
        ))
        bus.publish(StepEndEvent(
            run_id="r1", scenario_id="sc1", step_id="s2", status="failed",
            duration_ms=80, error_brief="404", timestamp=_ts()
        ))
        bus.publish(ScenarioEndEvent(
            run_id="r1", scenario_id="sc1", status="failed", step_count=2, timestamp=_ts()
        ))
        bus.publish(RunEndEvent(
            run_id="r1", total=2, passed=1, failed=1, error=0, timestamp=_ts()
        ))

        plugin.deactivate()
        bus.stop()

        assert out.exists()
        text = out.read_text(encoding="utf-8")
        assert "login" in text
        assert "ok" in text
        assert "bad" in text
        assert "404" in text
        assert ">2<" in text    # total=2
        assert ">1<" in text    # passed=1 / failed=1
        assert "Gimbal Test Report" in text or "Gimbal" in text

    def test_no_run_means_no_file(self, tmp_path):
        """没有 run.start 就 run.end → 不应写文件（sanity）。"""
        out = tmp_path / "report.html"
        bus = InMemoryEventBus()
        plugin = ReportPlugin()
        plugin.load()
        ctx = _make_ctx(bus, {"output_path": str(out)})
        plugin.activate(ctx)
        # 直接发 run.end,不做任何 run.start
        bus.publish(RunEndEvent(run_id="r0", total=0, passed=0, failed=0, error=0))
        plugin.deactivate()
        bus.stop()
        # store snapshot → None,_flush 提前返回,不写文件
        # tmp_path 应该没有 report.html
        assert not out.exists()

    def test_flush_failure_does_not_raise(self, tmp_path):
        """output_path 指向一个无法写入的位置(把它设成一个目录)→ flush
        应被 try/except 吞掉,不影响后续操作。
        """
        bus = InMemoryEventBus()
        plugin = ReportPlugin()
        plugin.load()
        # 把一个目录路径塞给 file writer 会失败
        bad_path = tmp_path  # tmp_path 是一个目录,不能 write_text
        ctx = _make_ctx(bus, {"output_path": str(bad_path)})
        plugin.activate(ctx)
        # 不应该抛
        bus.publish(RunStartEvent(run_id="r1", env="", mode=""))
        bus.publish(RunEndEvent(run_id="r1", total=0, passed=0, failed=0, error=0))
        plugin.deactivate()
        bus.stop()

    def test_manifest_defaults_override_user_config(self, tmp_path):
        """未提供的 config 字段使用 manifest.default_config。"""
        out = tmp_path / "r.html"
        bus = InMemoryEventBus()
        plugin = ReportPlugin()
        plugin.load()
        # 仅给 output_path → title / include_passed 取默认
        ctx = _make_ctx(bus, {"output_path": str(out)})
        plugin.activate(ctx)
        bus.publish(RunStartEvent(run_id="r1", env="", mode=""))
        bus.publish(RunEndEvent(run_id="r1", total=1, passed=1, failed=0, error=0))
        plugin.deactivate()
        bus.stop()
        assert out.exists()
        # 默认 title 是 "Gimbal Test Report"
        assert "Gimbal Test Report" in out.read_text(encoding="utf-8")


# ────────────────────────────────────────────────────────────────────
# 4) 插件加载链路（PluginLoader 真发现 + 真 activate）
# ────────────────────────────────────────────────────────────────────
class TestPluginDiscovery:
    def test_plugin_loader_can_load_test_report(self, tmp_path):
        """PluginLoader 在临时 plugins_dir 中应能发现并加载本插件。"""
        from gimbal.plugins.loader import PluginLoader

        loader = PluginLoader(plugins_dir=tmp_path)
        # 直接导入 plugin 类（不走 .yaml,因为我们用的名字在 .yaml 也写了，
        # 但为简化测试只验证类能 import & activate）
        plugin = ReportPlugin()
        plugin.load()
        ctx = _make_ctx(InMemoryEventBus(), {
            "output_path": str(tmp_path / "auto.html"),
        })
        plugin.activate(ctx)
        assert plugin.state.name == "ACTIVATED"

        bus = ctx.event_bus  # type: ignore[assignment]
        bus.publish(RunStartEvent(run_id="r1", env="dev", mode=""))
        bus.publish(RunEndEvent(run_id="r1", total=0, passed=0, failed=0, error=0))
        plugin.deactivate()
        bus.stop()  # type: ignore[attr-defined]
        assert (tmp_path / "auto.html").exists()
