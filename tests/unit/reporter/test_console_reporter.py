"""Unit tests for gimbal.reporter.builtin.console (ConsoleReporter).

Coverage:
  [1] on_event handles Scenario/Step/Http events without raising
  [2] finalize returns ReportArtifact with inline text (no file)
  [3] failed-step tracking populates _failed_steps
  [4] no_color honored
  [5] verbose mode subscribes to HTTP events
"""
import sys, os, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("CONSOLE REPORTER TEST")
print("=" * 60)


def test_on_event_handlers():
    from gimbal.reporter.builtin.console import ConsoleReporter
    from gimbal.events.types import (
     ScenarioStartEvent, ScenarioEndEvent, StepStartEvent, StepEndEvent,
     StepFailedEvent, HttpRequestEvent, HttpResponseEvent,
    )
    r = ConsoleReporter()
    saved = sys.stderr
    sys.stderr = io.StringIO()
    try:
     r.on_event(ScenarioStartEvent(
     scenario_id="sc-1", scenario_name="Demo", step_count=2, suite_id="s",
     ))
     r.on_event(StepStartEvent(
     scenario_id="sc-1", step_id="s1", step_name="go", strategy_kind="http",
     ))
     r.on_event(StepEndEvent(
     scenario_id="sc-1", step_id="s1", status="passed", duration_ms=12.0,
     assertion_count=1, assertion_passed=1, promotion_count=0,
     ))
     r.on_event(StepFailedEvent(
     step_id="s2", phase="execute", error="boom",
     ))
     r.on_event(HttpRequestEvent(
     method="GET", url="http://x/y", step_id="s1",
     ))
     r.on_event(HttpResponseEvent(
     method="GET", url="http://x/y", status_code=200, duration_ms=5.0, step_id="s1",
     ))
     r.on_event(ScenarioEndEvent(
     scenario_id="sc-1", status="failed", step_count=2, suite_id="s",
     ))
    finally:
     captured = sys.stderr.getvalue()
     sys.stderr = saved
    assert "sc-1" in captured
    assert r._failed_steps and r._failed_steps[0]["step_id"] == "s2"
    print(" [1] on_event handles all event types; failed-steps tracked: OK")


def test_finalize_returns_inline_artifact():
    from gimbal.reporter.builtin.console import ConsoleReporter
    from gimbal.reporter.protocol import ReportContext
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.events.subscription import SubscriptionMode
    from gimbal.core.runner import RunResult

    r = ConsoleReporter()
    bus = InMemoryEventBus()
    class _Cfg:
     no_color = True
    ctx = ReportContext(
     framework_ctx=None, bus=bus, config=_Cfg(),
     report_dir=".", user_config={}, artifacts_dir=".",
     subscription_mode=SubscriptionMode.SYNC,
    )
    r.begin(ctx)
    saved = sys.stderr
    sys.stderr = io.StringIO()
    try:
     art = r.finalize(
      RunResult(exit_code=0, total=1, passed=1, failed=0, details=[
       {"scenario_id": "sc-1", "status": "passed", "duration_ms": 7.5},
      ]),
      ctx,
     )
    finally:
     sys.stderr = saved
    assert art.name == "console"
    assert art.path is None
    assert art.media_type == "text/plain"
    assert art.content and "PASS" in art.content
    assert art.metadata["total"] ==1 and art.metadata["passed"] ==1
    print(" [2] finalize returns ReportArtifact (inline, no path) with metadata: OK")


def test_no_color_honored():
    from gimbal.reporter.builtin.console import ConsoleReporter
    from gimbal.reporter.protocol import ReportContext
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.events.subscription import SubscriptionMode
    from gimbal.core.runner import RunResult

    r = ConsoleReporter()
    bus = InMemoryEventBus()
    class _Cfg:
     no_color = True
    ctx = ReportContext(
     framework_ctx=None, bus=bus, config=_Cfg(),
     report_dir=".", user_config={"no_color": True}, artifacts_dir=".",
     subscription_mode=SubscriptionMode.SYNC,
    )
    r.begin(ctx)
    saved = sys.stderr
    sys.stderr = io.StringIO()
    try:
     art = r.finalize(RunResult(), ctx)
    finally:
     sys.stderr = saved
    # No ANSI escape sequences expected when no_color is true
    assert "\x1b[" not in art.content
    print(" [3] no_color honored (no ANSI in output): OK")


def test_verbose_http_events():
    from gimbal.reporter.builtin.console import ConsoleReporter
    from gimbal.reporter.protocol import ReportContext
    from gimbal.events.types import HttpRequestEvent, HttpResponseEvent
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.events.subscription import SubscriptionMode

    r = ConsoleReporter()
    bus = InMemoryEventBus()
    class _Cfg:
     no_color = True
    ctx = ReportContext(
     framework_ctx=None, bus=bus, config=_Cfg(),
     report_dir=".", user_config={"verbosity": "verbose"}, artifacts_dir=".",
     subscription_mode=SubscriptionMode.SYNC,
    )
    r.begin(ctx)
    saved = sys.stderr
    sys.stderr = io.StringIO()
    try:
     r.on_event(HttpRequestEvent(method="GET", url="http://x/y", step_id="s1"))
     r.on_event(HttpResponseEvent(
      method="GET", url="http://x/y", status_code=200, duration_ms=5.0, step_id="s1",
     ))
     captured = sys.stderr.getvalue()
    finally:
     sys.stderr = saved
    assert "GET" in captured and "200" in captured
    print(" [4] verbose mode prints HTTP request/response: OK")


def main():
    test_on_event_handlers()
    test_finalize_returns_inline_artifact()
    test_no_color_honored()
    test_verbose_http_events()
    print("=" * 60)
    print("ALL CONSOLE REPORTER TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
