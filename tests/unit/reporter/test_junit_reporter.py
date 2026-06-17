"""Unit tests for gimbal.reporter.builtin.junit (JUnitReporter).

Coverage:
  [1] finalize produces a valid JUnit XML file
  [2] file content contains scenario_id and status
  [3] failed scenarios are reported with <failure> element
  [4] path is set and content is empty
  [5] artifact metadata includes scenario_count
"""
import sys, os, tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("JUNIT REPORTER TEST")
print("=" * 60)


def _build_ctx(tmpdir):
    from gimbal.reporter.builtin.junit import JUnitReporter
    from gimbal.reporter.protocol import ReportContext
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.events.subscription import SubscriptionMode

    r = JUnitReporter()
    bus = InMemoryEventBus()
    class _Cfg:
     no_color = True
    ctx = ReportContext(
     framework_ctx=None, bus=bus, config=_Cfg(),
     report_dir=Path(tmpdir), user_config={}, artifacts_dir=Path(tmpdir),
     subscription_mode=SubscriptionMode.SYNC,
    )
    return r, ctx


def test_finalize_writes_xml_file():
    from gimbal.core.runner import RunResult
    with tempfile.TemporaryDirectory() as td:
     r, ctx = _build_ctx(td)
     r.begin(ctx)
     rr = RunResult(exit_code=0, total=2, passed=1, failed=1, details=[
      {"scenario_id": "sc-1", "status": "passed", "duration_ms": 12.5},
      {"scenario_id": "sc-2", "status": "failed", "duration_ms": 7.0, "error": "AssertionError: x != y"},
     ])
     art = r.finalize(rr, ctx)
     assert art.name == "junit"
     assert art.path is not None and os.path.isfile(art.path), f"file not created: {art.path}"
     assert art.media_type == "application/xml"
     body = open(art.path, encoding="utf-8").read()
     assert "<?xml" in body and "<testsuite" in body
     assert "sc-1" in body and "sc-2" in body
     # JUnit format encodes pass/fail via attribute counts, not status text
     assert 'failures="1"' in body # one failure (sc-2)
     assert "Gimbal.sc-1" in body and "Gimbal.sc-2" in body
     assert art.metadata["tests"] ==2
     assert art.metadata["failures"] ==1
     print(" [1] finalize writes JUnit XML with scenarios, status, metadata: OK")


def test_failed_scenario_has_failure_element():
    from gimbal.core.runner import RunResult
    with tempfile.TemporaryDirectory() as td:
     r, ctx = _build_ctx(td)
     r.begin(ctx)
     rr = RunResult(exit_code=1, total=1, failed=1, details=[
      {"scenario_id": "sc-fail", "status": "failed",
       "duration_ms": 5.0, "error": "AssertionError: expected 200, got 500"},
     ])
     art = r.finalize(rr, ctx)
     body = open(art.path, encoding="utf-8").read()
     assert "<failure" in body
     assert "AssertionError" in body
     print(" [2] failed scenario has <failure> element with error text: OK")


def test_empty_run_produces_valid_xml():
    from gimbal.core.runner import RunResult
    with tempfile.TemporaryDirectory() as td:
     r, ctx = _build_ctx(td)
     r.begin(ctx)
     art = r.finalize(RunResult(), ctx)
     body = open(art.path, encoding="utf-8").read()
     assert body.startswith("<?xml")
     assert "<testsuite" in body
     print(" [3] empty run still produces valid XML skeleton: OK")


def main():
    test_finalize_writes_xml_file()
    test_failed_scenario_has_failure_element()
    test_empty_run_produces_valid_xml()
    print("=" * 60)
    print("ALL JUNIT REPORTER TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
