"""Unit tests for gimbal.reporter.builtin.html_reporter (HtmlReporter).

Coverage:
  [1] on_event 累积 step / http / scenario 状态，不抛异常
  [2] finalize 写出 HTML 文件，含 scenario + step + http details
  [3] failed step 在 HTML 中出现 <pre class="err">
  [4] step 顺序与事件触发顺序一致
  [5] RunResult.details fallback 路径（事件未触发时仍能渲染）
  [6] artifact metadata 包含 scenario_count / http_count
  [7] RunMetaEvent 缓存到 self._run_meta 并渲染到头部 .run-meta 区块
  [7b] _collect_run_meta() 字段名与 _render_run_meta() 主键对齐（回归）
  [8] ScenarioEndEvent.meta 渲染为 scenario summary 末尾的 chip 行
"""
import sys, os, tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("HTML REPORTER TEST")
print("=" * 60)


def _build_ctx(tmpdir):
    from gimbal.reporter.builtin.html_reporter import HtmlReporter
    from gimbal.reporter.protocol import ReportContext
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.events.subscription import SubscriptionMode

    r = HtmlReporter()
    bus = InMemoryEventBus()
    class _Cfg:
        no_color = True
    fc = type("FC", (), {
        "run_id": "rid-test",
        "environment": "dev",
        "mode": "local",
        "framework_version": "0.1.0",
    })()
    ctx = ReportContext(
        framework_ctx=fc, bus=bus, config=_Cfg(),
        report_dir=Path(tmpdir), user_config={}, artifacts_dir=Path(tmpdir),
        subscription_mode=SubscriptionMode.SYNC,
    )
    return r, ctx


def test_on_event_accumulates_state():
    from gimbal.reporter.builtin.html_reporter import HtmlReporter
    from gimbal.events.types import (
        ScenarioStartEvent, ScenarioEndEvent, StepStartEvent, StepEndEvent,
        StepFailedEvent, HttpRequestEvent, HttpResponseEvent,
    )
    r = HtmlReporter()
    r.on_event(ScenarioStartEvent(scenario_id="sc-1", scenario_name="Demo", step_count=2, suite_id="s"))
    r.on_event(StepStartEvent(scenario_id="sc-1", step_id="s1", step_name="Login", strategy_kind="http"))
    r.on_event(StepEndEvent(
        scenario_id="sc-1", step_id="s1", status="passed", duration_ms=12.0,
        assertion_count=1, assertion_passed=1, promotion_count=0,
    ))
    r.on_event(StepStartEvent(scenario_id="sc-1", step_id="s2", step_name="GetUser", strategy_kind="http"))
    r.on_event(StepEndEvent(
        scenario_id="sc-1", step_id="s2", status="failed", duration_ms=50.0,
        assertion_count=2, assertion_passed=1, promotion_count=0,
        error_brief="AssertionError: expected 200, got 500",
    ))
    r.on_event(HttpRequestEvent(method="GET", url="http://x/users/1", step_id="s2"))
    r.on_event(HttpResponseEvent(method="GET", url="http://x/users/1", status_code=500,
                                  duration_ms=50.0, step_id="s2"))
    r.on_event(ScenarioEndEvent(scenario_id="sc-1", status="failed", step_count=2, suite_id="s"))

    assert "sc-1" in r._scenarios
    assert r._scenarios["sc-1"]["scenario_name"] == "Demo"
    assert r._scenarios["sc-1"]["status"] == "failed"
    assert r._step_order["sc-1"] == ["s1", "s2"]
    s1 = r._steps[("sc-1", "s1")]
    s2 = r._steps[("sc-1", "s2")]
    assert s1["step_name"] == "Login" and s1["status"] == "passed"
    assert s2["step_name"] == "GetUser" and s2["status"] == "failed"
    assert s2["error"] == "AssertionError: expected 200, got 500"
    assert r._http_count == 1
    assert len(r._http_calls[("sc-1", "s2")]) == 2
    print(" [1] on_event accumulates scenario/step/http state with correct ordering: OK")


