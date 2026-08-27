"""v2 全量信息测试 —— 覆盖 14 个 handler、suite/loose 兼容、HTTP exchanges、
variable promotions、step.failed 与 failure block 的渲染。

放在独立文件是为了和 v1 测试分开，v1 还在用 report.scenarios[...] 直接构造。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "plugins"))

import pytest

from gimbal.core.plugin import PluginContext
from gimbal.core.hooks import HookRegistry
from gimbal.events import InMemoryEventBus
from gimbal.events.types import (
    FrameworkInitEvent,
    RunStartEvent, RunMetaEvent, RunEndEvent,
    SuiteStartEvent, SuiteEndEvent,
    ScenarioStartEvent, ScenarioEndEvent,
    StepStartEvent, StepEndEvent, StepFailedEvent,
    HttpRequestEvent, HttpResponseEvent,
    VariablePromotedEvent,
)

from test_report.plugin import ReportPlugin
from test_report.renderers import HtmlRenderer
from test_report.store import ReportStore


# ── helpers ──

def _make_ctx(bus, config=None) -> PluginContext:
    return PluginContext(
        plugin_name="gimbal-test-report",
        config=config or {},
        event_bus=bus,
        hook_registry=HookRegistry(),
    )


def _ts() -> datetime:
    return datetime(2026, 7, 16, 13, 0, 0, tzinfo=timezone.utc)


# ── 1) Store: 14 handler 各自的工作流 ──

class TestStoreV2:
    def test_framework_init_populates_version(self):
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="dev", mode="local",
                                     timestamp=_ts()))
        # run.start 时 framework.init 还没来，version 应空
        assert s.snapshot().framework_version == ""
        # 模拟 framework.init 在 run.start 之后才到
        s.on_framework_init(FrameworkInitEvent(
            framework_version="2.5.0", timestamp=_ts(),
        ))
        assert s.snapshot().framework_version == "2.5.0"

    def test_suite_groups_scenarios(self):
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="", mode="",
                                     timestamp=_ts()))
        s.on_suite_start(SuiteStartEvent(
            run_id="r1", suite_id="sA", suite_name="Suite A", timestamp=_ts(),
        ))
        s.on_scenario_start(ScenarioStartEvent(
            run_id="r1", suite_id="sA", scenario_id="sc1",
            scenario_name="in suite", step_count=1, timestamp=_ts(),
        ))
        snap = s.snapshot()
        # 进了 suite.scenarios，不是 loose
        assert "sc1" in snap.suites["sA"].scenarios
        assert "sc1" not in snap._loose_scenarios

    def test_loose_scenario_when_no_suite(self):
        """没收到 suite.start 时，scenario 进 _loose_scenarios。"""
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="", mode=""))
        s.on_scenario_start(ScenarioStartEvent(
            run_id="r1", suite_id="", scenario_id="loose1",
            scenario_name="no suite", step_count=1,
        ))
        snap = s.snapshot()
        assert "loose1" in snap._loose_scenarios
        assert not snap.suites

    def test_step_failed_sets_phase_and_error(self):
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="", mode=""))
        s.on_scenario_start(ScenarioStartEvent(
            run_id="r1", suite_id="", scenario_id="sc",
            scenario_name="x", step_count=1,
        ))
        s.on_step_start(StepStartEvent(
            run_id="r1", scenario_id="sc", step_id="s1",
            step_name="will fail", strategy_kind="http",
            description="GET /health",
        ))
        # 注意：StepFailedEvent 没有 scenario_id / run_id 字段，
        # 它的 step_id 在 framework 内与最近的 step 关联。
        s.on_step_failed(StepFailedEvent(
            step_id="s1", error="connection refused", phase="http_call",
        ))
        # store 自身在 on_step_failed 里 fallback 用全局 step 查找
        snap = s.snapshot()
        st = snap._loose_scenarios["sc"].steps["s1"]
        assert st.phase == "http_call"
        assert st.error_brief == "connection refused"
        assert st.strategy_kind == "http"
        assert st.description == "GET /health"

    def test_http_request_then_response_merges_into_step(self):
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="", mode=""))
        s.on_scenario_start(ScenarioStartEvent(
            run_id="r1", suite_id="", scenario_id="sc",
            scenario_name="x", step_count=1,
        ))
        s.on_step_start(StepStartEvent(
            run_id="r1", scenario_id="sc", step_id="s1", step_name="GET /x",
        ))
        s.on_http_request(HttpRequestEvent(
            run_id="r1", step_id="s1", method="GET", url="http://x/y",
            request_headers={"X-A": "1"},
            request_body={"q": 1},
        ))
        s.on_http_response(HttpResponseEvent(
            run_id="r1", step_id="s1", method="GET", url="http://x/y",
            status_code=200, duration_ms=42.5,
            response_body={"ok": True},
        ))
        snap = s.snapshot()
        ex = snap._loose_scenarios["sc"].steps["s1"].http_exchanges
        assert len(ex) == 1
        assert ex[0].request_method == "GET"
        assert ex[0].status_code == 200
        assert ex[0].duration_ms == 42.5
        assert ex[0].response_body == {"ok": True}

    def test_http_response_without_request_creates_placeholder(self):
        """罕见情况：response 先到 → 占位 exchange 也要被填充。"""
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="", mode=""))
        s.on_scenario_start(ScenarioStartEvent(
            run_id="r1", suite_id="", scenario_id="sc",
            scenario_name="x", step_count=1,
        ))
        s.on_step_start(StepStartEvent(
            run_id="r1", scenario_id="sc", step_id="s1", step_name="x",
        ))
        s.on_http_response(HttpResponseEvent(
            run_id="r1", step_id="s1", method="GET", url="u",
            status_code=500, duration_ms=1.0,
        ))
        ex = s.snapshot()._loose_scenarios["sc"].steps["s1"].http_exchanges
        assert len(ex) == 1
        assert ex[0].status_code == 500

    def test_variable_promoted_attaches_to_step(self):
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="", mode=""))
        s.on_scenario_start(ScenarioStartEvent(
            run_id="r1", suite_id="", scenario_id="sc",
            scenario_name="x", step_count=1,
        ))
        s.on_step_start(StepStartEvent(
            run_id="r1", scenario_id="sc", step_id="s1", step_name="x",
        ))
        s.on_variable_promoted(VariablePromotedEvent(
            run_id="r1", key="token", from_layer="step",
            to_layer="scenario", by_step_id="s1",
            by_scenario_id="sc", overwrote_previous=True,
            reason="auth header",
        ))
        st = s.snapshot()._loose_scenarios["sc"].steps["s1"]
        assert len(st.promotions) == 1
        assert st.promotions[0].key == "token"
        assert st.promotions[0].overwrote_previous is True
        assert st.promotions[0].reason == "auth header"

    def test_run_meta_merges_into_run(self):
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="", mode=""))
        s.on_run_meta(RunMetaEvent(
            run_id="r1", meta={"git_sha": "abc123", "trigger": "ci"},
        ))
        s.on_run_meta(RunMetaEvent(
            run_id="r1", meta={"git_sha": "def456"},
        ))
        snap = s.snapshot()
        # 后到的覆盖先到的（同一 key）
        assert snap.meta["git_sha"] == "def456"
        assert snap.meta["trigger"] == "ci"

    def test_scenario_end_re_attaches_to_suite(self):
        """scenario.start 时 suite_id 为空，scenario.end 时带了 → 应迁移。"""
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="", mode=""))
        s.on_suite_start(SuiteStartEvent(
            run_id="r1", suite_id="sA", suite_name="Suite A",
        ))
        s.on_scenario_start(ScenarioStartEvent(
            run_id="r1", suite_id="", scenario_id="sc",
            scenario_name="x", step_count=1,
        ))
        # 此时应在 loose
        assert "sc" in s.snapshot()._loose_scenarios
        # end 时带 suite_id → 迁移到 suite 下
        s.on_scenario_end(ScenarioEndEvent(
            run_id="r1", suite_id="sA", scenario_id="sc",
            status="passed", step_count=1,
        ))
        snap = s.snapshot()
        assert "sc" in snap.suites["sA"].scenarios
        assert "sc" not in snap._loose_scenarios


# ── 2) Renderer v2 sections ──

class TestRendererV2:
    def _full_report(self):
        """构造一个包含 suite + loose + http + promotion + failure 的报告。"""
        from test_report.report_data import (
            RunReport, ScenarioReport, StepReport, SuiteReport,
            HttpExchange, VariablePromotion,
        )
        run = RunReport(
            run_id="r-v2", env="prod", mode="ci",
            framework_version="2.5.0",
            started_at="t1", ended_at="t2",
            total=2, passed=1, failed=1, error=0, skipped=0,
            meta={"git_sha": "abc", "trigger": "ci"},
        )
        su = SuiteReport(
            suite_id="sA", suite_name="Login Suite",
            status="failed", started_at="t1", ended_at="t2",
        )
        sc = ScenarioReport(
            scenario_id="sc1", scenario_name="login flow",
            status="failed", started_at="t1", ended_at="t2",
            suite_id="sA",
            meta={"tags": ["smoke"], "priority": "P1"},
        )
        st_ok = StepReport(
            step_id="s_ok", step_name="GET /health",
            status="passed", duration_ms=42,
            strategy_kind="http", description="health check",
            assertion_count=1, assertion_passed=1,
        )
        st_ok.http_exchanges.append(HttpExchange(
            request_method="GET", request_url="http://api/health",
            request_headers={"X-T": "v"},
            status_code=200, duration_ms=42,
            response_body={"status": "ok"},
        ))
        st_ok.promotions.append(VariablePromotion(
            key="token", from_layer="step", to_layer="scenario",
            by_step_id="s_ok", by_scenario_id="sc1",
            overwrote_previous=False, reason="cached token",
        ))
        sc.steps["s_ok"] = st_ok

        st_fail = StepReport(
            step_id="s_fail", step_name="POST /login",
            status="failed", duration_ms=200,
            strategy_kind="http",
            error_brief="expected 200 got 401",
            phase="http_call",
        )
        st_fail.http_exchanges.append(HttpExchange(
            request_method="POST", request_url="http://api/login",
            request_body={"user": "x"},
            status_code=401, duration_ms=200,
        ))
        sc.steps["s_fail"] = st_fail
        su.scenarios["sc1"] = sc
        run.suites["sA"] = su

        # 一个 loose scenario（没 suite）
        loose_sc = ScenarioReport(
            scenario_id="lsc", scenario_name="standalone",
            status="passed", started_at="t1", ended_at="t2",
        )
        loose_sc.steps["ls1"] = StepReport(
            step_id="ls1", step_name="quick check",
            status="passed", duration_ms=5,
        )
        run._loose_scenarios["lsc"] = loose_sc
        return run

    def test_html_contains_framework_version(self, tmp_path):
        out = tmp_path / "r.html"
        HtmlRenderer().render(self._full_report(), out)
        text = out.read_text(encoding="utf-8")
        assert "framework: 2.5.0" in text

    def test_html_contains_run_meta_table(self, tmp_path):
        out = tmp_path / "r.html"
        HtmlRenderer().render(self._full_report(), out)
        text = out.read_text(encoding="utf-8")
        assert "Run meta" in text
        assert "git_sha" in text
        assert "abc" in text
        assert "trigger" in text

    def test_html_groups_suites(self, tmp_path):
        out = tmp_path / "r.html"
        HtmlRenderer().render(self._full_report(), out)
        text = out.read_text(encoding="utf-8")
        assert "Suites" in text
        assert "Login Suite" in text
        assert "sA" in text

    def test_html_shows_loose_scenarios_separately(self, tmp_path):
        out = tmp_path / "r.html"
        HtmlRenderer().render(self._full_report(), out)
        text = out.read_text(encoding="utf-8")
        assert "Scenarios (no suite)" in text
        assert "standalone" in text

    def test_html_renders_http_exchanges_subtable(self, tmp_path):
        out = tmp_path / "r.html"
        HtmlRenderer().render(self._full_report(), out)
        text = out.read_text(encoding="utf-8")
        assert "HTTP exchanges (1)" in text
        assert "http://api/health" in text
        assert "http://api/login" in text

    def test_html_renders_variable_promotion_subtable(self, tmp_path):
        out = tmp_path / "r.html"
        HtmlRenderer().render(self._full_report(), out)
        text = out.read_text(encoding="utf-8")
        assert "Variable promotions (1)" in text
        assert "token" in text
        assert "step → scenario" in text

    def test_html_renders_failure_block_with_phase(self, tmp_path):
        out = tmp_path / "r.html"
        HtmlRenderer().render(self._full_report(), out)
        text = out.read_text(encoding="utf-8")
        assert "phase: http_call" in text
        assert "expected 200 got 401" in text
        # v3：failure 用 .failure-section class（红色背景，与其他 section 区分）
        assert 'class="step-section failure-section"' in text

    def test_html_step_card_layout(self, tmp_path):
        """v3：每个 step 渲染成一张完整卡片（step-card），各 section 用 divider 隔开。"""
        out = tmp_path / "r.html"
        HtmlRenderer().render(self._full_report(), out)
        text = out.read_text(encoding="utf-8")
        # step-card 包装器
        assert '<div class="step-card">' in text
        # 头部：name + status badge + duration
        assert '<div class="step-header">' in text
        assert '<div class="step-name">' in text
        assert '<div class="step-status">' in text
        assert '<div class="step-duration">' in text
        # 各 section 用 .step-section 包裹
        assert text.count('class="step-section') >= 3
        # 老的 table-row 风格不复存在
        assert '<th>Step</th><th>Status</th>' not in text
        assert '<th class="duration">Duration</th><th>Detail</th>' not in text

    def test_html_includes_http_body_only_when_enabled(self, tmp_path):
        out = tmp_path / "r.html"
        # 默认 include_http_body=False → body 不出现
        HtmlRenderer().render(self._full_report(), out)
        text = out.read_text(encoding="utf-8")
        assert "Request #1 body" not in text
        # 启用后 → body 出现
        out2 = tmp_path / "r2.html"
        HtmlRenderer().render(self._full_report(), out2, include_http_body=True)
        text2 = out2.read_text(encoding="utf-8")
        assert "Request #1 body" in text2
        assert "Response #1 body" in text2

    def test_html_summary_cards_include_http_and_promotions(self, tmp_path):
        out = tmp_path / "r.html"
        HtmlRenderer().render(self._full_report(), out)
        text = out.read_text(encoding="utf-8")
        assert ">2<" in text      # HTTP total = 2
        assert ">1<" in text      # PROMOTIONS = 1


# ── 3) Plugin 端到端：完整 v2 事件流 → 落盘 HTML 含全部段落 ──

class TestPluginV2EndToEnd:
    def test_full_event_stream_produces_full_html(self, tmp_path):
        out = tmp_path / "v2-report.html"
        bus = InMemoryEventBus()
        plugin = ReportPlugin()
        plugin.load()
        ctx = _make_ctx(bus, {
            "output_path": str(out),
            "title": "v2 Demo",
            "include_passed": True,
            "include_http_body": True,
            "max_body_chars": 200,
        })
        plugin.activate(ctx)

        bus.publish(FrameworkInitEvent(
            framework_version="2.5.0", timestamp=_ts(),
        ))
        bus.publish(RunMetaEvent(
            run_id="rv2", meta={"git_sha": "deadbeef"},
        ))
        bus.publish(RunStartEvent(
            run_id="rv2", env="dev", mode="local", timestamp=_ts(),
        ))
        bus.publish(SuiteStartEvent(
            run_id="rv2", suite_id="sA", suite_name="Auth Suite",
            timestamp=_ts(),
        ))
        bus.publish(ScenarioStartEvent(
            run_id="rv2", suite_id="sA", scenario_id="sc1",
            scenario_name="login", step_count=2, timestamp=_ts(),
        ))
        bus.publish(StepStartEvent(
            run_id="rv2", scenario_id="sc1", step_id="s1",
            step_name="GET /health", strategy_kind="http",
            description="smoke check", timestamp=_ts(),
        ))
        bus.publish(HttpRequestEvent(
            run_id="rv2", step_id="s1", method="GET",
            url="http://api/health", request_headers={"X-T": "v"},
            request_body={"probe": 1},
        ))
        bus.publish(HttpResponseEvent(
            run_id="rv2", step_id="s1", method="GET",
            url="http://api/health", status_code=200, duration_ms=12.0,
            response_body={"status": "ok"},
        ))
        bus.publish(StepEndEvent(
            run_id="rv2", scenario_id="sc1", step_id="s1",
            status="passed", duration_ms=12,
            assertion_count=1, assertion_passed=1, promotion_count=1,
            timestamp=_ts(),
        ))
        bus.publish(VariablePromotedEvent(
            run_id="rv2", key="token", from_layer="step",
            to_layer="scenario", by_step_id="s1",
            by_scenario_id="sc1", overwrote_previous=False,
            reason="cached",
        ))
        bus.publish(StepStartEvent(
            run_id="rv2", scenario_id="sc1", step_id="s2",
            step_name="POST /login", strategy_kind="http", timestamp=_ts(),
        ))
        bus.publish(HttpRequestEvent(
            run_id="rv2", step_id="s2", method="POST",
            url="http://api/login", request_body={"user": "x"},
        ))
        bus.publish(HttpResponseEvent(
            run_id="rv2", step_id="s2", method="POST",
            url="http://api/login", status_code=401, duration_ms=50.0,
            response_body={"error": "unauthorized"},
        ))
        bus.publish(StepFailedEvent(
            step_id="s2", error="auth failed", phase="http_call",
        ))
        bus.publish(StepEndEvent(
            run_id="rv2", scenario_id="sc1", step_id="s2",
            status="failed", duration_ms=50, error_brief="auth failed",
            timestamp=_ts(),
        ))
        bus.publish(ScenarioEndEvent(
            run_id="rv2", suite_id="sA", scenario_id="sc1",
            status="failed", step_count=2,
            meta={"tags": ["smoke"], "priority": "P1"},
            timestamp=_ts(),
        ))
        bus.publish(SuiteEndEvent(
            run_id="rv2", suite_id="sA", status="failed", timestamp=_ts(),
        ))
        bus.publish(RunEndEvent(
            run_id="rv2", total=2, passed=1, failed=1, error=0,
            timestamp=_ts(),
        ))

        plugin.deactivate()
        bus.stop()

        assert out.exists()
        text = out.read_text(encoding="utf-8")

        # 头部
        assert "<title>v2 Demo</title>" in text
        assert "framework: 2.5.0" in text
        assert "git_sha" in text
        assert "deadbeef" in text

        # Suite 分组
        assert "Auth Suite" in text
        assert "sA" in text
        # Scenario meta
        assert "tags" in text and "smoke" in text
        # Step 内容
        assert "GET /health" in text
        assert "POST /login" in text
        assert "smoke check" in text   # description
        # HTTP exchanges
        assert "http://api/health" in text
        assert "http://api/login" in text
        # body (include_http_body=True)
        assert "Request #1 body" in text
        assert "Response #1 body" in text
        assert "probe" in text
        # promotion
        assert "Variable promotions (1)" in text
        assert "token" in text
        # failure block
        assert "phase: http_call" in text
        assert "auth failed" in text
        # summary 卡片
        assert ">1<" in text  # passed=1 / failed=1


# ── 4) 策略信息（strategy_kind / strategy_spec / retry_count） ──

class TestStrategyInfo:
    """v2 补全：把 StepInputs.strategy_spec 和 StepOutcome.retry_count
    通过 StepStartEvent / StepEndEvent 投影到报告，让用户能在 HTML 里
    看到每个 step 实际配置的策略参数和重试次数。
    """

    def test_store_captures_strategy_spec_from_step_start(self):
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="", mode=""))
        s.on_scenario_start(ScenarioStartEvent(
            run_id="r1", suite_id="", scenario_id="sc",
            scenario_name="x", step_count=1,
        ))
        spec = {
            "type": "http",
            "request": {"method": "POST", "url": "http://api/x"},
            "assertions": [
                {"path": "$.code", "op": "eq", "expected": 0},
                {"path": "$.msg", "op": "contains", "expected": "ok"},
            ],
            "extract": {"order_id": "$.data.id"},
            "retry": {"max_attempts": 3, "backoff": "exponential"},
        }
        s.on_step_start(StepStartEvent(
            run_id="r1", scenario_id="sc", step_id="s1",
            step_name="create order", strategy_kind="http",
            strategy_spec=spec,
        ))
        snap = s.snapshot()
        st = snap._loose_scenarios["sc"].steps["s1"]
        assert st.strategy_kind == "http"
        assert st.strategy_spec["type"] == "http"
        # 嵌套 assertions / extract / retry 都完整保存
        assert len(st.strategy_spec["assertions"]) == 2
        assert st.strategy_spec["extract"]["order_id"] == "$.data.id"
        assert st.strategy_spec["retry"]["max_attempts"] == 3

    def test_store_captures_retry_count_from_step_end(self):
        s = ReportStore()
        s.on_run_start(RunStartEvent(run_id="r1", env="", mode=""))
        s.on_scenario_start(ScenarioStartEvent(
            run_id="r1", suite_id="", scenario_id="sc",
            scenario_name="x", step_count=1,
        ))
        s.on_step_start(StepStartEvent(
            run_id="r1", scenario_id="sc", step_id="s1",
            step_name="flaky", strategy_kind="http",
        ))
        s.on_step_end(StepEndEvent(
            run_id="r1", scenario_id="sc", step_id="s1",
            status="passed", duration_ms=300, retry_count=2,
        ))
        st = s.snapshot()._loose_scenarios["sc"].steps["s1"]
        assert st.retry_count == 2

    def test_html_renders_strategy_block_with_spec(self, tmp_path):
        from test_report.report_data import (
            RunReport, ScenarioReport, StepReport,
        )
        run = RunReport(run_id="r1", env="dev", mode="ci")
        sc = ScenarioReport(scenario_id="sc", scenario_name="x")
        sc.steps["s1"] = StepReport(
            step_id="s1", step_name="create order",
            status="passed", duration_ms=120,
            strategy_kind="http",
            strategy_spec={
                "type": "http",
                "request": {"method": "POST", "url": "http://api/order"},
                "assertions": [
                    {"path": "$.code", "op": "eq", "expected": 0},
                ],
                "extract": {"order_id": "$.data.id"},
            },
            retry_count=2,
        )
        run._loose_scenarios["sc"] = sc

        out = tmp_path / "r.html"
        HtmlRenderer().render(run, out)
        text = out.read_text(encoding="utf-8")

        # v3：每个 step 是一张 step-card，strategy 是其中一个 section。
        # step-card 用 div 包裹，section 之间用 border divider 隔开。
        assert '<div class="step-card">' in text
        assert '<div class="step-section">' in text
        # strategy 内容用 <details>/<summary> + class="subtable"
        assert '<summary style="font-weight:500">Strategy' in text
        assert '<table class="subtable">' in text
        # summary 包含 kind + retry
        assert ">Strategy · http · ⚡ 2 retries</summary>" in text
        # spec 的 KV 都展开
        assert "method" in text
        assert "POST" in text
        assert "http://api/order" in text
        assert "order_id" in text
        assert "$.data.id" in text
        assert "path" in text
        assert "assertions" in text

    def test_html_splits_step_config_and_individual_strategies(self, tmp_path):
        """v4：strategy_spec['strategy'] 列表里的每个策略要单独成 section。

        这是用户提出的核心需求：step 配置（api / request body）和具体策略
        （assertion / extract / verify）不能再混在一个折叠块里。
        """
        from test_report.report_data import (
            RunReport, ScenarioReport, StepReport,
        )
        run = RunReport(run_id="r1", env="dev", mode="ci")
        sc = ScenarioReport(scenario_id="sc", scenario_name="x")
        sc.steps["s1"] = StepReport(
            step_id="s1", step_name="create order",
            status="passed", duration_ms=120,
            strategy_kind="multi",
            strategy_spec={
                "kind": "step",
                "description": "create an order via api",
                "api": {
                    "kind": "api",
                    "method": "POST",
                    "path": "/api/order",
                    "headers": {"Authorization": "Bearer xxx"},
                    "request": {
                        "kind": "request",
                        "body": {"product": "A", "qty": 3},
                    },
                },
                "strategy": [
                    {
                        "name": "assert_http_status_eq_200",
                        "phase": "StrategyPhase.VERIFYING",
                        "kind": "assertion",
                        "target": "$.response_status",
                        "operator": "AssertOperator.EQ",
                        "expected": 200,
                        "onFailure": "FailurePolicy.ABORT",
                    },
                    {
                        "name": "extract_order_id",
                        "phase": "StrategyPhase.EXTRACTING",
                        "kind": "extract",
                        "target": "$.data.id",
                        "variable": "order_id",
                        "soft": True,
                    },
                ],
            },
        )
        run._loose_scenarios["sc"] = sc

        out = tmp_path / "r.html"
        HtmlRenderer().render(run, out)
        text = out.read_text(encoding="utf-8")

        # ── Step config section 存在 ──
        # 它的 summary 里要带 strategy 计数（让用户知道下方还有 2 个独立 strategy）
        assert ">Strategy · multi · 2 strategies</summary>" in text
        # Step config section 仍然包含 api / method / path / request body
        assert "method" in text
        assert "POST" in text
        assert "/api/order" in text
        assert "product" in text

        # ── 每个 strategy 一张独立的折叠 section ──
        # 用 strategy 的 name 字段作 summary
        assert ">Strategy · assert_http_status_eq_200" in text
        assert ">Strategy · extract_order_id" in text

        # 每个 strategy section 内有自己的 subtable，展示具体断言/提取参数
        assert "$.response_status" in text
        assert "AssertOperator.EQ" in text
        assert "$.data.id" in text
        assert "order_id" in text

        # ── 关键约束：step config section 不应再包含 strategy 列表本身 ──
        # 把 step config 这块单独抠出来再检查 —— 它不应该含 "assert_http_status_eq_200"
        # （那是 strategy section 的内容）
        cfg_start = text.index('>Strategy · multi · 2 strategies</summary>')
        # 找下一个 "Strategy · " —— step config 后第一个出现的应该是某个 strategy
        next_strategy_idx = text.find(
            '>Strategy · assert_http_status_eq_200', cfg_start,
        )
        cfg_block = text[cfg_start:next_strategy_idx]
        # Step config 里不应有 strategy.name / target 等 strategy 专属字段
        assert "assert_http_status_eq_200" not in cfg_block
        assert "extract_order_id" not in cfg_block
        assert "AssertOperator" not in cfg_block
        # 但 api 内容应有
        assert "method" in cfg_block
        assert "POST" in cfg_block

    def test_html_strategy_item_summary_shows_extras(self, tmp_path):
        """v4：strategy section 的 summary 应展示 phase / soft / onFailure 等高亮字段。"""
        from test_report.report_data import (
            RunReport, ScenarioReport, StepReport,
        )
        run = RunReport(run_id="r1", env="dev", mode="ci")
        sc = ScenarioReport(scenario_id="sc", scenario_name="x")
        sc.steps["s1"] = StepReport(
            step_id="s1", step_name="x", status="passed",
            strategy_kind="multi",
            strategy_spec={
                "kind": "step",
                "strategy": [
                    {
                        "name": "assert_status_200",
                        "phase": "StrategyPhase.VERIFYING",
                        "kind": "assertion",
                        "soft": True,
                        "onFailure": "FailurePolicy.ABORT",
                    },
                ],
            },
        )
        run._loose_scenarios["sc"] = sc
        out = tmp_path / "r.html"
        HtmlRenderer().render(run, out)
        text = out.read_text(encoding="utf-8")
        # summary 内含 phase + soft + onFailure
        assert "phase: StrategyPhase.VERIFYING" in text
        assert "soft" in text
        assert "onFailure: FailurePolicy.ABORT" in text

    def test_html_renders_strategy_block_when_only_kind(self, tmp_path):
        """spec 为空但 kind 非空 → 也展示 strategy 块。"""
        from test_report.report_data import (
            RunReport, ScenarioReport, StepReport,
        )
        run = RunReport(run_id="r1", env="dev", mode="ci")
        sc = ScenarioReport(scenario_id="sc", scenario_name="x")
        sc.steps["s1"] = StepReport(
            step_id="s1", step_name="x",
            status="passed", duration_ms=10,
            strategy_kind="smoke",
        )
        run._loose_scenarios["sc"] = sc
        out = tmp_path / "r.html"
        HtmlRenderer().render(run, out)
        text = out.read_text(encoding="utf-8")
        # v3：strategy 是 step-card 内一个 section。
        assert '<div class="step-section">' in text
        # 跟 HTTP/promotion 块同样结构：<details>/<summary>
        assert "<summary style=\"font-weight:500\">Strategy · smoke</summary>" in text
        # 没有 retry 也没有 spec → strategy 块依然渲染
        assert "<summary style=\"font-weight:500\">Strategy" in text

    def test_html_omits_strategy_block_when_no_strategy(self, tmp_path):
        """旧 statemachine 发的 step 没 strategy_kind / strategy_spec → 不渲染。"""
        from test_report.report_data import (
            RunReport, ScenarioReport, StepReport,
        )
        run = RunReport(run_id="r1", env="dev", mode="ci")
        sc = ScenarioReport(scenario_id="sc", scenario_name="x")
        sc.steps["s1"] = StepReport(
            step_id="s1", step_name="x",
            status="passed", duration_ms=10,
            # strategy_kind / strategy_spec 都默认空
        )
        run._loose_scenarios["sc"] = sc
        out = tmp_path / "r.html"
        HtmlRenderer().render(run, out)
        text = out.read_text(encoding="utf-8")
        # 没有 strategy 信息 → <details style="margin:6px 0"> 这个通用 wrapper
        # 也不应出现在 step detail 中。
        # 注：HTML 中可能还有其它详情块（如 failure / http / promotion），
        # 但本测试 step 没这些也不会有。
        assert '<summary style="font-weight:500">Strategy' not in text

    def test_strategy_spec_xss_escape(self, tmp_path):
        """strategy_spec 里的值要 HTML 转义。"""
        from test_report.report_data import (
            RunReport, ScenarioReport, StepReport,
        )
        run = RunReport(run_id="r1", env="dev", mode="ci")
        sc = ScenarioReport(scenario_id="sc", scenario_name="x")
        sc.steps["s1"] = StepReport(
            step_id="s1", step_name="x",
            status="passed", strategy_kind="x",
            strategy_spec={"url": "http://x/<script>alert(1)</script>"},
        )
        run._loose_scenarios["sc"] = sc
        out = tmp_path / "r.html"
        HtmlRenderer().render(run, out)
        text = out.read_text(encoding="utf-8")
        # 原样字符串不应出现；转义后的应出现
        assert "<script>alert(1)</script>" not in text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text