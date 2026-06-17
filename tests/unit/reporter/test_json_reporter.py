"""Unit tests for gimbal.reporter.builtin.json_reporter (JsonReporter).

Coverage:
  [1] finalize writes a JSON file with meta + summary + details
  [2] run_id, env, mode appear in meta
  [3] include_event_timeline=True records events to the timeline
  [4] indent user_config is honored
"""
import sys, os, json, tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("JSON REPORTER TEST")
print("=" * 60)


def _make_framework_ctx(run_id="r-001", env="dev", mode="local", framework_version="0.1.0"):
    """Build a minimal object that satisfies the fields JsonReporter reads."""
    class FC:
        pass
    fc = FC()
    fc.run_id = run_id
    fc.environment = env
    fc.mode = mode
    fc.framework_version = framework_version
    return fc


def _build_ctx(tmpdir, *, include_timeline=False, indent=2, framework_ctx=None):
    from gimbal.reporter.builtin.json_reporter import JsonReporter
    from gimbal.reporter.protocol import ReportContext
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.events.subscription import SubscriptionMode

    r = JsonReporter()
    bus = InMemoryEventBus()
    class _Cfg:
     no_color = True
    fc = framework_ctx or _make_framework_ctx()
    ctx = ReportContext(
     framework_ctx=fc, bus=bus, config=_Cfg(),
     report_dir=Path(tmpdir), user_config={
      "include_event_timeline": include_timeline,
      "indent": indent,
     },
     artifacts_dir=Path(tmpdir),
     subscription_mode=SubscriptionMode.SYNC,
    )
    return r, ctx


def test_finalize_writes_json():
    from gimbal.core.runner import RunResult
    with tempfile.TemporaryDirectory() as td:
     r, ctx = _build_ctx(td)
     r.begin(ctx)
     rr = RunResult(exit_code=0, total=2, passed=1, failed=1, details=[
      {"scenario_id": "sc-1", "status": "passed", "duration_ms": 1.0},
      {"scenario_id": "sc-2", "status": "failed", "duration_ms": 2.0, "error": "x"},
     ])
     art = r.finalize(rr, ctx)
     assert art.name == "json"
     assert art.path is not None and os.path.isfile(art.path)
     assert art.media_type == "application/json"
     body = open(art.path, encoding="utf-8").read()
     data = json.loads(body)
     assert "meta" in data and "summary" in data and "details" in data
     assert data["meta"]["run_id"] == "r-001"
     assert data["meta"]["env"] == "dev"
     assert data["meta"]["mode"] == "local"
     assert data["summary"]["total"] ==2
     assert data["summary"]["failed"] ==1
     assert len(data["details"]) ==2
     assert "event_timeline" not in data # default off
     print(" [1] finalize writes JSON with meta + summary + details: OK")


def test_indent_honored():
    from gimbal.core.runner import RunResult
    with tempfile.TemporaryDirectory() as td:
     r, ctx = _build_ctx(td, indent=4)
     r.begin(ctx)
     art = r.finalize(RunResult(), ctx)
     body = open(art.path, encoding="utf-8").read()
     # 4-space indent: first content line indented by 4 spaces
     lines = body.splitlines()
     assert any(line.startswith("    \"meta\"") for line in lines), \
      f"expected 4-space indent, got:\n{body[:200]}"
     print(" [2] indent user_config honored: OK")


def test_event_timeline_off_by_default():
    from gimbal.core.runner import RunResult
    from gimbal.events.types import StepEndEvent
    with tempfile.TemporaryDirectory() as td:
     r, ctx = _build_ctx(td, include_timeline=False)
     r.begin(ctx)
     # Even if events come, timeline should be off
     r._record_event(StepEndEvent(
      scenario_id="sc", step_id="s1", status="passed", duration_ms=1.0,
     ))
     art = r.finalize(RunResult(), ctx)
     data = json.loads(open(art.path, encoding="utf-8").read())
     assert "event_timeline" not in data
     print(" [3] event_timeline off by default: OK")


def test_event_timeline_on():
    from gimbal.core.runner import RunResult
    from gimbal.events.types import StepEndEvent
    with tempfile.TemporaryDirectory() as td:
     r, ctx = _build_ctx(td, include_timeline=True)
     r.begin(ctx)
     # Manually inject an event (in real flow, bus.subscribe delivers these)
     r._record_event(StepEndEvent(
      scenario_id="sc", step_id="s1", status="passed", duration_ms=1.0,
     ))
     art = r.finalize(RunResult(), ctx)
     data = json.loads(open(art.path, encoding="utf-8").read())
     assert "event_timeline" in data
     assert len(data["event_timeline"]) ==1
     assert data["event_timeline"][0]["type"] == "step.end"
     print(" [4] event_timeline on: records events: OK")


def main():
    test_finalize_writes_json()
    test_indent_honored()
    test_event_timeline_off_by_default()
    test_event_timeline_on()
    print("=" * 60)
    print("ALL JSON REPORTER TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