def test_finalize_writes_html_with_steps_and_http():
    from gimbal.reporter.builtin.html_reporter import HtmlReporter
    from gimbal.events.types import (
        ScenarioStartEvent, ScenarioEndEvent, StepStartEvent, StepEndEvent,
        HttpRequestEvent, HttpResponseEvent,
    )
    from gimbal.core.runner import RunResult

    with tempfile.TemporaryDirectory() as td:
        r, ctx = _build_ctx(td)
        r.begin(ctx)
        r.on_event(ScenarioStartEvent(scenario_id="sc-1", scenario_name="Payment", step_count=2, suite_id="s"))
        r.on_event(StepStartEvent(scenario_id="sc-1", step_id="s1", step_name="Login", strategy_kind="http"))
        r.on_event(StepEndEvent(scenario_id="sc-1", step_id="s1", status="passed", duration_ms=10.0,
                                 assertion_count=1, assertion_passed=1, promotion_count=0))
        r.on_event(StepStartEvent(scenario_id="sc-1", step_id="s2", step_name="GetUser", strategy_kind="http"))
        r.on_event(StepEndEvent(scenario_id="sc-1", step_id="s2", status="failed", duration_ms=20.0,
                                 assertion_count=2, assertion_passed=1, promotion_count=0,
                                 error_brief="AssertionError: 500"))
        r.on_event(HttpRequestEvent(method="POST", url="http://x/login", step_id="s1"))
        r.on_event(HttpResponseEvent(method="POST", url="http://x/login", status_code=200,
                                      duration_ms=8.0, step_id="s1"))
        r.on_event(HttpRequestEvent(method="GET", url="http://x/users/1", step_id="s2"))
        r.on_event(HttpResponseEvent(method="GET", url="http://x/users/1", status_code=500,
                                      duration_ms=20.0, step_id="s2"))
        r.on_event(ScenarioEndEvent(scenario_id="sc-1", status="failed", step_count=2, suite_id="s"))

        rr = RunResult(exit_code=1, total=1, passed=0, failed=1, details=[{
            "scenario_id": "sc-1", "status": "failed", "duration_ms": 30.0,
        }])
        art = r.finalize(rr, ctx)

        assert art.name == "html"
        assert art.path is not None and os.path.isfile(art.path), f"file not created: {art.path}"
        assert art.media_type == "text/html"
        body = open(art.path, encoding="utf-8").read()

        # ── HTML 框架 ──
        assert "<!doctype html>" in body
        assert "Gimbal Report" in body
        assert "sc-1" in body
        assert "Payment" in body  # scenario_name

        # ── step 详情 ──
        assert "Login" in body          # step_name s1
        assert "GetUser" in body        # step_name s2
        assert "asserts=1/1" in body    # s1 assertion summary
        assert "asserts=1/2" in body    # s2 assertion summary
        assert "http" in body.lower()   # strategy_kind

        # ── 错误块 ──
        assert '<pre class="err">' in body
        assert "AssertionError: 500" in body

        # ── HTTP 详情 ──
        assert "POST" in body
        assert "GET" in body
        assert "200" in body
        assert "500" in body
        assert "http-summary" in body

        # ── 报告数据 JSON ──
        assert 'id="report-data"' in body
        assert '"scenarios"' in body
        assert '"steps"' in body

        # ── metadata ──
        assert art.metadata["scenario_count"] == 1
        assert art.metadata["http_count"] == 2
        assert art.metadata["size"] > 0
        print(" [2] finalize writes HTML with step details, errors, HTTP, scenario_name, JSON: OK")


def test_step_order_preserved():
    from gimbal.reporter.builtin.html_reporter import HtmlReporter
    from gimbal.events.types import StepStartEvent, StepEndEvent

    r = HtmlReporter()
    for sid in ("step-3", "step-1", "step-2", "step-4"):
        r.on_event(StepStartEvent(scenario_id="sc-A", step_id=sid, step_name=sid, strategy_kind=""))
        r.on_event(StepEndEvent(scenario_id="sc-A", step_id=sid, status="passed", duration_ms=1.0))
    assert r._step_order["sc-A"] == ["step-3", "step-1", "step-2", "step-4"]
    print(" [3] step order matches first-seen order regardless of natural sort: OK")


def test_fallback_when_no_events():
    """事件未触发时，HtmlReporter 必须能基于 RunResult.details 渲染。"""
    from gimbal.reporter.builtin.html_reporter import HtmlReporter
    from gimbal.core.runner import RunResult

    with tempfile.TemporaryDirectory() as td:
        r, ctx = _build_ctx(td)
        r.begin(ctx)
        # 不调用任何 on_event，直接 finalize
        rr = RunResult(exit_code=0, total=1, passed=1, details=[{
            "scenario_id": "sc-fallback", "status": "passed", "duration_ms": 5.0,
        }])
        art = r.finalize(rr, ctx)
        body = open(art.path, encoding="utf-8").read()
        assert "sc-fallback" in body
        assert "No steps recorded." in body  # 显式提示
        assert art.metadata["scenario_count"] == 1
        assert art.metadata["http_count"] == 0
        print(" [4] fallback to RunResult.details when no events fired: OK")


def test_step_failed_marks_step_red():
    from gimbal.reporter.builtin.html_reporter import HtmlReporter
    from gimbal.events.types import (
        ScenarioStartEvent, ScenarioEndEvent, StepStartEvent, StepFailedEvent,
    )
    from gimbal.core.runner import RunResult

    with tempfile.TemporaryDirectory() as td:
        r, ctx = _build_ctx(td)
        r.begin(ctx)
        r.on_event(ScenarioStartEvent(scenario_id="sc-x", scenario_name="X", step_count=1, suite_id=""))
        r.on_event(StepStartEvent(scenario_id="sc-x", step_id="only", step_name="doIt", strategy_kind="http"))
        r.on_event(StepFailedEvent(step_id="only", error="kaboom", phase="execute"))
        r.on_event(ScenarioEndEvent(scenario_id="sc-x", status="failed", step_count=1, suite_id=""))

        rr = RunResult(exit_code=1, total=1, failed=1, details=[
            {"scenario_id": "sc-x", "status": "failed", "duration_ms": 0.0}
        ])
        art = r.finalize(rr, ctx)
        body = open(art.path, encoding="utf-8").read()
        assert 'data-step-status="failed"' in body
        assert "kaboom" in body
        assert 'data-status="failed"' in body  # scenario open
        print(" [5] StepFailedEvent marks step red and surfaces error in HTML: OK")


def test_meta_block_includes_run_id_and_env():
    from gimbal.reporter.builtin.html_reporter import HtmlReporter
    from gimbal.events.types import ScenarioStartEvent, ScenarioEndEvent
    from gimbal.core.runner import RunResult

    with tempfile.TemporaryDirectory() as td:
        r, ctx = _build_ctx(td)
        r.begin(ctx)
        r.on_event(ScenarioStartEvent(scenario_id="sc-z", scenario_name="Z", step_count=0, suite_id=""))
        r.on_event(ScenarioEndEvent(scenario_id="sc-z", status="passed", step_count=0, suite_id=""))
        rr = RunResult(exit_code=0, total=1, passed=1, details=[
            {"scenario_id": "sc-z", "status": "passed", "duration_ms": 0.0}
        ])
        art = r.finalize(rr, ctx)
        body = open(art.path, encoding="utf-8").read()
        assert "rid-test" in body  # run_id
        assert "dev" in body        # env
        assert "local" in body      # mode
        assert "0.1.0" in body      # framework_version
        print(" [6] meta block surfaces run_id / env / mode / framework_version: OK")


def test_run_meta_event_populates_header():
    """RunMetaEvent 缓存到 self._run_meta 并在 HTML 头部渲染 .run-meta 区块。"""
    from gimbal.reporter.builtin.html_reporter import HtmlReporter
    from gimbal.events.types import (
        ScenarioStartEvent, ScenarioEndEvent, RunMetaEvent,
    )
    from gimbal.core.runner import RunResult

    with tempfile.TemporaryDirectory() as td:
        r, ctx = _build_ctx(td)
        r.begin(ctx)
        # 头部元数据：CI / branch / commit / triggered_by / build_url
        r.on_event(RunMetaEvent(meta={
            "ci": "github-actions",
            "branch": "main",
            "commit": "abc1234",
            "triggered_by": "alice",
            "build_url": "https://ci.example.com/build/42",
            "pr": "123",  # 扩展键
        }))
        r.on_event(ScenarioStartEvent(scenario_id="sc-m", scenario_name="Meta", step_count=0, suite_id=""))
        r.on_event(ScenarioEndEvent(scenario_id="sc-m", status="passed", step_count=0, suite_id=""))
        rr = RunResult(exit_code=0, total=1, passed=1, details=[
            {"scenario_id": "sc-m", "status": "passed", "duration_ms": 1.0}
        ])
        art = r.finalize(rr, ctx)

        # 缓存层
        assert r._run_meta.get("ci") == "github-actions"
        assert r._run_meta.get("branch") == "main"
        assert art.metadata["has_run_meta"] is True

        body = open(art.path, encoding="utf-8").read()
        # .run-meta 区块存在
        assert 'class="run-meta"' in body
        # 主键 pill
        assert "github-actions" in body
        assert "main" in body
        assert "abc1234" in body
        assert "alice" in body
        # 扩展键
        assert "pr" in body
        assert "123" in body
        # pill-ci / pill-meta 样式至少一个
        assert "pill-ci" in body or "pill-meta" in body
        # 嵌入 JSON 也带 run_meta
        assert '"run_meta"' in body
        print(" [7] RunMetaEvent populates header .run-meta block and JSON dump: OK")


def test_run_meta_via_collect_run_meta_field_names():
    """回归测试：_collect_run_meta() 产出的字段名必须与 _render_run_meta() 主键对齐。

    历史 bug：_collect_run_meta 原本产出 `git_branch` / `git_commit`，但渲染端
    primary_keys 期望 `branch` / `commit`，导致真实 CI 环境下的 meta pill
    静默 MISS。修复后两者统一为短名（branch / commit）。

    本测试通过真实路径走一遍：env var → _collect_run_meta → bus.publish →
    HtmlReporter.on_event → _render_run_meta，确保所有"主键"在 producer
    端一定存在（contract 验证）。
    """
    from gimbal.reporter.builtin.html_reporter import HtmlReporter
    from gimbal.events.types import (
        ScenarioStartEvent, ScenarioEndEvent, RunMetaEvent,
    )
    from gimbal.core.runner import RunResult
    from gimbal.cli.common import _collect_run_meta

    with tempfile.TemporaryDirectory() as td:
        r, ctx = _build_ctx(td)
        r.begin(ctx)
        # 走真实路径：env vars → _collect_run_meta() → on_event
        meta = _collect_run_meta()
        r.on_event(RunMetaEvent(meta=meta))

        r.on_event(ScenarioStartEvent(scenario_id="sc-r", scenario_name="Real", step_count=0, suite_id=""))
        r.on_event(ScenarioEndEvent(scenario_id="sc-r", status="passed", step_count=0, suite_id=""))
        rr = RunResult(exit_code=0, total=1, passed=1, details=[
            {"scenario_id": "sc-r", "status": "passed", "duration_ms": 1.0}
        ])
        art = r.finalize(rr, ctx)
        body = open(art.path, encoding="utf-8").read()

        # 关键断言：_collect_run_meta 产出的字段名集合 ⊇ 渲染端 primary_keys
        # （防止未来再次出现 producer / consumer 命名空间漂移）
        producer_keys = set(meta.keys())
        renderer_primary = {"branch", "commit", "build_url", "ci", "triggered_by"}
        missing = renderer_primary - producer_keys
        assert not missing, (
            f"REGRESSION: 渲染端期望主键 {missing!r} 但 _collect_run_meta 不产出。"
            f"实际产出 keys={sorted(producer_keys)}"
        )

        # 至少 triggered_by 一定会有值（USER env var 在测试环境也存在），
        # 应以 pill 形式出现在头部
        assert "pill-meta" in body or "pill-ci" in body, \
            "run-meta 区块应至少含 1 个 pill"
        print(" [7b] _collect_run_meta 字段名与 _render_run_meta 主键完全对齐: OK")


def test_scenario_meta_chips_render_in_summary():
    """ScenarioEndEvent.meta 渲染为 scenario summary 末尾的 chip 行。"""
    from gimbal.reporter.builtin.html_reporter import HtmlReporter
    from gimbal.events.types import (
        ScenarioStartEvent, ScenarioEndEvent, StepStartEvent, StepEndEvent,
    )
    from gimbal.core.runner import RunResult

    with tempfile.TemporaryDirectory() as td:
        r, ctx = _build_ctx(td)
        r.begin(ctx)
        r.on_event(ScenarioStartEvent(
            scenario_id="sc-tags", scenario_name="Tagged", step_count=1, suite_id="s",
        ))
        r.on_event(StepStartEvent(scenario_id="sc-tags", step_id="s1", step_name="Do", strategy_kind="http"))
        r.on_event(StepEndEvent(
            scenario_id="sc-tags", step_id="s1", status="passed", duration_ms=1.0,
        ))
        r.on_event(ScenarioEndEvent(
            scenario_id="sc-tags", status="passed", step_count=1, suite_id="s",
            meta={
                "tags": ["smoke", "regression"],
                "author": "bob",
                "priority": "P0",
                "version": "1.2.3",
            },
        ))

        # 缓存层
        assert r._scenarios["sc-tags"]["meta"] == {
            "tags": ["smoke", "regression"],
            "author": "bob",
            "priority": "P0",
            "version": "1.2.3",
        }

        rr = RunResult(exit_code=0, total=1, passed=1, details=[
            {"scenario_id": "sc-tags", "status": "passed", "duration_ms": 1.0}
        ])
        art = r.finalize(rr, ctx)
        body = open(art.path, encoding="utf-8").read()

        # chip 容器存在
        assert "scenario-meta-chips" in body
        # tag pill
        assert "pill-tag" in body
        assert "smoke" in body
        assert "regression" in body
        # meta pill
        assert "bob" in body
        assert "P0" in body
        assert "1.2.3" in body
        print(" [8] ScenarioEndEvent.meta renders as tag/author/priority chips in summary: OK")


def main():
    test_on_event_accumulates_state()
    test_finalize_writes_html_with_steps_and_http()
    test_step_order_preserved()
    test_fallback_when_no_events()
    test_step_failed_marks_step_red()
    test_meta_block_includes_run_id_and_env()
    test_run_meta_event_populates_header()
    test_run_meta_via_collect_run_meta_field_names()
    test_scenario_meta_chips_render_in_summary()
    print("=" * 60)
    print("ALL HTML REPORTER TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
