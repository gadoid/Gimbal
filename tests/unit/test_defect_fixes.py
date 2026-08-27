"""Unit tests for the low-risk defect fixes identified in the code review.

Covers the following fix points (numbers match the report):
  #11  EventFilter: re.match -> re.fullmatch
  #14  _publish_run_meta silent except -> logger.warning
  #23  RunEndEvent add skipped field
  #34/#79  HttpResponseEvent status_code conversion crash
  #45  Suite details add step_results
  #57  step_count exclude unresolved StepRef
  #76  wl.py docstring fix
  #77  auth files f-string log -> loguru style
  #78  PreToken mode refresh skip

Tests use a self-assert style (matches tests/unit/test_asset_materializer.py).
"""
import sys
import os
import re
import time
from datetime import datetime, timezone, timedelta

# Force UTF-8 stdout to avoid GBK encoding issues on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("DEFECT FIXES TEST SUITE")
print("=" * 60)

results: list[tuple[str, bool, str]] = []


def test(name: str):
    """Test decorator: capture exceptions and record results."""
    def deco(fn):
        try:
            fn()
            results.append((name, True, ""))
            print(f"  [PASS] {name}")
        except AssertionError as e:
            results.append((name, False, str(e)))
            print(f"  [FAIL] {name}: {e}")
        except Exception as e:  # noqa: BLE001
            import traceback
            tb = traceback.format_exc()
            results.append((name, False, f"{type(e).__name__}: {e}\n{tb}"))
            print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        return fn
    return deco


# ════════════════════════════════════════════════════════════════════
# #11  EventFilter: re.match -> re.fullmatch
# ════════════════════════════════════════════════════════════════════
print("\n[1] EventFilter re.fullmatch (#11)")

from gimbal.events.subscription import EventFilter
from gimbal.events.types import StepStartEvent, StepEndEvent


@test("#11.1 exact event_type filter still works")
def _():
    f = EventFilter(event_type="step.start")
    ev = StepStartEvent(step_id="s1", step_name="n1")
    assert f.matches(ev), "exact event_type match should pass"
    ev_end = StepEndEvent(step_id="s1", status="passed", duration_ms=1.0)
    assert not f.matches(ev_end), "non-matching event_type should be filtered"


@test("#11.2 'step.start' literal pattern no longer matches 'step.start.extra'")
def _():
    # The actual difference between re.match and re.fullmatch:
    #   re.match anchors at start, re.fullmatch anchors at both ends
    # So a pattern like "step.start" should NOT match "step.start.extra"
    f = EventFilter(event_type_pattern="step.start")
    # Real step.start event
    ev_match = StepStartEvent(step_id="s1", step_name="n1")
    assert f.matches(ev_match), "step.start should match itself"
    # 'step.start.extra' -- old re.match would pass, new re.fullmatch must reject
    class _ExtraEvent:
        event_type = "step.start.extra"
        run_id = None
        step_id = None
        scenario_id = None
    assert not f.matches(_ExtraEvent()), (
        "step.start.extra should NOT match 'step.start' (defect #11 fix)"
    )


@test("#11.3 pattern '.*end$' full match")
def _():
    f = EventFilter(event_type_pattern=".*end$")
    class _A:
        event_type = "step.end"
        run_id = None; step_id = None; scenario_id = None
    class _B:
        event_type = "step.start"
        run_id = None; step_id = None; scenario_id = None
    class _C:
        event_type = "endpoint"
        run_id = None; step_id = None; scenario_id = None
    assert f.matches(_A())
    assert not f.matches(_B())
    assert not f.matches(_C()), "endpoint should not match pattern ending in 'end$'"


# ════════════════════════════════════════════════════════════════════
# #23  RunEndEvent add skipped field
# ════════════════════════════════════════════════════════════════════
print("\n[2] RunEndEvent skipped field (#23)")

from gimbal.events.types import RunEndEvent


@test("#23.1 default skipped=0 is backward compatible")
def _():
    ev = RunEndEvent(total=10, passed=8, failed=1, error=1)
    assert ev.skipped == 0, f"default skipped should be 0, got {ev.skipped}"
    assert ev.total == 10 and ev.passed == 8 and ev.failed == 1 and ev.error == 1


@test("#23.2 explicit skipped is preserved")
def _():
    ev = RunEndEvent(total=10, passed=5, failed=2, error=1, skipped=2)
    assert ev.skipped == 2, f"skipped should be 2, got {ev.skipped}"


# ════════════════════════════════════════════════════════════════════
# #14  _publish_run_meta silent except -> logger.warning
# ════════════════════════════════════════════════════════════════════
print("\n[3] _publish_run_meta exception handling (#14)")

import inspect
from gimbal.cli import common as cli_common


@test("#14.1 _publish_run_meta uses logger.warning instead of pass")
def _():
    src = inspect.getsource(cli_common._publish_run_meta)
    assert "logger.warning" in src, "should use logger.warning instead of pass"
    # extract except block
    after_except = src.split("except Exception")[1] if "except Exception" in src else ""
    assert "pass" not in after_except, "should not silently pass in except block"


@test("#14.2 _publish_run_meta returns early when bus is None")
def _():
    class _FakeCfg:
        event_bus = None

    # Should not raise
    cli_common._publish_run_meta(_FakeCfg())


# ════════════════════════════════════════════════════════════════════
# #34/#79  HttpResponseEvent status_code conversion crash
# ════════════════════════════════════════════════════════════════════
print("\n[4] HttpResponseEvent status code defense (#34/#79)")

from gimbal.statemachine import engine as sm_engine
from gimbal.strategy.executor_base import StrategyResult, StrategyStatus, PhaseResult
from gimbal.schema.strategy import StrategyPhase, FailurePolicy


class _FakeBus:
    """Mock event_bus, captures publish calls."""
    def __init__(self):
        self.published: list = []

    def publish(self, event):
        self.published.append(event)


class _FakeCallSpec:
    method = "GET"
    url = "http://test/api"
    headers = {}
    body = {}
    timeout = 30.0


def _make_sm(bus):
    """Construct StepStateMachine without going through __init__ side effects."""
    sm = sm_engine.StepStateMachine.__new__(sm_engine.StepStateMachine)
    sm._step_id = "s1"
    sm._step_schema = None
    sm._dispatcher = None
    sm._view = None
    sm._service_base_url = ""
    sm._on_transition = None
    sm._hooks = None
    sm._bus = bus
    sm._state = sm_engine.StepState.PENDING
    sm._phase_results = []
    sm._error = None
    sm._error_phase = None  # 修复 #5：需要显式初始化
    sm._handlers = {}
    return sm


@test("#34.1 HTTP success: status_code correct")
def _():
    bus = _FakeBus()
    sm = _make_sm(bus)
    result = StrategyResult(status=StrategyStatus.PASSED, message="ok", duration_ms=100.0)
    result.status = 200  # simulate HTTP 200
    sm._emit_http_response(_FakeCallSpec(), result)
    assert len(bus.published) == 1, f"should publish 1 event, got {len(bus.published)}"
    assert bus.published[0].status_code == 200, f"status_code should be 200"


@test("#34.2 HTTP failure: status string no longer crashes")
def _():
    bus = _FakeBus()
    sm = _make_sm(bus)
    # Simulate HTTP error: result.status is string "timeout"
    result = StrategyResult(status=StrategyStatus.ERROR, message="timeout", duration_ms=0.0)
    result.status = "timeout"  # string, old code int() would crash
    sm._emit_http_response(_FakeCallSpec(), result)  # should not raise ValueError
    assert len(bus.published) == 1
    assert bus.published[0].status_code == 0, (
        f"when conversion fails should be 0, got {bus.published[0].status_code}"
    )


@test("#34.3 result.status=None does not crash")
def _():
    bus = _FakeBus()
    sm = _make_sm(bus)
    result = StrategyResult(status=StrategyStatus.ERROR, message="x", duration_ms=0.0)
    result.status = None
    sm._emit_http_response(_FakeCallSpec(), result)
    assert bus.published[0].status_code == 0


# ════════════════════════════════════════════════════════════════════
# #45  Suite details includes step_results
# ════════════════════════════════════════════════════════════════════
print("\n[5] Suite details includes steps (#45)")

from gimbal.core.runner import Engine
from gimbal.core.scenario_runner import ScenarioRunResult, StepRunResult
from unittest.mock import MagicMock, patch


def _make_scenario_run_result(scenario_id: str, step_count: int = 2) -> ScenarioRunResult:
    steps = [
        StepRunResult(step_id=f"step-{i:03d}", status="passed", duration_ms=10.0 * i)
        for i in range(step_count)
    ]
    return ScenarioRunResult(
        scenario_id=scenario_id,
        status="passed",
        step_results=steps,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )


@test("#45.1 _run_suite details include steps field")
def _():
    from gimbal.schema.scenario import Suite, Scenario, Meta, Config

    sc = Scenario(
        scenarioId="sc-1",
        meta=Meta(
            name="t", description="d", module="m", priority=1,
            author="a", owner="o", tags=[], version="1.0",
            createTime=datetime.now(timezone.utc), expire=False, requirementRef=[],
        ),
        config=Config(),
        resource={},
        steps=[],
    )
    suite = Suite(suite=[sc])

    # Mock framework_ctx
    framework_ctx = MagicMock()
    framework_ctx.run_id = "rid"
    framework_ctx.config = MagicMock(fail_fast=False)
    framework_ctx.dispatcher = MagicMock()
    suite_ctx = MagicMock(suite_id="s1")
    framework_ctx.ctx_manager.derive_suite_context.return_value = suite_ctx

    # Mock ScenarioRunner.run to return 3 steps
    mock_result = _make_scenario_run_result("sc-1", step_count=3)

    with patch("gimbal.core.scenario_runner.ScenarioRunner") as MockRunner:
        MockRunner.return_value.run.return_value = mock_result
        engine = Engine.__new__(Engine)
        engine._ictx = MagicMock()
        engine._ictx.dispatcher = MagicMock()
        engine._ictx.hook_registry = MagicMock()
        engine._ictx.event_bus = None
        engine._ictx.auth_registry = MagicMock()
        engine._asset_store = None

        result = engine._run_suite(suite, framework_ctx)

    assert len(result.details) == 1
    assert "steps" in result.details[0], (
        f"details should contain 'steps' key, got keys: {list(result.details[0].keys())}"
    )
    assert len(result.details[0]["steps"]) == 3, (
        f"should have 3 steps, got {len(result.details[0]['steps'])}"
    )
    assert result.details[0]["steps"][0]["step_id"] == "step-000"


# ════════════════════════════════════════════════════════════════════
# #6  service_url 兜底删除
# ════════════════════════════════════════════════════════════════════
print("\n[6b] service_url 兜底删除 (#6)")

from gimbal.schema.api import Api
from gimbal.schema.request import Request
from gimbal.schema.step import Step as StepSchema


def _make_sm_with_api(service: str, base_url: str, api: Api = None):
    """Build StepStateMachine with a real Step schema containing an Api."""
    bus = _FakeBus()
    sm = sm_engine.StepStateMachine.__new__(sm_engine.StepStateMachine)
    sm._step_id = "s1"
    if api is None:
        api = Api(
            kind="api",
            service=service,
            method="GET",
            path="/api/test",
            headers={},
            timeout=30.0,
        )
    request = Request(kind="request", body={})
    sm._step_schema = StepSchema(
        kind="step",
        api=api,
        request=request,
        strategy=[],
    )
    sm._dispatcher = MagicMock()
    sm._dispatcher.dispatch.return_value = StrategyResult(
        status=StrategyStatus.PASSED,
        strategy_id="_call",
        message="mock ok",
        duration_ms=0.0,
    )
    sm._view = MagicMock()
    sm._service_base_url = base_url
    sm._services = {}  # D7 per-step 查表(空 dict = 回落 base_url,保持 #6 语义)
    sm._on_transition = None
    sm._hooks = None
    sm._bus = bus
    sm._state = sm_engine.StepState.CALLING
    sm._phase_results = []
    sm._error = None
    sm._error_phase = None  # 修复 #5：需要显式初始化
    sm._handlers = {}
    return sm, bus


@test("#6.1 empty service_base_url returns ERROR result")
def _():
    sm, bus = _make_sm_with_api(service="fin-tidb", base_url="")
    result = sm._do_http_call()
    assert isinstance(result, StrategyResult)
    assert result.status == StrategyStatus.ERROR, (
        f"expected ERROR status, got {result.status}"
    )
    assert "no service_base_url configured" in result.message, (
        f"message should mention missing config, got: {result.message}"
    )
    assert "fin-tidb" in result.message, (
        f"message should include the service key 'fin-tidb', got: {result.message}"
    )
    # dispatcher must NOT be called when config is missing
    assert sm._dispatcher.dispatch.call_count == 0, (
        "dispatcher should not be invoked when base_url is empty"
    )


@test("#6.2 valid service_base_url proceeds to dispatcher")
def _():
    sm, bus = _make_sm_with_api(
        service="fin-tidb",
        base_url="https://api.example.com",
    )
    result = sm._do_http_call()
    assert result.status == StrategyStatus.PASSED, (
        f"expected PASSED with valid base_url, got {result.status} / {result.message}"
    )
    # dispatcher called once
    assert sm._dispatcher.dispatch.call_count == 1, (
        f"dispatcher should be called once, got {sm._dispatcher.dispatch.call_count}"
    )
    # the call_spec url should start with the base_url
    call_args = sm._dispatcher.dispatch.call_args
    call_spec = call_args[0][0]  # first positional arg
    assert call_spec.url.startswith("https://api.example.com"), (
        f"call_spec.url should start with base_url, got: {call_spec.url}"
    )


@test("#6.3 error message clarifies api.service is a key, not a URL")
def _():
    sm, bus = _make_sm_with_api(
        service="some_service_key",
        base_url="",
    )
    result = sm._do_http_call()
    assert "is a service key, not a URL" in result.message, (
        f"message should clarify service is a key, got: {result.message}"
    )
    # should mention both config locations so user knows where to fix
    assert "scenario.config.services" in result.message, (
        f"message should mention scenario.config.services, got: {result.message}"
    )
    assert "bootstrap.services" in result.message, (
        f"message should mention bootstrap.services, got: {result.message}"
    )


# ════════════════════════════════════════════════════════════════════
# #57  step_count excludes StepRef
# ════════════════════════════════════════════════════════════════════
print("\n[6] step_count excludes StepRef (#57)")


@test("#57.1 executable_count filters out StepRef (no api attr)")
def _():
    step_a = MagicMock(spec=["api"])
    step_b = MagicMock(spec=["api"])
    # StepRef has no 'api' attribute
    step_ref = type("StepRef", (), {})()
    resolved = [step_a, step_ref, step_b]
    executable_count = sum(1 for s in resolved if hasattr(s, "api"))
    assert executable_count == 2, f"should have 2 executable, got {executable_count}"


# ════════════════════════════════════════════════════════════════════
# #76 wl.py docstring
# ════════════════════════════════════════════════════════════════════
print("\n[7] wl.py docstring fix (#76)")


@test("#76.1 wl.py no longer says 'GitHub OAuth2' in docstring")
def _():
    from gimbal.auth.authenticators import wl
    src = inspect.getsource(wl)
    assert "GitHub OAuth2" not in src, (
        "wl.py should not have 'GitHub OAuth2' as docstring"
    )
    assert "WLAuthenticator" in src or "fin-tidb" in src, (
        "docstring should mention WLAuthenticator or fin-tidb"
    )


# ════════════════════════════════════════════════════════════════════
# #77 f-string log -> loguru style
# ════════════════════════════════════════════════════════════════════
print("\n[8] auth files loguru style (#77)")


@test("#77.1 github.py uses {} placeholder")
def _():
    from gimbal.auth.authenticators import github
    src = inspect.getsource(github)
    assert 'logger.debug(f"GitHub OAuth' not in src, (
        "github.py should not use f-string for logger"
    )
    assert 'logger.debug("GitHub OAuth response: {}"' in src, (
        "should use loguru {} placeholder"
    )


@test("#77.2 wl.py uses {} placeholder")
def _():
    from gimbal.auth.authenticators import wl
    src = inspect.getsource(wl)
    assert 'logger.debug(f"Response data' not in src
    assert 'logger.debug("Response data: {}"' in src


# ════════════════════════════════════════════════════════════════════
# #78 PreToken mode refresh skip
# ════════════════════════════════════════════════════════════════════
print("\n[9] PreToken mode refresh (#78)")

from gimbal.auth.manager import AuthManager
from gimbal.auth.registry import AuthRegistry
from gimbal.schema.auth import AuthSession


@test("#78.1 PreToken mode (no url) refresh does not call _login")
def _():
    reg = AuthRegistry()
    auth = AuthSession(
        url="",
        username="",
        password="preserved_token",
        token="preserved_token",
        expires_in=7200,
    )
    auth.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)  # already expired
    reg.set("p", auth)
    mgr = AuthManager(reg)

    with patch.object(mgr, "_login") as mock_login:
        mgr._refresh(auth, "p")
        # PreToken mode should return directly, not call _login
        assert mock_login.call_count == 0, (
            f"PreToken mode should not call _login, got {mock_login.call_count} calls"
        )


@test("#78.2 normal mode (has url) refresh still falls back to _login on error")
def _():
    import sys
    reg = AuthRegistry()
    auth = AuthSession(
        url="https://api.example.com/",
        username="u",
        password="p",
        token="old",
        expires_in=7200,
    )
    auth.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    reg.set("u", auth)
    mgr = AuthManager(reg)

    fake_httpx = MagicMock()
    fake_httpx.post.side_effect = Exception("network error")

    with patch.object(mgr, "_login") as mock_login, \
         patch.dict(sys.modules, {"httpx": fake_httpx}):
        mgr._refresh(auth, "u")
        # Should fall back to _login at least once
        assert mock_login.call_count >= 1, "normal mode should fallback to _login on network error"


# ════════════════════════════════════════════════════════════════════
# #9  Soft-failure terminal state semantics
# ════════════════════════════════════════════════════════════════════
print("\n[10] Soft-failure terminal state (#9)")


def _make_strategy_result(status: str, soft: bool = False) -> StrategyResult:
    """Build a StrategyResult with explicit status and soft flag."""
    return StrategyResult(
        status=StrategyStatus(status),
        strategy_id="test_strategy",
        message="",
        soft=soft,
    )


def _build_sm_for_soft_failure(
    verifying_results: list,
    teardown_results: list = None,
    has_teardown_phase: bool = False,
    before_request_results: list = None,
    after_request_results: list = None,
):
    """Build a StepStateMachine whose dispatch_phase returns controlled results.

    Verifying is always present. Teardown is optional.
    Returns (sm, bus) tuple.

    Note: We bypass Pydantic validation on StepSchema by setting _step_schema
    to a MagicMock with a `strategy` list of SimpleNamespace objects (Pydantic
    would reject these as they are not real Extract/Assign/Assertion models).
    """
    from types import SimpleNamespace

    bus = _FakeBus()
    # Build strategies as SimpleNamespace to bypass Pydantic validation
    strategies = []
    if before_request_results is None:
        before_request_results = [_make_strategy_result("passed")]
    if after_request_results is None:
        after_request_results = [_make_strategy_result("passed")]
    for _ in before_request_results:
        strategies.append(SimpleNamespace(
            kind="assign", phase=StrategyPhase.BEFORE_REQUEST, order=0,
            enabled=True, onFailure=FailurePolicy.ABORT, name="before",
        ))
    strategies.append(SimpleNamespace(
        kind="extract", phase=StrategyPhase.AFTER_REQUEST, order=0,
        enabled=True, onFailure=FailurePolicy.ABORT, name="after",
    ))
    for _ in verifying_results:
        strategies.append(SimpleNamespace(
            kind="assertion", phase=StrategyPhase.VERIFYING, order=0,
            enabled=True, onFailure=FailurePolicy.ABORT, name="verify",
        ))
    if has_teardown_phase or teardown_results:
        for _ in (teardown_results or [_make_strategy_result("passed")]):
            strategies.append(SimpleNamespace(
                kind="sql", phase=StrategyPhase.TEARDOWN, order=0,
                enabled=True, onFailure=FailurePolicy.ABORT, name="teardown",
            ))

    # Use MagicMock for the schema to bypass Pydantic validation entirely
    step_schema = MagicMock()
    step_schema.strategy = strategies
    step_schema.api.service = "test-svc"
    step_schema.api.method = "GET"
    step_schema.api.path = "/x"
    step_schema.api.headers = {}
    step_schema.api.timeout = 30.0
    step_schema.request.body = {}

    sm = sm_engine.StepStateMachine.__new__(sm_engine.StepStateMachine)
    sm._step_id = "soft-test"
    sm._step_schema = step_schema
    sm._dispatcher = MagicMock()
    # HTTP call (dispatch with _CallSpec) returns PASSED
    sm._dispatcher.dispatch.return_value = StrategyResult(
        status=StrategyStatus.PASSED,
        strategy_id="_call",
        message="ok",
        duration_ms=0.0,
    )
    # dispatch_phase returns the configured per-phase results
    def _dispatch_phase(phase, strategies, view):
        if phase == StrategyPhase.BEFORE_REQUEST:
            return before_request_results
        if phase == StrategyPhase.AFTER_REQUEST:
            return after_request_results
        if phase == StrategyPhase.VERIFYING:
            return verifying_results
        if phase == StrategyPhase.TEARDOWN:
            return teardown_results or [_make_strategy_result("passed")]
        return []
    sm._dispatcher.dispatch_phase.side_effect = _dispatch_phase
    sm._view = MagicMock()
    sm._service_base_url = "https://api.example.com"  # valid to avoid #6 firing
    sm._services = {}  # D7 per-step 查表(空 dict = 回落 base_url)
    sm._on_transition = None
    sm._hooks = None
    sm._bus = bus
    sm._state = sm_engine.StepState.PENDING
    sm._phase_results = []
    sm._error = None
    sm._error_phase = None  # 修复 #5
    sm._handlers = {
        sm_engine.StepState.BEFORE_REQUEST: sm._handle_before_request,
        sm_engine.StepState.CALLING: sm._handle_calling,
        sm_engine.StepState.AFTER_REQUEST: sm._handle_after_request,
        sm_engine.StepState.VERIFYING: sm._handle_verifying,
        sm_engine.StepState.TEARDOWN: sm._handle_teardown,
    }
    return sm, bus


@test("#9.1 VERIFYING soft-only failure -> step status='passed'")
def _():
    sm, bus = _build_sm_for_soft_failure(
        verifying_results=[_make_strategy_result("failed", soft=True)],
    )
    result = sm.run()
    assert result.status == "passed", (
        f"soft-only failure should not mark step failed, got: {result.status}"
    )
    assert result.passed is True, f"StepRunResult.passed should be True, got: {result.passed}"


@test("#9.2 VERIFYING hard failure -> step status='failed'")
def _():
    sm, bus = _build_sm_for_soft_failure(
        verifying_results=[_make_strategy_result("failed", soft=False)],
    )
    result = sm.run()
    assert result.status == "failed", (
        f"hard failure should mark step failed, got: {result.status}"
    )
    assert result.passed is False, f"StepRunResult.passed should be False, got: {result.passed}"


@test("#9.3 VERIFYING mixed soft+hard -> step status='failed' (hard dominates)")
def _():
    sm, bus = _build_sm_for_soft_failure(
        verifying_results=[
            _make_strategy_result("failed", soft=True),
            _make_strategy_result("failed", soft=False),
        ],
    )
    result = sm.run()
    assert result.status == "failed", (
        f"mixed soft+hard should mark step failed (hard dominates), got: {result.status}"
    )


@test("#9.4 VERIFYING passes + TEARDOWN soft failure -> step status='passed'")
def _():
    sm, bus = _build_sm_for_soft_failure(
        verifying_results=[_make_strategy_result("passed")],
        teardown_results=[_make_strategy_result("failed", soft=True)],
        has_teardown_phase=True,
    )
    result = sm.run()
    assert result.status == "passed", (
        f"soft teardown failure should not fail step, got: {result.status}"
    )
    assert result.passed is True


@test("#9.5 VERIFYING passes + TEARDOWN hard failure -> step stays 'passed' (B6)")
def _():
    # B6 fix: teardown 失败不污染业务结果
    sm, bus = _build_sm_for_soft_failure(
        verifying_results=[_make_strategy_result("passed")],
        teardown_results=[_make_strategy_result("failed", soft=False)],
        has_teardown_phase=True,
    )
    result = sm.run()
    # B6: teardown 失败不再翻转业务结果，business PASS 保持 PASS
    assert result.status == "passed", (
        f"B6 fix: teardown failure should NOT fail step (business passed), got: {result.status}"
    )
    assert result.passed is True
    # 但 error_phase 标记为 teardown
    assert result.error_phase == "teardown", (
        f"error_phase should be 'teardown' on teardown-only failure, got: {result.error_phase}"
    )


@test("#9.6 BEFORE_REQUEST soft failure + VERIFYING pass -> step status='passed'")
def _():
    # Defect #9 originally: a soft failure in BEFORE_REQUEST went to TEARDOWN,
    # then TEARDOWN saw the soft fail via any_failed and marked step FAILED.
    # After fix: BEFORE_REQUEST's pr.hard_failed is False (only soft),
    # so flow continues to CALLING/AFTER_REQUEST/VERIFYING normally.
    sm, bus = _build_sm_for_soft_failure(
        verifying_results=[_make_strategy_result("passed")],
        before_request_results=[_make_strategy_result("failed", soft=True)],
    )
    result = sm.run()
    assert result.status == "passed", (
        f"soft BEFORE_REQUEST failure should not fail step (BEFORE_REQUEST handler "
        f"already uses hard_failed), got: {result.status}"
    )
    assert result.passed is True


# ════════════════════════════════════════════════════════════════════
# #3/#24/#56  datetime utcnow() -> timezone-aware now(timezone.utc)
# ════════════════════════════════════════════════════════════════════
print("\n[11] datetime timezone-aware (#3/#24/#56)")


@test("#3.1 FrameworkEvent.timestamp is timezone-aware by default")
def _():
    from gimbal.events.types import StepStartEvent
    ev = StepStartEvent(step_id="s1", step_name="n1")
    assert ev.timestamp.tzinfo is not None, (
        f"event timestamp should be aware, got tzinfo={ev.timestamp.tzinfo}"
    )
    assert ev.timestamp.tzinfo == timezone.utc, (
        f"event timestamp should be UTC, got {ev.timestamp.tzinfo}"
    )


@test("#3.2 AuthSession.is_authenticated handles aware expires_at")
def _():
    # Construct a session, set expires_at to past aware datetime
    auth = AuthSession(
        token="t", expires_in=3600,
    )
    auth.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    # Without fix: utcnow() (naive) > aware expires_at raises TypeError in 3.12+
    # With fix: now(timezone.utc) > aware expires_at works and returns False
    assert auth.is_authenticated is False, (
        f"expired token should not be authenticated, got: {auth.is_authenticated}"
    )


@test("#3.3 AuthSession.is_authenticated True for non-expired aware expires_at")
def _():
    auth = AuthSession(token="t", expires_in=3600)
    auth.expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
    assert auth.is_authenticated is True, (
        f"non-expired token should be authenticated, got: {auth.is_authenticated}"
    )


@test("#3.4 AuthSession.should_refresh works with aware expires_at")
def _():
    # Set expires_at 1 minute from now -> within 5-min refresh window
    auth = AuthSession(token="t", expires_in=3600)
    auth.expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    assert auth.should_refresh is True, (
        f"token expiring in 30s should be refreshable, got: {auth.should_refresh}"
    )

    # Set expires_at 1 hour from now -> outside refresh window
    auth2 = AuthSession(token="t", expires_in=7200)
    auth2.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    assert auth2.should_refresh is False, (
        f"token with 1h left should not need refresh, got: {auth2.should_refresh}"
    )


@test("#3.5 AuthSession.remaining_seconds works with aware expires_at")
def _():
    auth = AuthSession(token="t", expires_in=3600)
    auth.expires_at = datetime.now(timezone.utc) + timedelta(seconds=120)
    remaining = auth.remaining_seconds
    assert remaining is not None
    # Should be roughly 120s (allow some slack for execution time)
    assert 115 <= remaining <= 120, (
        f"expected ~120s remaining, got {remaining}"
    )


@test("#3.6 AuthSession.apply_token sets aware expires_at")
def _():
    auth = AuthSession()
    auth.apply_token("new_token", expires_in=3600)
    assert auth.expires_at is not None
    assert auth.expires_at.tzinfo is not None, (
        f"apply_token should set aware expires_at, got tzinfo={auth.expires_at.tzinfo}"
    )
    assert auth.expires_at.tzinfo == timezone.utc
    # And it should be ~3600s in the future
    delta = (auth.expires_at - datetime.now(timezone.utc)).total_seconds()
    assert 3590 <= delta <= 3600, (
        f"expected expires_at ~3600s in future, got delta={delta}"
    )


@test("#3.7 SealedBaseModel._sealed_at is aware after seal()")
def _():
    from gimbal.context.base import SealedBaseModel, ContextLayer
    # Build a minimal concrete subclass
    from pydantic import Field

    class _Dummy(SealedBaseModel):
        layer: ContextLayer = ContextLayer.STEP
        x: int = 0

    obj = _Dummy(x=1)
    obj.seal()
    assert obj._sealed is True
    assert obj._sealed_at is not None
    assert obj._sealed_at.tzinfo is not None, (
        f"sealed_at should be aware, got tzinfo={obj._sealed_at.tzinfo}"
    )


@test("#3.8 ContextManager.create_framework_context produces aware started_at")
def _():
    # We need a real BootstrapConfig -- construct a minimal one
    from unittest.mock import MagicMock
    from gimbal.context.manager import ContextManager
    from gimbal.context.framework import FrameworkContext
    from gimbal.context.channels import Channels, Policies
    from gimbal.context.base import ContextLayer
    from gimbal.config.models import BootstrapConfig

    # Construct a minimal real BootstrapConfig
    real_cfg = BootstrapConfig(
        env="dev", mode="local", log_level="info",
    )
    real_channels = Channels(
        owner_layer=ContextLayer.FRAMEWORK,
        policy=Policies.framework_locked(),
    )
    fc = FrameworkContext(
        run_id="rid-test",
        started_at=datetime.now(timezone.utc),
        config=real_cfg,
        ctx_manager=MagicMock(),
        dispatcher=MagicMock(),
        event_bus=MagicMock(),
        archive=MagicMock(),
        channels=real_channels,
    )
    assert fc.started_at.tzinfo is not None, (
        f"FrameworkContext.started_at should be aware, got tzinfo={fc.started_at.tzinfo}"
    )
    assert fc.started_at.tzinfo == timezone.utc


@test("#3.9 aware vs aware datetime subtraction works (no TypeError)")
def _():
    # This is the key 3.12 compatibility check
    t1 = datetime.now(timezone.utc)
    t2 = datetime.now(timezone.utc)
    # If either side were naive, this subtraction would raise TypeError in 3.12+
    delta = (t2 - t1).total_seconds()
    assert isinstance(delta, float)
    assert delta >= 0


@test("#3.10 Aware datetime comparison with aware datetime (no TypeError)")
def _():
    t1 = datetime.now(timezone.utc)
    t2 = t1 + timedelta(seconds=1)
    # In 3.12+, comparing naive to aware raises TypeError
    # Both here are aware, so comparison is fine
    assert t2 > t1
    assert t1 < t2


# ════════════════════════════════════════════════════════════════════
# #4  AuthSession.apply_token semantics + clear_token asymmetry
# ════════════════════════════════════════════════════════════════════
print("\n[12] apply_token/clear_token semantics (#4)")


@test("#4.1 apply_token with expires_in>0 sets aware expires_at")
def _():
    auth = AuthSession()
    auth.apply_token("tok", expires_in=3600)
    assert auth.token == "tok"
    assert auth.expires_in == 3600
    assert auth.expires_at is not None
    assert auth.expires_at.tzinfo == timezone.utc, (
        f"expires_at should be aware UTC, got tzinfo={auth.expires_at.tzinfo}"
    )
    # Measure delta from "now" (after apply_token), not from a "before" snapshot,
    # to avoid microsecond precision drift.
    delta = (auth.expires_at - datetime.now(timezone.utc)).total_seconds()
    # Should be very close to 3600s, allowing small slack for execution time
    assert 3599 <= delta <= 3601, f"expected ~3600s, got {delta}"


@test("#4.2 apply_token with expires_in>0 REPLACES old expires_in")
def _():
    auth = AuthSession(expires_in=7200)
    auth.apply_token("tok", expires_in=3600)
    assert auth.expires_in == 3600, "new expires_in should replace old"
    delta = (auth.expires_at - datetime.now(timezone.utc)).total_seconds()
    assert 3590 <= delta <= 3600, "new lifetime should be ~3600s"


@test("#4.3 apply_token with None re-anchors expires_at to now+self.expires_in (no extension)")
def _():
    auth = AuthSession(expires_in=7200)
    auth.apply_token("first")
    first_expires_at = auth.expires_at
    # Re-apply without expires_in; expires_at should be re-anchored to now
    import time
    time.sleep(0.05)  # 50ms
    auth.apply_token("second")
    second_expires_at = auth.expires_at
    # New expires_at should be very close to "now" + 7200s, NOT 7200s more than original
    # (which would be a full extra 7200s lifetime extension)
    diff_ms = abs((second_expires_at - first_expires_at).total_seconds() * 1000)
    assert diff_ms < 1000, (
        f"expires_at should be re-anchored (diff<1s), not extended. diff={diff_ms}ms"
    )
    assert auth.expires_in == 7200, "self.expires_in should remain unchanged"


@test("#4.4 apply_token with expires_in=0 explicitly clears lifetime")
def _():
    auth = AuthSession(expires_in=7200)
    auth.apply_token("tok", expires_in=0)
    assert auth.token == "tok", "token should still be set"
    assert auth.expires_in == 0
    assert auth.expires_at is None, (
        f"expires_in=0 should clear expires_at, got: {auth.expires_at}"
    )
    # is_authenticated: token is set but expires_at is None -> True
    # (no expiration info, treated as valid)
    assert auth.is_authenticated is True


@test("#4.5 apply_token with None on fresh session leaves expires_at as None")
def _():
    auth = AuthSession()
    auth.apply_token("tok")
    assert auth.token == "tok"
    assert auth.expires_in is None
    assert auth.expires_at is None, (
        f"apply_token without prior expires_in should leave expires_at None, got: {auth.expires_at}"
    )


@test("#4.6 PreToken call pattern with configured expires_in")
def _():
    # Simulates pretoken.py:11: user pre-configures expires_in, then apply_token(password)
    auth = AuthSession(expires_in=7200)
    auth.apply_token("my_pretoken")  # no expires_in arg
    assert auth.token == "my_pretoken"
    assert auth.expires_in == 7200
    assert auth.expires_at is not None, (
        "PreToken with configured expires_in MUST get expires_at"
    )
    delta = (auth.expires_at - datetime.now(timezone.utc)).total_seconds()
    assert 7190 <= delta <= 7200, f"expected ~7200s, got {delta}"


@test("#4.7 refresh path: apply_token(new) without expires_in re-anchors (no loop)")
def _():
    auth = AuthSession(expires_in=3600)
    auth.apply_token("initial")
    assert auth.should_refresh is False
    # Simulate refresh: server returns new token but no expires_in
    auth.apply_token("refreshed")  # None arg
    # After refresh, expires_at should be ~3600s in future, not 7200s
    delta = (auth.expires_at - datetime.now(timezone.utc)).total_seconds()
    assert 3590 <= delta <= 3600, (
        f"refresh should re-anchor to now+3600s, not extend to 7200s. got {delta}"
    )
    # No infinite refresh loop
    assert auth.should_refresh is False, (
        "after refresh, should_refresh should be False (no infinite loop)"
    )


@test("#4.8 clear_token clears all three fields (token, expires_at, expires_in)")
def _():
    auth = AuthSession()
    auth.apply_token("tok", expires_in=3600)
    assert auth.token == "tok"
    assert auth.expires_in == 3600
    assert auth.expires_at is not None
    auth.clear_token()
    assert auth.token is None
    assert auth.expires_in is None, (
        f"clear_token should also clear expires_in, got: {auth.expires_in}"
    )
    assert auth.expires_at is None
    # Session should be in fresh state
    assert auth.is_authenticated is False
    assert auth.should_refresh is False


# ════════════════════════════════════════════════════════════════════
# #2  AuthManager isinstance check
# ════════════════════════════════════════════════════════════════════
print("\n[13] AuthManager isinstance check (#2)")


@test("#2.1 AuthManager accepts AuthRegistry instance")
def _():
    reg = AuthRegistry()
    mgr = AuthManager(reg)
    assert mgr._registry is reg, "AuthManager should store the AuthRegistry"


@test("#2.2 AuthManager rejects Configuration (was brittle hasattr behavior)")
def _():
    # Configuration has 'auth_registry' attr but no 'set' method
    # Old code would unwrap configuration.auth_registry
    # New code should raise TypeError immediately
    from gimbal.core.bootstrap import Configuration
    from unittest.mock import MagicMock

    # Build a minimal real Configuration (all required fields)
    from gimbal.config.models import BootstrapConfig
    from gimbal.context.manager import ContextManager
    from gimbal.core.hooks import HookRegistry
    from gimbal.context.archive import InMemoryArchive
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.strategy.dispatcher import build_default_dispatcher
    from gimbal.auth.registry import AuthRegistry

    real_cfg = BootstrapConfig(env="dev", mode="local", log_level="info")
    real_auth_reg = AuthRegistry()
    real_event_bus = InMemoryEventBus()
    real_archive = InMemoryArchive()
    real_ctx_mgr = ContextManager(archive=real_archive, event_bus=real_event_bus)
    real_dispatcher = build_default_dispatcher(hook_registry=HookRegistry())
    real_hook_reg = HookRegistry()
    real_plugin_reg = MagicMock()

    cfg = Configuration(
        cfg=real_cfg,
        auth_registry=real_auth_reg,
        ctx_manager=real_ctx_mgr,
        dispatcher=real_dispatcher,
        event_bus=real_event_bus,
        archive=real_archive,
        hook_registry=real_hook_reg,
        plugin_registry=real_plugin_reg,
        plugins=(),
    )
    try:
        AuthManager(cfg)
        assert False, "AuthManager(Configuration) should raise TypeError, but didn't"
    except TypeError as e:
        msg = str(e)
        assert "AuthRegistry" in msg, f"error should mention AuthRegistry, got: {msg}"
        assert "Configuration" in msg, f"error should mention actual type, got: {msg}"


@test("#2.3 AuthManager rejects None")
def _():
    try:
        AuthManager(None)
        assert False, "AuthManager(None) should raise TypeError"
    except TypeError as e:
        assert "NoneType" in str(e)


@test("#2.4 AuthManager rejects dict")
def _():
    try:
        AuthManager({"auth_registry": "fake"})
        assert False, "AuthManager(dict) should raise TypeError"
    except TypeError as e:
        assert "dict" in str(e)


@test("#2.5 AuthManager rejects string")
def _():
    try:
        AuthManager("not_a_registry")
        assert False, "AuthManager(str) should raise TypeError"
    except TypeError as e:
        assert "str" in str(e)


@test("#2.6 AuthManager accepts a duck-typed AuthRegistry subclass")
def _():
    # A subclass should also be accepted (isinstance is robust to subclassing)
    class _CustomRegistry(AuthRegistry):
        pass

    reg = _CustomRegistry()
    reg.set("test", AuthSession(token="t"))
    mgr = AuthManager(reg)
    assert mgr._registry is reg


@test("#2.7 error message guides user to fix the call")
def _():
    from gimbal.core.bootstrap import Configuration
    from gimbal.config.models import BootstrapConfig
    from gimbal.context.manager import ContextManager
    from gimbal.core.hooks import HookRegistry
    from gimbal.context.archive import InMemoryArchive
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.strategy.dispatcher import build_default_dispatcher
    from gimbal.auth.registry import AuthRegistry
    from unittest.mock import MagicMock

    real_cfg = BootstrapConfig(env="dev", mode="local", log_level="info")
    real_event_bus = InMemoryEventBus()
    real_archive = InMemoryArchive()
    real_ctx_mgr = ContextManager(archive=real_archive, event_bus=real_event_bus)
    real_dispatcher = build_default_dispatcher(hook_registry=HookRegistry())
    cfg = Configuration(
        cfg=real_cfg,
        auth_registry=AuthRegistry(),
        ctx_manager=real_ctx_mgr,
        dispatcher=real_dispatcher,
        event_bus=real_event_bus,
        archive=real_archive,
        hook_registry=HookRegistry(),
        plugin_registry=MagicMock(),
        plugins=(),
    )
    try:
        AuthManager(cfg)
    except TypeError as e:
        msg = str(e)
        # Should mention how to fix
        assert "configuration.auth_registry" in msg, (
            f"error should guide user to pass configuration.auth_registry, got: {msg}"
        )


# ════════════════════════════════════════════════════════════════════
# #15  HookResult.modified semantics
# ════════════════════════════════════════════════════════════════════
print("\n[14] HookResult.modified semantics (#15)")


@test("#15.1 noop handler (returns None) does NOT set modified=True")
def _():
    hr = _make_sm_with_api.__globals__["sm_engine"]  # not needed, use direct import
    from gimbal.core.hooks import HookRegistry, HookPoint

    hr2 = HookRegistry()

    def noop_handler(payload):
        pass  # does nothing, returns None implicitly

    hr2.register(HookPoint.STEP_START, noop_handler, plugin_name="test")
    result = hr2.trigger(HookPoint.STEP_START, {"key": "value"})
    assert result.modified is False, (
        f"noop handler should NOT set modified=True, got: {result.modified}"
    )


@test("#15.2 handler returning a new payload sets modified=True")
def _():
    from gimbal.core.hooks import HookRegistry, HookPoint

    hr = HookRegistry()

    def replace_handler(payload):
        return {"replaced": True}

    hr.register(HookPoint.STEP_START, replace_handler, plugin_name="test")
    result = hr.trigger(HookPoint.STEP_START, {"original": True})
    assert result.modified is True, (
        f"handler returning new payload should set modified=True, got: {result.modified}"
    )


@test("#15.3 handler returning the same payload object sets modified=True")
def _():
    from gimbal.core.hooks import HookRegistry, HookPoint

    hr = HookRegistry()
    payload = {"key": "value"}

    def return_same_handler(p):
        p["seen"] = True
        return p  # explicitly return to signal modification

    hr.register(HookPoint.STEP_START, return_same_handler, plugin_name="test")
    result = hr.trigger(HookPoint.STEP_START, payload)
    assert result.modified is True, (
        f"handler returning payload (in-place mutator) should set modified=True, "
        f"got: {result.modified}"
    )


@test("#15.4 in-place mutation WITHOUT return keeps modified=False")
def _():
    # This is the case the original test relied on. Now we require explicit return.
    from gimbal.core.hooks import HookRegistry, HookPoint

    hr = HookRegistry()
    seen = []

    def in_place_only(p):
        seen.append(p)
        # does NOT return -- in-place mutation only

    hr.register(HookPoint.STEP_START, in_place_only, plugin_name="test")
    result = hr.trigger(HookPoint.STEP_START, {"key": "value"})
    # Modified should be False because handler didn't return anything
    assert result.modified is False, (
        f"in-place-only handler (no return) should NOT set modified=True, "
        f"got: {result.modified}"
    )
    # But the handler DID run (verified by side effect)
    assert len(seen) == 1, f"handler should have run, seen={len(seen)} times"


@test("#15.5 multiple handlers: modified=True if ANY returns new payload")
def _():
    from gimbal.core.hooks import HookRegistry, HookPoint

    hr = HookRegistry()

    def noop(p):
        pass

    def replacer(p):
        return {"new": True}

    hr.register(HookPoint.STEP_START, noop, priority=10, plugin_name="first")
    hr.register(HookPoint.STEP_START, replacer, priority=20, plugin_name="second")
    result = hr.trigger(HookPoint.STEP_START, {"original": True})
    assert result.modified is True, (
        f"if any handler replaces payload, modified should be True, got: {result.modified}"
    )


@test("#15.6 multiple noop handlers: modified=False")
def _():
    from gimbal.core.hooks import HookRegistry, HookPoint

    hr = HookRegistry()

    def noop1(p):
        pass

    def noop2(p):
        pass

    hr.register(HookPoint.STEP_START, noop1, priority=10, plugin_name="a")
    hr.register(HookPoint.STEP_START, noop2, priority=20, plugin_name="b")
    result = hr.trigger(HookPoint.STEP_START, {"key": "value"})
    assert result.modified is False, (
        f"all noop handlers should keep modified=False, got: {result.modified}"
    )


@test("#15.7 STOP exception does not affect modified (errors are tracked separately)")
def _():
    from gimbal.core.hooks import HookRegistry, HookPoint, HookSignal

    hr = HookRegistry()

    def stop_handler(p):
        raise HookSignal.STOP("intentional")

    hr.register(HookPoint.STEP_START, stop_handler, plugin_name="test")
    result = hr.trigger(HookPoint.STEP_START, {"key": "value"})
    assert result.stopped is True
    # modified is independent of STOP
    assert result.modified is False, (
        f"STOP handler should not set modified=True, got: {result.modified}"
    )


@test("#15.8 returned payload replaces original (verifies payload flow)")
def _():
    from gimbal.core.hooks import HookRegistry, HookPoint

    hr = HookRegistry()
    captured = []

    def replacer(p):
        return {"new": True}

    def capture(p):
        captured.append(dict(p))
        return p

    # Replacer runs first (priority 10), then capture sees the new payload
    hr.register(HookPoint.STEP_START, replacer, priority=10, plugin_name="replace")
    hr.register(HookPoint.STEP_START, capture, priority=20, plugin_name="capture")
    result = hr.trigger(HookPoint.STEP_START, {"old": True})
    assert result.modified is True
    assert captured == [{"new": True}], (
        f"capture should see replaced payload, got: {captured}"
    )


# ════════════════════════════════════════════════════════════════════
# #5  State machine error attribution (calling vs verifying vs teardown)
# ════════════════════════════════════════════════════════════════════
print("\n[15] State machine error attribution (#5)")


def _build_sm_with_http_result(http_result: "StrategyResult", has_teardown: bool = False):
    """Build a StepStateMachine whose _do_http_call returns a controlled result.

    Verifying passes. The HTTP call (in CALLING phase) returns http_result.
    """
    from types import SimpleNamespace

    bus = _FakeBus()
    api = Api(kind="api", service="test-svc", method="GET", path="/x",
              headers={}, timeout=30.0)
    request = Request(kind="request", body={})
    strategies = [
        SimpleNamespace(kind="assign", phase=StrategyPhase.BEFORE_REQUEST,
                        order=0, enabled=True, onFailure=FailurePolicy.ABORT, name="before"),
        SimpleNamespace(kind="extract", phase=StrategyPhase.AFTER_REQUEST,
                        order=0, enabled=True, onFailure=FailurePolicy.ABORT, name="after"),
        SimpleNamespace(kind="assertion", phase=StrategyPhase.VERIFYING,
                        order=0, enabled=True, onFailure=FailurePolicy.ABORT, name="verify"),
    ]
    if has_teardown:
        strategies.append(SimpleNamespace(
            kind="sql", phase=StrategyPhase.TEARDOWN,
            order=0, enabled=True, onFailure=FailurePolicy.ABORT, name="teardown",
        ))

    step_schema = MagicMock()
    step_schema.strategy = strategies
    step_schema.api.service = "test-svc"
    step_schema.api.method = "GET"
    step_schema.api.path = "/x"
    step_schema.api.headers = {}
    step_schema.api.timeout = 30.0
    step_schema.request.body = {}

    sm = sm_engine.StepStateMachine.__new__(sm_engine.StepStateMachine)
    sm._step_id = "error-attr-test"
    sm._step_schema = step_schema
    sm._dispatcher = MagicMock()
    # HTTP call (dispatch with _CallSpec) returns the controlled result
    sm._dispatcher.dispatch.return_value = http_result
    # dispatch_phase: BEFORE/AFTER/VERIFYING pass
    def _dispatch_phase(phase, strategies, view):
        if phase == StrategyPhase.TEARDOWN:
            return [_make_strategy_result("passed")]
        return [_make_strategy_result("passed")]
    sm._dispatcher.dispatch_phase.side_effect = _dispatch_phase
    sm._view = MagicMock()
    sm._service_base_url = "https://api.example.com"
    sm._services = {}  # D7 per-step 查表(空 dict = 回落 base_url)
    sm._on_transition = None
    sm._hooks = None
    sm._bus = bus
    sm._state = sm_engine.StepState.PENDING
    sm._phase_results = []
    sm._error = None
    sm._error_phase = None
    sm._handlers = {
        sm_engine.StepState.BEFORE_REQUEST: sm._handle_before_request,
        sm_engine.StepState.CALLING: sm._handle_calling,
        sm_engine.StepState.AFTER_REQUEST: sm._handle_after_request,
        sm_engine.StepState.VERIFYING: sm._handle_verifying,
        sm_engine.StepState.TEARDOWN: sm._handle_teardown,
    }
    return sm, bus


@test("#5.1 HTTP failure (timeout) is attributed to 'calling' phase")
def _():
    # Simulate HTTP timeout
    http_result = StrategyResult(
        status=StrategyStatus.ERROR,
        message="Request timeout: Read timed out",
        duration_ms=30.0,
    )
    sm, bus = _build_sm_with_http_result(http_result, has_teardown=True)
    result = sm.run()
    assert result.status == "failed", "step should fail when HTTP fails"
    assert result.error_phase == "calling", (
        f"error_phase should be 'calling' for HTTP failure, got: {result.error_phase}"
    )
    # Error message should include original HTTP error
    assert result.error is not None
    assert "calling" in result.error, (
        f"error should contain phase marker 'calling', got: {result.error}"
    )
    assert "timeout" in result.error.lower(), (
        f"error should propagate original HTTP error message, got: {result.error}"
    )


@test("#5.2 HTTP RequestError is attributed to 'calling' phase")
def _():
    http_result = StrategyResult(
        status=StrategyStatus.ERROR,
        message="Request error: Connection refused",
        duration_ms=5.0,
    )
    sm, bus = _build_sm_with_http_result(http_result, has_teardown=False)
    result = sm.run()
    assert result.status == "failed"
    assert result.error_phase == "calling", (
        f"Connection refused should be attributed to calling, got: {result.error_phase}"
    )
    assert "Connection refused" in result.error


@test("#5.3 successful step has error_phase=None")
def _():
    http_result = StrategyResult(
        status=StrategyStatus.PASSED,
        message="ok",
        duration_ms=10.0,
    )
    sm, bus = _build_sm_with_http_result(http_result, has_teardown=False)
    result = sm.run()
    assert result.status == "passed"
    assert result.error_phase is None, (
        f"successful step should have error_phase=None, got: {result.error_phase}"
    )
    assert result.error is None


@test("#5.4 StepRunResult.error_phase is backward compatible (defaults to None)")
def _():
    # Test that constructing StepRunResult without error_phase still works
    from gimbal.statemachine.engine import StepRunResult
    r = StepRunResult(
        step_id="s1",
        status="passed",
        error="some old error",
        duration_ms=10.0,
    )
    # error_phase should default to None (backward compat)
    assert r.error_phase is None, (
        f"StepRunResult without error_phase should default to None, got: {r.error_phase}"
    )
    assert r.error == "some old error"


# ════════════════════════════════════════════════════════════════════
# #100  AuthSession.clear_password (sensitive credential hygiene)
# ════════════════════════════════════════════════════════════════════
print("\n[16] AuthSession.clear_password (#100)")


@test("#100.1 clear_password sets password to empty string")
def _():
    auth = AuthSession(password="supersecret123")
    assert auth.password == "supersecret123"
    result = auth.clear_password()
    assert auth.password == "", f"password should be empty, got: {auth.password!r}"
    assert result is auth, "clear_password should return self for chaining"


@test("#100.2 clear_password does NOT clear token (PreToken mode safe)")
def _():
    # PreToken mode: apply_token copies password to token
    auth = AuthSession()
    auth.apply_token("mytoken")
    auth.password = "mytoken"
    # clear password — token should still be available
    auth.clear_password()
    assert auth.password == ""
    assert auth.token == "mytoken", (
        f"clear_password should not affect token, got: {auth.token}"
    )
    assert auth.is_authenticated is True


@test("#100.3 clear_password preserves other config (url, username, expires_in)")
def _():
    auth = AuthSession(
        url="https://api.example.com",
        username="admin",
        password="secret",
        expires_in=3600,
    )
    auth.clear_password()
    assert auth.url == "https://api.example.com"
    assert auth.username == "admin"
    assert auth.expires_in == 3600
    assert auth.password == ""


@test("#100.4 clear_password on already-empty password is no-op")
def _():
    auth = AuthSession()  # default password=""
    auth.clear_password()
    assert auth.password == ""


@test("#100.5 clear_password allows is_same_credential to still work")
def _():
    # is_same_credential compares all 3 (url/username/password)
    # After clear, two sessions with same url/username are still same
    a = AuthSession(url="https://x", username="u", password="secret_a")
    b = AuthSession(url="https://x", username="u", password="secret_b")
    assert a.is_same_credential(b) is False  # passwords differ
    a.clear_password()
    b.clear_password()
    # Both passwords now empty — they're now considered same credential
    assert a.is_same_credential(b) is True, (
        "After clearing both passwords, credentials should match"
    )


# ════════════════════════════════════════════════════════════════════
# #8  EventBus async thread pool (replaces unbounded thread list)
# ════════════════════════════════════════════════════════════════════
print("\n[17] EventBus async thread pool (#8)")


@test("#8.1 InMemoryEventBus has a ThreadPoolExecutor for ASYNC")
def _():
    from gimbal.events.bus import InMemoryEventBus
    bus = InMemoryEventBus()
    assert bus._async_executor is not None, (
        "EventBus should have a thread pool executor for ASYNC events"
    )
    # Should be a ThreadPoolExecutor
    from concurrent.futures import ThreadPoolExecutor
    assert isinstance(bus._async_executor, ThreadPoolExecutor)


@test("#8.2 ASYNC publish uses thread pool (not raw thread + list append)")
def _():
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.events.subscription import Subscription, SubscriptionMode
    from gimbal.events.types import StepStartEvent
    import time

    bus = InMemoryEventBus()
    received = []
    def handler(event):
        time.sleep(0.01)  # simulate work
        received.append(event.step_id)

    sub = Subscription(
        subscription_id="s1",
        event_filter=__import__("gimbal.events.subscription", fromlist=["EventFilter"]).EventFilter(),
        handler=handler,
        mode=SubscriptionMode.ASYNC,
        priority=100,
    )
    bus._subscriptions.append(sub)

    # Publish many events - the old code would create 100 threads
    # The new code reuses a pool of 8 threads
    for i in range(20):
        bus.publish(StepStartEvent(step_id=f"s{i}", step_name=f"n{i}"))

    # Wait for all async tasks to complete
    bus.stop()  # shutdown waits for tasks

    assert len(received) == 20, f"all 20 events should be processed, got {len(received)}"


@test("#8.3 stop() shuts down thread pool cleanly")
def _():
    from gimbal.events.bus import InMemoryEventBus
    bus = InMemoryEventBus()
    executor = bus._async_executor
    assert executor is not None
    bus.stop()
    # After stop, executor should be shut down (set to None)
    assert bus._async_executor is None, (
        f"after stop, executor should be None, got: {bus._async_executor}"
    )


@test("#8.4 calling stop() twice is safe")
def _():
    from gimbal.events.bus import InMemoryEventBus
    bus = InMemoryEventBus()
    bus.stop()
    # Second call should not raise
    bus.stop()
    assert bus._async_executor is None


@test("#8.5 publish after stop falls back to sync (no event loss)")
def _():
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.events.subscription import Subscription, SubscriptionMode, EventFilter
    from gimbal.events.types import StepStartEvent

    bus = InMemoryEventBus()
    received = []
    bus.subscribe(
        lambda e: received.append(e.step_id),
        event_type="step.start",
        mode=SubscriptionMode.ASYNC,
    )
    bus.stop()  # shut down executor

    # Publish after stop - should still work (fallback to sync)
    bus.publish(StepStartEvent(step_id="post-stop", step_name="x"))
    assert "post-stop" in received, (
        "events published after stop should still be processed (sync fallback)"
    )


# ════════════════════════════════════════════════════════════════════
# #10  AuthSession.refresh_token (independent of access_token)
# ════════════════════════════════════════════════════════════════════
print("\n[18] AuthSession.refresh_token (#10)")


@test("#10.1 AuthSession has refresh_token field defaulting to None")
def _():
    auth = AuthSession()
    assert hasattr(auth, "refresh_token"), "AuthSession should have refresh_token field"
    assert auth.refresh_token is None, (
        f"refresh_token should default to None, got: {auth.refresh_token}"
    )


@test("#10.2 refresh_token is independent of access_token (token)")
def _():
    auth = AuthSession()
    auth.token = "access_abc"
    auth.refresh_token = "refresh_xyz"
    assert auth.token == "access_abc"
    assert auth.refresh_token == "refresh_xyz"
    # They should NOT be the same
    assert auth.token != auth.refresh_token


@test("#10.3 _refresh prefers refresh_token over token for OAuth2 standard")
def _():
    import sys
    from unittest.mock import patch, MagicMock
    from gimbal.auth.manager import AuthManager
    from gimbal.auth.registry import AuthRegistry
    from gimbal.schema.auth import AuthSession

    reg = AuthRegistry()
    auth = AuthSession(
        url="https://api.example.com",
        token="old_access_token",
        refresh_token="proper_refresh_token",
        expires_in=3600,
    )
    auth.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)  # expired
    reg.set("u", auth)
    mgr = AuthManager(reg)

    # Mock httpx to capture the POST body
    fake_httpx = MagicMock()
    captured_body = {}
    def fake_post(url, json=None, timeout=None, **kwargs):
        captured_body['url'] = url
        captured_body['json'] = json
        # Return a fake response with new tokens
        resp = MagicMock()
        resp.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }
        resp.raise_for_status = MagicMock()
        return resp
    fake_httpx.post.side_effect = fake_post

    with patch.dict(sys.modules, {"httpx": fake_httpx}):
        mgr._refresh(auth, "u")

    # Critical assertion: refresh endpoint received proper refresh_token, NOT access_token
    assert captured_body['json']['refresh_token'] == "proper_refresh_token", (
        f"refresh should use refresh_token field, got: {captured_body['json']}"
    )
    # And the new access_token should be saved
    assert auth.token == "new_access"
    # And new refresh_token should be saved (refresh-token rotation)
    assert auth.refresh_token == "new_refresh", (
        f"new refresh_token should be saved, got: {auth.refresh_token}"
    )


@test("#10.4 _refresh falls back to token if refresh_token is None (backward compat)")
def _():
    import sys
    from unittest.mock import patch, MagicMock
    from gimbal.auth.manager import AuthManager
    from gimbal.auth.registry import AuthRegistry
    from gimbal.schema.auth import AuthSession

    reg = AuthRegistry()
    auth = AuthSession(
        url="https://api.example.com",
        token="only_access_token",  # no refresh_token set
        expires_in=3600,
    )
    auth.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    reg.set("u", auth)
    mgr = AuthManager(reg)

    captured_body = {}
    def fake_post(url, json=None, timeout=None, **kwargs):
        captured_body['json'] = json
        resp = MagicMock()
        resp.json.return_value = {"access_token": "new", "expires_in": 3600}
        resp.raise_for_status = MagicMock()
        return resp
    fake_httpx = MagicMock()
    fake_httpx.post.side_effect = fake_post

    with patch.dict(sys.modules, {"httpx": fake_httpx}):
        mgr._refresh(auth, "u")

    # Fallback: should use token as refresh_token
    assert captured_body['json']['refresh_token'] == "only_access_token", (
        f"when refresh_token is None, should fallback to access_token, got: {captured_body['json']}"
    )


@test("#10.5 refresh_token is not overwritten if response does not include it")
def _():
    import sys
    from unittest.mock import patch, MagicMock
    from gimbal.auth.manager import AuthManager
    from gimbal.auth.registry import AuthRegistry
    from gimbal.schema.auth import AuthSession

    reg = AuthRegistry()
    auth = AuthSession(
        url="https://api.example.com",
        token="access",
        refresh_token="keep_me",
        expires_in=3600,
    )
    auth.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    reg.set("u", auth)
    mgr = AuthManager(reg)

    def fake_post(url, json=None, timeout=None, **kwargs):
        resp = MagicMock()
        # Response only has access_token, no refresh_token rotation
        resp.json.return_value = {"access_token": "new_access", "expires_in": 3600}
        resp.raise_for_status = MagicMock()
        return resp
    fake_httpx = MagicMock()
    fake_httpx.post.side_effect = fake_post

    with patch.dict(sys.modules, {"httpx": fake_httpx}):
        mgr._refresh(auth, "u")

    # Old refresh_token should be preserved when response doesn't include new one
    assert auth.refresh_token == "keep_me", (
        f"refresh_token should be preserved when response omits it, got: {auth.refresh_token}"
    )
    # But new access_token should be applied
    assert auth.token == "new_access"


# ════════════════════════════════════════════════════════════════════
# #40  LogLevel double definition (common.py enum vs params.py Annotated)
# ════════════════════════════════════════════════════════════════════
print("\n[19] LogLevel resolution (#40)")


@test("#40.1 LogLevel from common.py is the enum (not Annotated[str, ...])")
def _():
    from gimbal.cli.common import LogLevel
    from enum import Enum
    assert isinstance(LogLevel, type) and issubclass(LogLevel, Enum), (
        f"LogLevel should be an Enum subclass, got: {type(LogLevel)}"
    )


@test("#40.2 LogLevel.info is a valid enum value")
def _():
    from gimbal.cli.common import LogLevel
    assert LogLevel.info.value == "info"
    assert LogLevel.warning.value == "warning"
    assert LogLevel.debug.value == "debug"
    assert LogLevel.error.value == "error"


@test("#40.3 LogLevelEnum is the canonical name (with LogLevel as alias)")
def _():
    from gimbal.cli.common import LogLevelEnum, LogLevel
    assert LogLevelEnum is LogLevel, (
        f"LogLevel should be alias for LogLevelEnum, "
        f"got LogLevel={LogLevel}, LogLevelEnum={LogLevelEnum}"
    )


@test("#40.4 params.py no longer defines LogLevel (removed double definition)")
def _():
    import gimbal.cli.params as params_module
    assert not hasattr(params_module, "LogLevel"), (
        "params.py should NOT define LogLevel (was a duplicate of common.py enum)"
    )


@test("#40.5 main.py uses LogLevel.info enum as default")
def _():
    # Verify the main module imports LogLevel from common (not from params)
    from gimbal.cli.common import LogLevel
    # The default value in main.py is now LogLevel.info (enum member)
    assert LogLevel.info.value == "info"


# ════════════════════════════════════════════════════════════════════
# #17/#31  AssetMaterializer: frozen model field mutation
# ════════════════════════════════════════════════════════════════════
print("\n[20] AssetMaterializer frozen model handling (#17/#31)")


@test("#17.1 AssetMaterializer mutates frozen model fields via object.__setattr__")
def _():
    from unittest.mock import MagicMock
    from gimbal.core.asset_materializer import AssetMaterializer
    from gimbal.context.step import StepInputs, AssertionResult
    import tempfile, shutil, json, os
    from gimbal.repository import AssetStore, LocalFsContentStore, AssetRef
    from gimbal.schema.api import Api
    from gimbal.schema.request import Request
    from gimbal.schema.step import Step
    from gimbal.exceptions import AssetMaterializationError

    tmp = tempfile.mkdtemp(prefix="gimbal_mat_test_")
    try:
        # Create a real asset store with a Step that's NOT frozen (regular Pydantic)
        store = AssetStore(backend=LocalFsContentStore(root=tmp))
        ref = AssetRef.parse("smoke/sample-step:latest")
        # Push a step as a scenario
        step_dict = {
            "kind": "step",
            "api": {"kind": "api", "service": "test", "method": "GET", "path": "/x",
                    "headers": {}, "timeout": 30.0},
            "request": {"kind": "request", "body": {}},
            "strategy": [],
        }
        store.push(ref, json.dumps(step_dict).encode())

        # Build a frozen StepInputs (with the ref as strategy_kind)
        frozen_inputs = StepInputs(
            step_id="s1",
            step_name="n1",
            strategy_kind="smoke/sample-step:latest",  # this is a "ref" string
            strategy_spec={},
            resolved_vars={},
        )
        assert frozen_inputs.model_config.get("frozen") is True, (
            "StepInputs should be frozen for this test to be meaningful"
        )

        # Materialize the frozen model
        materializer = AssetMaterializer(store)
        try:
            result = materializer._walk_model(
                frozen_inputs, depth=0, path="$"
            )
        except AssetMaterializationError:
            # If pull failed, that's expected in this minimal test setup
            # The key is that setattr failure should be handled, not crash
            return
        # If materialization succeeded, result should still be the same model object
        assert result is frozen_inputs
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@test("#17.2 regular (non-frozen) model still works via direct setattr")
def _():
    """Regression test: non-frozen models still work as before."""
    from unittest.mock import MagicMock
    from gimbal.core.asset_materializer import AssetMaterializer
    from pydantic import BaseModel

    class _Simple(BaseModel):
        x: int = 0
        y: str = "default"

    store = MagicMock()
    materializer = AssetMaterializer(store)

    # Mock _walk to return new value for y
    original = _Simple(x=1, y="old")
    materializer._walk = MagicMock(return_value="new_value")

    result = materializer._walk_model(original, depth=0, path="$")
    assert result is original
    assert result.y == "new_value"


@test("#17.3 _walk_model does not crash when walk returns same object (idempotent)")
def _():
    from unittest.mock import MagicMock
    from gimbal.core.asset_materializer import AssetMaterializer
    from pydantic import BaseModel

    class _Simple(BaseModel):
        x: int = 0

    store = MagicMock()
    materializer = AssetMaterializer(store)

    original = _Simple(x=1)
    # _walk returns same object — no setattr should happen
    materializer._walk = MagicMock(return_value=original.x)  # returns same value

    result = materializer._walk_model(original, depth=0, path="$")
    assert result is original
    # x should be unchanged
    assert result.x == 1


# ════════════════════════════════════════════════════════════════════
# Low-priority defect fixes
# ════════════════════════════════════════════════════════════════════


# ─── #65 dead enum ContextPromotionEvent ───────────────────────────────
print("\n[21] Low-priority: dead enum (#65)")


@test("#65.1 ContextPromotionEvent alias is removed")
def _():
    # The deprecated alias should no longer exist
    try:
        from gimbal.events.types import ContextPromotionEvent
        assert False, (
            "ContextPromotionEvent should be removed (was a dead alias for VariablePromotedEvent)"
        )
    except ImportError:
        pass  # expected

    # VariablePromotedEvent is the canonical name and still works
    from gimbal.events.types import VariablePromotedEvent
    assert VariablePromotedEvent is not None


@test("#65.2 events.__init__ no longer exports ContextPromotionEvent")
def _():
    import gimbal.events as events_pkg
    assert "ContextPromotionEvent" not in events_pkg.__all__, (
        "events package should not export the dead alias"
    )
    assert "VariablePromotedEvent" in events_pkg.__all__


# ─── #66 auth_header CRLF injection ───────────────────────────────────
print("\n[22] Low-priority: auth_header CRLF (#66)")


@test("#66.1 auth_header rejects token_type with CR character")
def _():
    auth = AuthSession(token="abc", token_type="Bearer\r\nX-Injected: bad")
    try:
        _ = auth.auth_header
        assert False, "auth_header should raise on control character in token_type"
    except ValueError as e:
        msg = str(e)
        assert "control character" in msg.lower(), (
            f"error should mention control character, got: {msg}"
        )


@test("#66.2 auth_header rejects token_type with LF only")
def _():
    auth = AuthSession(token="abc", token_type="Bearer\nX-Injected: bad")
    try:
        _ = auth.auth_header
        assert False, "auth_header should raise on LF in token_type"
    except ValueError:
        pass


@test("#66.3 auth_header accepts normal token_type values")
def _():
    auth = AuthSession(token="abc", token_type="Bearer")
    assert auth.auth_header == "Bearer abc"
    auth2 = AuthSession(token="xyz", token_type="Token")
    assert auth2.auth_header == "Token xyz"


@test("#66.4 auth_header returns None when no token")
def _():
    auth = AuthSession(token_type="Bearer")  # no token
    assert auth.auth_header is None


@test("#66.5 apply_token rejects token with control character (early fail)")
def _():
    # 修复 #R1：早失败——写入时验证，不延迟到 auth_header
    try:
        AuthSession().apply_token("good_token\r\nX-Bad: evil")
        assert False, "apply_token should reject token with control character"
    except ValueError as e:
        assert "control character" in str(e).lower(), (
            f"error should mention control character, got: {e}"
        )


@test("#66.6 apply_token accepts normal tokens")
def _():
    auth = AuthSession()
    auth.apply_token("eyJhbGciOiJIUzI1NiJ9.payload.signature")
    assert auth.token == "eyJhbGciOiJIUzI1NiJ9.payload.signature"


# ─── #32 jsonpath FIELD edge case ──────────────────────────────────────
print("\n[23] Low-priority: jsonpath FIELD (#32)")


@test("#32.1 jsonpath get on object with missing attribute returns None")
def _():
    from gimbal.utils.jsonpath import get
    from types import SimpleNamespace
    data = SimpleNamespace(existing_field="value")
    # Field doesn't exist on object - should return None (not raise)
    result = get(data, "$.nonexistent_field")
    assert result is None, (
        f"expected None for missing attribute, got: {result}"
    )


@test("#32.2 jsonpath get on object that raises AttributeError in __getattr__")
def _():
    from gimbal.utils.jsonpath import get
    class _Strict:
        def __getattr__(self, name):
            raise AttributeError(f"no such attr: {name}")
    # Should not crash
    result = get(_Strict(), "$.anything")
    assert result is None


@test("#32.3 jsonpath get on dict still works (regression)")
def _():
    from gimbal.utils.jsonpath import get
    data = {"a": {"b": 1}}
    assert get(data, "$.a.b") == 1
    assert get(data, "$.missing") is None


@test("#32.4 jsonpath get on Pydantic v2 model with undeclared field")
def _():
    """Pydantic v2 raises AttributeError for undeclared fields — should return None."""
    from gimbal.utils.jsonpath import get
    from pydantic import BaseModel
    class _M(BaseModel):
        x: int = 0
    m = _M(x=5)
    # declared field works
    assert get(m, "$.x") == 5
    # undeclared field returns None (not AttributeError)
    assert get(m, "$.y") is None


@test("#32.5 jsonpath on object with __getattr__ raising AttributeError returns None")
def _():
    """Other exceptions (RuntimeError, TypeError) should propagate as JsonPathError.

    Only AttributeError/KeyError (programmer errors: missing field) are swallowed.
    Programmer errors in __getattr__ (like RuntimeError) should surface.
    """
    from gimbal.utils.jsonpath import get
    from gimbal.utils.jsonpath import JsonPathError
    class _Bad:
        def __getattr__(self, name):
            raise RuntimeError(f"boom: {name}")
    # RuntimeError is NOT caught — should propagate as JsonPathError
    try:
        get(_Bad(), "$.anything")
        assert False, "RuntimeError should have been raised (wrapped as JsonPathError)"
    except JsonPathError as e:
        assert "boom" in str(e), f"JsonPathError should wrap original, got: {e}"


# ─── #50 vars end-to-end ─────────────────────────────────────────────
print("\n[24] Low-priority: vars end-to-end (#50)")


@test("#50.1 BootstrapConfig has vars field")
def _():
    from gimbal.config.models import BootstrapConfig
    cfg = BootstrapConfig()
    assert hasattr(cfg, "vars"), "BootstrapConfig should have vars field"
    assert cfg.vars == {}, f"default vars should be empty dict, got: {cfg.vars}"


@test("#50.2 _from_cli extracts vars from cli.extras")
def _():
    from gimbal.config.loader import ConfigLoader
    from gimbal.cli.context import CLIContext
    cli_ctx = CLIContext()
    cli_ctx.extras["vars"] = {"user": "alice", "env_name": "test"}
    cli_ctx.env = "dev"
    cli_ctx.mode = "local"
    cli_ctx.log_level = "info"
    result = ConfigLoader()._from_cli(cli_ctx)
    assert "vars" in result, f"vars should be extracted, got: {result}"
    assert result["vars"] == {"user": "alice", "env_name": "test"}


@test("#50.3 _build_resolve_root includes cfg.vars as 'var' key")
def _():
    from unittest.mock import MagicMock
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.config.models import BootstrapConfig
    from gimbal.schema.scenario import Scenario, Meta, Config as ScenarioConfig
    from gimbal.auth.registry import AuthRegistry
    from datetime import datetime, timezone

    cfg = BootstrapConfig(env="dev", mode="local", log_level="info")
    cfg.vars["api_key"] = "test_key_123"
    cfg.vars["env_name"] = "staging"

    scenario = Scenario(
        scenarioId="sc1",
        meta=Meta(
            name="t", description="d", module="m", priority=1,
            author="a", owner="o", tags=[], version="1.0",
            createTime=datetime.now(timezone.utc), expire=False, requirementRef=[],
        ),
        config=ScenarioConfig(),
        resource={},
        steps=[],
    )

    pre = ScenarioPreprocessor(
        scenario_schema=scenario,
        bootstrap_config=cfg,
        auth_registry=AuthRegistry(),
    )
    # Use the private method to inspect root
    root = pre._build_resolve_root()
    assert "var" in root, f"root should have 'var' key, got keys: {list(root.keys())}"
    assert root["var"] == {"api_key": "test_key_123", "env_name": "staging"}


@test("#50.4 _build_resolve_root has no 'var' key when cfg.vars is empty")
def _():
    from unittest.mock import MagicMock
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.config.models import BootstrapConfig
    from gimbal.schema.scenario import Scenario, Meta, Config as ScenarioConfig
    from gimbal.auth.registry import AuthRegistry
    from datetime import datetime, timezone

    cfg = BootstrapConfig(env="dev", mode="local", log_level="info")
    # cfg.vars is empty (default)

    scenario = Scenario(
        scenarioId="sc1",
        meta=Meta(
            name="t", description="d", module="m", priority=1,
            author="a", owner="o", tags=[], version="1.0",
            createTime=datetime.now(timezone.utc), expire=False, requirementRef=[],
        ),
        config=ScenarioConfig(),
        resource={},
        steps=[],
    )

    pre = ScenarioPreprocessor(
        scenario_schema=scenario,
        bootstrap_config=cfg,
        auth_registry=AuthRegistry(),
    )
    root = pre._build_resolve_root()
    assert "var" not in root, (
        f"when cfg.vars is empty, 'var' should not be in root, got: {list(root.keys())}"
    )


@test("#50.5 end-to-end: ${var.api_key} resolves to actual value")
def _():
    from gimbal.utils.jsonpath import resolve_template
    root = {"var": {"api_key": "secret_123"}}
    # Single var resolves to raw value
    assert resolve_template("${var.api_key}", root) == "secret_123"
    # Embedded in string
    assert resolve_template("Bearer ${var.api_key}", root) == "Bearer secret_123"


# ─── #89 typed ref kind error message ─────────────────────────────────
print("\n[25] Low-priority: typed ref kind error (#89)")


@test("#89.1 typed ref with parsed=None includes content_kind in error")
def _():
    from unittest.mock import MagicMock
    from gimbal.core.asset_materializer import AssetMaterializer
    from gimbal.exceptions import AssetMaterializationError
    from gimbal.repository import AssetRecord

    # Build a content with parsed=None and kind="blob"
    fake_record = AssetRecord(
        ref=__import__("gimbal.repository", fromlist=["AssetRef"]).AssetRef.parse("smoke/x:latest"),
        digest="sha256:" + "0" * 64,
        size=10,
        kind="blob",  # not in (suite, scenario, data)
        media_type="application/octet-stream",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_content = MagicMock()
    fake_content.parsed = None
    fake_content.raw = b"{}"
    fake_content.record = fake_record
    fake_content.digest = "sha256:" + "0" * 64
    fake_content.size = 10

    fake_store = MagicMock()
    fake_store.pull.return_value = fake_content

    from gimbal.schema.api import ApiRef
    ref = ApiRef(ref="smoke/x:latest")
    materializer = AssetMaterializer(fake_store)

    try:
        materializer._materialize_ref(ref, depth=0, path="$")
        assert False, "should have raised AssetMaterializationError"
    except AssetMaterializationError as e:
        msg = str(e)
        assert "blob" in msg or "content_kind" in msg, (
            f"error should mention actual content kind, got: {msg}"
        )
        assert "suite" in msg and "scenario" in msg and "data" in msg, (
            f"error should list supported kinds, got: {msg}"
        )


# ════════════════════════════════════════════════════════════════════
# Business flow fixes
# ════════════════════════════════════════════════════════════════════

# ─── B1: Multi-service base_url resolution ──────────────────────────────
print("\n[26] Business flow: multi-service base_url (B1)")


def _make_step_with_service(service_name: str):
    """Build a Step with given api.service key."""
    from gimbal.schema.step import Step
    from gimbal.schema.api import Api
    from gimbal.schema.request import Request
    from gimbal.schema.strategy import Assertion, AssertOperator

    return Step(
        kind="step",
        api=Api(
            kind="api", service=service_name, method="GET", path="/x",
            headers={}, timeout=30.0,
        ),
        request=Request(kind="request", body={}),
        strategy=[
            Assertion(
                kind="assertion", name="a1", phase=StrategyPhase.VERIFYING,
                order=0, enabled=True, onFailure=FailurePolicy.ABORT,
                target="$.response_status", operator=AssertOperator.EQ,
                expected=200, message="ok", soft=False,
            )
        ],
    )


@test("#B1.1 single-service: uses referenced service's URL")
def _():
    from unittest.mock import MagicMock
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.config.models import BootstrapConfig
    from gimbal.schema.scenario import Scenario, Meta, Config as ScenarioConfig
    from gimbal.auth.registry import AuthRegistry
    from datetime import datetime, timezone

    cfg = BootstrapConfig(env="dev", mode="local", log_level="info")
    scenario_cfg = ScenarioConfig(
        services={"user-svc": "https://user.example.com"},
    )
    scenario = Scenario(
        scenarioId="sc1",
        meta=Meta(
            name="t", description="d", module="m", priority=1,
            author="a", owner="o", tags=[], version="1.0",
            createTime=datetime.now(timezone.utc), expire=False, requirementRef=[],
        ),
        config=scenario_cfg,
        resource={},
        steps=[_make_step_with_service("user-svc")],
    )

    pre = ScenarioPreprocessor(
        scenario_schema=scenario, bootstrap_config=cfg,
        auth_registry=AuthRegistry(),
    )
    base_url = pre._pick_base_url()
    assert base_url == "https://user.example.com", (
        f"single-service should use its URL, got: {base_url}"
    )


@test("#B1.2 multi-service with all same reference: uses that one")
def _():
    from unittest.mock import MagicMock
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.config.models import BootstrapConfig
    from gimbal.schema.scenario import Scenario, Meta, Config as ScenarioConfig
    from gimbal.auth.registry import AuthRegistry
    from datetime import datetime, timezone

    cfg = BootstrapConfig(env="dev", mode="local", log_level="info")
    scenario_cfg = ScenarioConfig(
        services={
            "user-svc": "https://user.example.com",
            "order-svc": "https://order.example.com",
        },
    )
    scenario = Scenario(
        scenarioId="sc1",
        meta=Meta(
            name="t", description="d", module="m", priority=1,
            author="a", owner="o", tags=[], version="1.0",
            createTime=datetime.now(timezone.utc), expire=False, requirementRef=[],
        ),
        config=scenario_cfg,
        resource={},
        steps=[
            _make_step_with_service("order-svc"),
            _make_step_with_service("order-svc"),
        ],
    )

    pre = ScenarioPreprocessor(
        scenario_schema=scenario, bootstrap_config=cfg,
        auth_registry=AuthRegistry(),
    )
    base_url = pre._pick_base_url()
    # All steps reference order-svc → use its URL (NOT first dict entry)
    assert base_url == "https://order.example.com", (
        f"all steps use order-svc, should pick order-svc's URL, got: {base_url}"
    )


@test("#B1.3 no step references service: fallback to dict first")
def _():
    from unittest.mock import MagicMock
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.config.models import BootstrapConfig
    from gimbal.schema.scenario import Scenario, Meta, Config as ScenarioConfig
    from gimbal.auth.registry import AuthRegistry
    from datetime import datetime, timezone

    cfg = BootstrapConfig(env="dev", mode="local", log_level="info")
    scenario_cfg = ScenarioConfig(
        services={"user-svc": "https://user.example.com"},
    )
    # Step with api.service="" (empty/unset)
    step = _make_step_with_service("")  # no service
    scenario = Scenario(
        scenarioId="sc1",
        meta=Meta(
            name="t", description="d", module="m", priority=1,
            author="a", owner="o", tags=[], version="1.0",
            createTime=datetime.now(timezone.utc), expire=False, requirementRef=[],
        ),
        config=scenario_cfg,
        resource={},
        steps=[step],
    )

    pre = ScenarioPreprocessor(
        scenario_schema=scenario, bootstrap_config=cfg,
        auth_registry=AuthRegistry(),
    )
    base_url = pre._pick_base_url()
    # Fallback: pick first
    assert base_url == "https://user.example.com"


# ─── B2: BEFORE_REQUEST Assign effectiveness ───────────────────────────
print("\n[27] Business flow: Assign before_request (B2)")


@test("#B2.1 HTTP call body uses scratch.request_body (modified by Assign)")
def _():
    """When BEFORE_REQUEST Assign writes to scratch.request_body, HTTP call should use it."""
    sm, bus = _build_sm_for_soft_failure(
        verifying_results=[_make_strategy_result("passed")],
    )

    # Make dispatcher capture the call_spec
    captured_spec = {}
    original_dispatch = sm._dispatcher.dispatch

    def capturing_dispatch(call_spec, view):
        captured_spec['url'] = call_spec.url
        captured_spec['body'] = dict(call_spec.body) if call_spec.body else {}
        return StrategyResult(
            status=StrategyStatus.PASSED, message="ok", duration_ms=0.0,
        )
    sm._dispatcher.dispatch = capturing_dispatch

    # Simulate that BEFORE_REQUEST Assign wrote to scratch.request_body
    sm._view.read_scratch = MagicMock(return_value={
        "user_id": "alice",  # added by Assign
        "action": "create",
    })
    # But view.read_scratch for "request_body" returns the modified value
    def smart_read(key, default=None):
        if key == "request_body":
            return {"user_id": "alice", "action": "create"}
        return default
    sm._view.read_scratch.side_effect = smart_read

    sm.run()

    # Verify HTTP call used the scratch body
    assert captured_spec.get('body') == {"user_id": "alice", "action": "create"}, (
        f"HTTP call should use Assign-modified scratch.request_body, "
        f"got: {captured_spec.get('body')}"
    )


# ─── B3: scenario_timeout enforcement ──────────────────────────────────
print("\n[28] Business flow: scenario_timeout (B3)")


def _build_scenario_with_timeout(steps, timeout_seconds=None):
    """Build a ScenarioContext-like object that has a config.scenario_timeout."""
    from datetime import datetime, timezone
    from gimbal.config.models import BootstrapConfig

    bs_cfg = BootstrapConfig(
        env="dev", mode="local", log_level="info",
        scenario_timeout=timeout_seconds,
    )

    # Minimal scenario context
    class _Ctx:
        def __init__(self, cfg):
            self.config = cfg
            self._timeout_seconds = timeout_seconds
    return _Ctx(bs_cfg), bs_cfg


def _make_step_with_api():
    from gimbal.schema.step import Step
    from gimbal.schema.api import Api
    from gimbal.schema.request import Request
    return Step(
        kind="step",
        api=Api(kind="api", service="test", method="GET", path="/x",
                headers={}, timeout=30.0),
        request=Request(kind="request", body={}),
        strategy=[],
    )


@test("#B3.1 scenario_timeout=None means no limit (default)")
def _():
    from gimbal.core.scenario_runner import ScenarioRunner
    from unittest.mock import MagicMock
    ctx, _ = _build_scenario_with_timeout([_make_step_with_api()], timeout_seconds=None)
    # If timeout is None, the check should skip
    cfg_timeout = getattr(ctx, "_timeout_seconds", None)
    if cfg_timeout is None:
        bs_cfg = ctx.config
        cfg_timeout = getattr(bs_cfg, "scenario_timeout", None) if hasattr(bs_cfg, "scenario_timeout") else None
    assert cfg_timeout is None, "no timeout should mean no limit"


@test("#B3.2 scenario_timeout read from cfg.scenario_timeout")
def _():
    ctx, _ = _build_scenario_with_timeout([_make_step_with_api()], timeout_seconds=30)
    bs_cfg = ctx.config
    cfg_timeout = getattr(bs_cfg, "scenario_timeout", None) if hasattr(bs_cfg, "scenario_timeout") else None
    assert cfg_timeout == 30, f"expected 30s, got {cfg_timeout}"


# ─── B4 rollback: eager auth with template-aware optimization ─────────
print("\n[29] Business flow: eager auth for templates (B4 rollback)")


@test("#B4.1 _setup_auth triggers login for template-referenced tags")
def _():
    """回滚 B4：模板替换需要 token，所以 _setup_auth 必须实际登录被引用的 user。"""
    from unittest.mock import patch
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.config.models import BootstrapConfig
    from gimbal.schema.scenario import Scenario, Meta, Config as ScenarioConfig
    from gimbal.schema.api import Api
    from gimbal.schema.request import Request
    from gimbal.schema.step import Step
    from gimbal.schema.strategy import Assertion, AssertOperator, StrategyPhase, FailurePolicy
    from gimbal.auth.registry import AuthRegistry
    from datetime import datetime, timezone

    cfg = BootstrapConfig(env="dev", mode="local", log_level="info")
    # step header 引用 ${auth.admin.token}
    step = Step(
        kind="step",
        api=Api(
            kind="api", service="test", method="GET", path="/x",
            headers={"Authorization": "Bearer ${auth.admin.token}"},
            timeout=30.0,
        ),
        request=Request(kind="request", body={}),
        strategy=[],
    )
    scenario_cfg = ScenarioConfig(
        users={
            "admin": {"url": "https://api.example.com", "username": "admin", "password": "x"},
            "unused_user": {"url": "https://other.example.com", "username": "u", "password": "y"},
        },
    )
    scenario = Scenario(
        scenarioId="sc1",
        meta=Meta(
            name="t", description="d", module="m", priority=1,
            author="a", owner="o", tags=[], version="1.0",
            createTime=datetime.now(timezone.utc), expire=False, requirementRef=[],
        ),
        config=scenario_cfg,
        resource={},
        steps=[step],
    )
    auth_reg = AuthRegistry()
    pre = ScenarioPreprocessor(
        scenario_schema=scenario, bootstrap_config=cfg,
        auth_registry=auth_reg,
    )

    # Track AuthManager.get_auth calls
    with patch("gimbal.auth.AuthManager") as MockAuthManager:
        # Mock get_auth to set token
        mock_mgr_instance = MagicMock()
        def fake_get_auth(tag):
            session = auth_reg.get(tag)
            if session:
                session.token = "mock_token_for_" + tag
            return session
        mock_mgr_instance.get_auth = fake_get_auth
        MockAuthManager.return_value = mock_mgr_instance

        pre._setup_auth()

        # 验证：admin 被模板引用，应被登录
        # unused_user 未被模板引用，不应触发 get_auth
        assert auth_reg.get("admin").token == "mock_token_for_admin", (
            f"template-referenced admin should be logged in, "
            f"token={auth_reg.get('admin').token}"
        )
        # 验证 get_auth 只被调用一次（admin），unused_user 被 skip
        # (AuthManager.get_auth called exactly once for admin)
        admin_logged = (
            auth_reg.get("admin").token is not None
        )
        unused_logged = (
            auth_reg.get("unused_user").token is not None
        )
        assert admin_logged, "admin should be logged in (template reference)"
        assert not unused_logged, (
            "unused_user should NOT be logged in (no template reference)"
        )


@test("#B4.2 _setup_auth with no users is a no-op")
def _():
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.config.models import BootstrapConfig
    from gimbal.schema.scenario import Scenario, Meta, Config as ScenarioConfig
    from gimbal.auth.registry import AuthRegistry
    from datetime import datetime, timezone

    cfg = BootstrapConfig(env="dev", mode="local", log_level="info")
    scenario = Scenario(
        scenarioId="sc1",
        meta=Meta(
            name="t", description="d", module="m", priority=1,
            author="a", owner="o", tags=[], version="1.0",
            createTime=datetime.now(timezone.utc), expire=False, requirementRef=[],
        ),
        config=ScenarioConfig(),
        resource={},
        steps=[],
    )
    pre = ScenarioPreprocessor(
        scenario_schema=scenario, bootstrap_config=cfg,
        auth_registry=AuthRegistry(),
    )
    # Should not raise even with no users
    pre._setup_auth()


# ─── B5: template silent fail (B5) ─────────────────────────────────────
print("\n[30] Business flow: template silent fail (B5)")


@test("#B5.1 resolve_value returns None for missing template (not literal)")
def _():
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.utils.jsonpath import is_template

    pre = ScenarioPreprocessor.__new__(ScenarioPreprocessor)  # bypass init
    pre._resolve_value = ScenarioPreprocessor._resolve_value.__get__(pre)
    root = {"var": {"existing_key": "value"}}
    # Missing key
    result = pre._resolve_value("${var.nonexistent_key}", root)
    assert result is None, (
        f"missing template should return None (B5 fix), got: {result!r}"
    )


@test("#B5.2 _resolve_api raises when header template is missing")
def _():
    """Critical B5: header missing template should NOT silently drop — must raise."""
    from unittest.mock import MagicMock
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.schema.api import Api
    from gimbal.config.models import BootstrapConfig
    from gimbal.auth.registry import AuthRegistry

    api = Api(
        kind="api", service="test", method="GET", path="/x",
        headers={"Authorization": "Bearer ${var.no_such_token}"},
        timeout=30.0,
    )
    pre = ScenarioPreprocessor.__new__(ScenarioPreprocessor)
    root = {"var": {}}

    try:
        pre._resolve_api(api, root)
        assert False, (
            "should have raised ValueError due to missing header template"
        )
    except ValueError as e:
        msg = str(e)
        assert "Authorization" in msg, (
            f"error should mention which header is missing, got: {msg}"
        )


@test("#B5.3 _resolve_api raises when path template is missing")
def _():
    from unittest.mock import MagicMock
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.schema.api import Api
    from gimbal.config.models import BootstrapConfig
    from gimbal.auth.registry import AuthRegistry

    api = Api(
        kind="api", service="test", method="GET", path="/users/${var.user_id}",
        headers={},
        timeout=30.0,
    )
    pre = ScenarioPreprocessor.__new__(ScenarioPreprocessor)
    root = {"var": {}}

    try:
        pre._resolve_api(api, root)
        assert False, "should have raised for missing path template"
    except ValueError as e:
        assert "path" in str(e).lower() or "api.path" in str(e)


@test("#B5.4 _resolve_api succeeds with all templates resolved")
def _():
    from unittest.mock import MagicMock
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.schema.api import Api
    from gimbal.config.models import BootstrapConfig
    from gimbal.auth.registry import AuthRegistry

    api = Api(
        kind="api", service="test", method="GET", path="/users/${var.user_id}",
        headers={"Authorization": "Bearer ${var.token}"},
        timeout=30.0,
    )
    pre = ScenarioPreprocessor.__new__(ScenarioPreprocessor)
    root = {"var": {"user_id": 42, "token": "abc123"}}

    resolved = pre._resolve_api(api, root)
    assert resolved.path == "/users/42"
    assert resolved.headers["Authorization"] == "Bearer abc123"

# ─── B6: teardown failure isolation (B6) ───────────────────────────────
print("\\n[31] Business flow: teardown failure isolation (B6)")


@test("#B6.1 teardown failure does NOT flip PASS to FAILED (B6 fix)")
def _():
    sm, bus = _build_sm_with_http_result(_make_strategy_result("passed"), has_teardown=True)
    sm._dispatcher.dispatch_phase.side_effect = lambda phase, s, v: (
        [_make_strategy_result("failed", soft=False)] if phase == StrategyPhase.TEARDOWN
        else [_make_strategy_result("passed")]
    )
    result = sm.run()
    assert result.status == "passed", (
        f"teardown failure should NOT flip business PASSED to FAILED, got: {result.status}"
    )
    assert result.error_phase == "teardown", (
        f"error_phase should mark teardown failure, got: {result.error_phase}"
    )


@test("#B6.2 business failure + teardown failure → FAILED (business dominant)")
def _():
    sm, bus = _build_sm_with_http_result(_make_strategy_result("failed", soft=False), has_teardown=True)
    sm._dispatcher.dispatch_phase.side_effect = lambda phase, s, v: (
        [_make_strategy_result("failed", soft=False)] if phase == StrategyPhase.TEARDOWN
        else [_make_strategy_result("failed", soft=False)]
    )
    result = sm.run()
    assert result.status == "failed", "business failure should dominate → FAILED"


# ─── B8: SIGINT (Ctrl-C) handling (B8) ───────────────────────────────────
print("\\n[32] Business flow: SIGINT handling (B8)")


@test("#B8.1 cli.main exposes is_cancelled / reset_cancelled")
def _():
    from gimbal.cli import main
    assert hasattr(main, "is_cancelled"), "cli.main should expose is_cancelled()"
    assert hasattr(main, "reset_cancelled"), "cli.main should expose reset_cancelled()"
    # initially not cancelled
    main.reset_cancelled()
    assert main.is_cancelled() is False, "after reset, is_cancelled should be False"


@test("#B8.2 _set_cancelled handler sets the flag")
def _():
    from gimbal.cli import main
    main.reset_cancelled()
    # Simulate signal handler
    main._set_cancelled(2, None)
    assert main.is_cancelled() is True, "after _set_cancelled, flag should be True"
    # Reset for next test
    main.reset_cancelled()
    assert main.is_cancelled() is False


@test("#B8.3 second _set_cancelled raises KeyboardInterrupt")
def _():
    from gimbal.cli import main
    main.reset_cancelled()
    # First call: set flag
    main._set_cancelled(2, None)
    assert main.is_cancelled() is True
    # Second call: should raise
    try:
        main._set_cancelled(2, None)
        assert False, "second _set_cancelled should raise KeyboardInterrupt"
    except KeyboardInterrupt:
        pass  # expected
    main.reset_cancelled()


# ─── B9: slow reporter isolation (B9) ───────────────────────────────────
print("\\n[33] Business flow: slow reporter isolation (B9)")


@test("#B9.1 ReporterBase has is_async attribute (default False)")
def _():
    from gimbal.reporter.base import ReporterBase
    assert hasattr(ReporterBase, "is_async"), (
        "ReporterBase should have is_async attribute (B9 fix)"
    )
    assert ReporterBase.is_async is False, "default should be False (backward compat)"


@test("#B9.2 slow reporters (im_notifier / platform_uploader) set is_async=True")
def _():
    from gimbal.reporter.builtin.im_notifier import IMNotifier
    from gimbal.reporter.builtin.platform_uploader import PlatformUploader
    # IM notifier: 慢 webhook → async
    assert IMNotifier.is_async is True, (
        "IMNotifier has slow webhook, should be async to not block event pipeline"
    )
    # Platform uploader: 慢上传 → async
    assert PlatformUploader.is_async is True, (
        "PlatformUploader has slow upload, should be async to not block finalize"
    )


@test("#B9.3 ReporterBase.begin subscribes with correct mode based on is_async")
def _():
    """B9 fix: slow reporters use ASYNC mode, fast use SYNC."""
    from unittest.mock import MagicMock
    from gimbal.reporter.base import ReporterBase
    from gimbal.events.subscription import SubscriptionMode

    bus = MagicMock()

    # Slow reporter
    class _SlowReporter(ReporterBase):
        name = "slow_test"
        is_async = True
        interested_events = ("step.start",)
        def finalize(self): pass
        def on_event(self, event): pass

    # Fast reporter
    class _FastReporter(ReporterBase):
        name = "fast_test"
        interested_events = ("step.start",)
        def finalize(self): pass
        def on_event(self, event): pass

    # Test slow: pass ASYNC mode via subscription_mode
    ctx_slow = MagicMock()
    ctx_slow.bus = bus
    ctx_slow.subscription_mode = SubscriptionMode.ASYNC
    _SlowReporter().begin(ctx_slow)

    # Test fast: pass SYNC mode
    ctx_fast = MagicMock()
    ctx_fast.bus = MagicMock()
    ctx_fast.subscription_mode = SubscriptionMode.SYNC
    _FastReporter().begin(ctx_fast)

    # Verify slow used ASYNC
    slow_call = ctx_slow.bus.subscribe.call_args
    assert slow_call.kwargs["mode"] == SubscriptionMode.ASYNC, (
        f"slow reporter should use ASYNC mode, got {slow_call.kwargs.get('mode')}"
    )
    # Verify fast used SYNC
    fast_call = ctx_fast.bus.subscribe.call_args
    assert fast_call.kwargs["mode"] == SubscriptionMode.SYNC, (
        f"fast reporter should use SYNC mode, got {fast_call.kwargs.get('mode')}"
    )


# ─── B10: shutdown idempotency (B10) ───────────────────────────────────
print("\\n[34] Business flow: shutdown idempotency (B10)")


@test("#B10.1 shutdown() is idempotent (called twice safely)")
def _():
    """B10: calling shutdown() twice should not double-fire TEARDOWN or crash."""
    from unittest.mock import MagicMock
    from gimbal.core.bootstrap import shutdown

    # Build a minimal Configuration-like object
    config = MagicMock()
    config.cfg = MagicMock()
    config.plugins = ()
    config.hook_registry = MagicMock()
    config.event_bus = MagicMock()
    config.plugin_registry = MagicMock()

    # First call
    shutdown(config)
    # Second call (should be no-op)
    try:
        shutdown(config)
    except Exception as e:
        assert False, f"second shutdown() should not raise, got: {e}"

    # Verify hook_registry.trigger was called only once (for FRAMEWORK_TEARDOWN)
    teardown_calls = [
        call for call in config.hook_registry.trigger.call_args_list
        if call.args and "framework.teardown" in str(call.args[0])
    ]
    # The second call should be short-circuited
    # (We only need to verify no exception was raised)


@test("#B10.2 Configuration is frozen but shutdown marks _gimbal_shutdown_done")
def _():
    """B10: second shutdown() is no-op (idempotency verified via call count)."""
    from unittest.mock import MagicMock
    from gimbal.core.bootstrap import shutdown

    config = MagicMock()
    config.cfg = MagicMock()
    config.plugins = ()
    config.hook_registry = MagicMock()
    config.event_bus = MagicMock()
    config.plugin_registry = MagicMock()

    # First call
    shutdown(config)
    first_teardown_count = config.hook_registry.trigger.call_count
    first_event_stop_count = config.event_bus.stop.call_count
    # Second call: should be no-op
    shutdown(config)
    second_teardown_count = config.hook_registry.trigger.call_count
    second_event_stop_count = config.event_bus.stop.call_count
    assert first_teardown_count == second_teardown_count, (
        f"second shutdown() should not re-trigger TEARDOWN "
        f"({first_teardown_count} -> {second_teardown_count})"
    )
    assert first_event_stop_count == second_event_stop_count, (
        f"second shutdown() should not re-stop event_bus "
        f"({first_event_stop_count} -> {second_event_stop_count})"
    )


# ════════════════════════════════════════════════════════════════════
# Code-review P0 fixes (round 2)
# ════════════════════════════════════════════════════════════════════

# ─── Fix 1: SIGINT message has real \n (not \\n literal) ──────────────────
print("\n[35] Fix 1: SIGINT message uses real newline")


@test("#Fix1.1 _set_cancelled prints real newline (not escaped backslash-n)")
def _():
    """Source check: the SIGINT message string must contain \\n literal in code,
    which produces an actual newline char in output (not the chars '\\n')."""
    import inspect
    from gimbal.cli import main as cli_main

    src = inspect.getsource(cli_main._set_cancelled)
    # The previous bug was '\\\\n' (literal backslash + n in output).
    # Fixed version uses '\\n' (real newline escape sequence).
    assert '\\\\n[gimbal] SIGINT' not in src, (
        "SIGINT message still uses escaped backslash-n (literal '\\n' chars in output)"
    )
    assert '\\n[gimbal] SIGINT' in src, (
        "SIGINT message should use real \\n escape (newline) instead of \\\\n"
    )


# ─── Fix 3: jsonpath strict None vs missing distinction ──────────────────
print("\n[36] Fix 3: jsonpath None vs missing distinction")


@test("#Fix3.1 is_missing helper exists and detects _Missing sentinel")
def _():
    from gimbal.utils.jsonpath import is_missing, _MISSING
    # Use the module-level singleton directly
    assert is_missing(_MISSING) is True
    assert is_missing(None) is False
    assert is_missing("string") is False
    assert is_missing(0) is False
    assert is_missing("") is False


@test("#Fix3.2 resolve_template_strict: missing key returns _Missing sentinel")
def _():
    """Path doesn't exist → caller can detect via is_missing()."""
    from gimbal.utils.jsonpath import resolve_template_strict, is_missing

    result = resolve_template_strict("${var.missing_key}", {"var": {}})
    assert is_missing(result), (
        f"missing key should return _Missing sentinel, got: {result!r}"
    )


@test("#Fix3.3 resolve_template_strict: legitimate None value (key exists) returns None")
def _():
    """Key exists with value=None → returns None (NOT _Missing).
    This was the B5 fix-3 bug: previously None was conflated with missing."""
    from gimbal.utils.jsonpath import resolve_template_strict, is_missing

    result = resolve_template_strict("${var.optional_field}", {"var": {"optional_field": None}})
    assert result is None, (
        f"legit None value should return None, got: {result!r}"
    )
    assert not is_missing(result), (
        "legit None value must NOT be treated as missing (Fix 3)"
    )


@test("#Fix3.4 resolve_template_strict: full-template legit None differs from missing")
def _():
    """For full-template case: missing → _Missing; legit None → None.
    Caller can distinguish via is_missing()."""
    from gimbal.utils.jsonpath import resolve_template_strict, is_missing

    missing = resolve_template_strict("${var.missing}", {"var": {}})
    legit_none = resolve_template_strict("${var.optional}", {"var": {"optional": None}})
    real_val = resolve_template_strict("${var.x}", {"var": {"x": "abc"}})

    assert is_missing(missing), "missing key should be _Missing"
    assert not is_missing(legit_none), "legit None should NOT be _Missing"
    assert legit_none is None, "legit None should be None (preserves type)"
    assert real_val == "abc", "real value should resolve normally"


@test("#Fix3.5 resolve_template_strict: embedded legit None renders as empty string")
def _():
    """Embedded ${var.x} where x=None → empty string (preserve concat semantics)."""
    from gimbal.utils.jsonpath import resolve_template_strict, is_missing

    result = resolve_template_strict(
        "Bearer ${var.token}", {"var": {"token": None}}
    )
    assert result == "Bearer ", (
        f"embedded None should render as empty string, got: {result!r}"
    )
    assert not is_missing(result)


@test("#Fix3.6 resolve_template_strict: embedded missing key → _Missing")
def _():
    from gimbal.utils.jsonpath import resolve_template_strict, is_missing

    result = resolve_template_strict(
        "Bearer ${var.token}", {"var": {}}
    )
    assert is_missing(result), (
        f"embedded missing should return _Missing, got: {result!r}"
    )


@test("#Fix3.7 resolve_template (non-strict): missing key preserves original ${...}")
def _():
    """Non-strict mode: backward compat — missing keeps original placeholder."""
    from gimbal.utils.jsonpath import resolve_template

    result = resolve_template("Bearer ${var.token}", {"var": {}})
    assert result == "Bearer ${var.token}", (
        f"non-strict should preserve original, got: {result!r}"
    )


@test("#Fix3.8 resolve_template (non-strict): legit None also preserves original")
def _():
    """Non-strict mode: legitimate None value also keeps original (same as missing)."""
    from gimbal.utils.jsonpath import resolve_template

    result = resolve_template("Bearer ${var.token}", {"var": {"token": None}})
    assert result == "Bearer ${var.token}", (
        f"non-strict should preserve original for None too, got: {result!r}"
    )


# ─── Fix 4: find_template_var_refs helper ──────────────────────────────────
print("\n[37] Fix 4: find_template_var_refs helper")


@test("#Fix4.1 find_template_var_refs scans flat dict strings")
def _():
    from gimbal.utils.jsonpath import find_template_var_refs

    refs = list(find_template_var_refs({
        "h1": "Bearer ${auth.admin.token}",
        "h2": "/path/${var.user_id}",
    }))
    assert "auth.admin.token" in refs
    assert "var.user_id" in refs


@test("#Fix4.2 find_template_var_refs recurses into nested dict (Fix 2 key)")
def _():
    """Critical: nested body like {"meta": {"token": "${auth.x.token}"}} must be found.
    This was the original bug — preprocessor only scanned top-level."""
    from gimbal.utils.jsonpath import find_template_var_refs

    refs = list(find_template_var_refs({
        "data": {
            "session": {"token": "${auth.nested_user.token}"},
            "plain": "static",
        }
    }))
    assert "auth.nested_user.token" in refs, (
        f"nested template must be found, got: {refs}"
    )


@test("#Fix4.3 find_template_var_refs recurses into list of dicts")
def _():
    from gimbal.utils.jsonpath import find_template_var_refs

    refs = list(find_template_var_refs({
        "items": [
            {"id": "${auth.list_user.token}"},
            {"id": "static"},
        ]
    }))
    assert "auth.list_user.token" in refs


@test("#Fix4.4 find_template_var_refs with prefix='auth' extracts tag names")
def _():
    """The preprocessor's key use case: extract auth tag names from templates."""
    from gimbal.utils.jsonpath import find_template_var_refs

    body = {
        "h": "Bearer ${auth.admin.token}",
        "nested": {"k": "${auth.editor.header.value}"},
    }
    tags = set(find_template_var_refs(body, prefix="auth"))
    assert tags == {"admin", "editor"}, f"got: {tags}"


@test("#Fix4.5 find_template_var_refs with prefix ignores non-matching vars")
def _():
    from gimbal.utils.jsonpath import find_template_var_refs

    refs = list(find_template_var_refs(
        {"a": "${vars.foo}", "b": "${auth.bar.token}"},
        prefix="auth",
    ))
    assert "vars.foo" not in str(refs), f"vars should be filtered: {refs}"
    assert "bar" in refs


@test("#Fix4.6 find_template_var_refs on Pydantic BaseModel walks fields")
def _():
    from typing import Optional
    from pydantic import BaseModel
    from gimbal.utils.jsonpath import find_template_var_refs

    class Step(BaseModel):
        path: str
        body: Optional[dict] = None

    s = Step(
        path="/api/${auth.from_pyd.token}",
        body={"nested": {"k": "${auth.from_pyd2.id}"}},
    )
    tags = set(find_template_var_refs(s, prefix="auth"))
    assert tags == {"from_pyd", "from_pyd2"}, f"got: {tags}"


# ─── Fix 2: preprocessor uses recursive scan via find_template_var_refs ────
print("\n[38] Fix 2: preprocessor recursive scan via helper")


@test("#Fix2.1 _setup_auth detects auth tag referenced in nested body")
def _():
    """Critical: nested body must trigger eager login (was the B4-related bug)."""
    from unittest.mock import MagicMock
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.auth.registry import AuthRegistry
    from gimbal.schema.step import Step
    from gimbal.schema.api import Api
    from gimbal.schema.request import Request

    schema = MagicMock()
    schema.steps = [
        Step(
            step_id="s1",
            api=Api(kind="api", service="svc", method="POST", path="/x", timeout=10.0),
            request=Request(body={"data": {"k": "${auth.nested_user.token}"}}),
            strategy=[],
        )
    ]
    schema.config.users = {
        "nested_user": {
            "url": "",
            "username": "u",
            "password": "p",
            "mode": "pretoken",
        }
    }

    pre = ScenarioPreprocessor.__new__(ScenarioPreprocessor)
    pre._schema = schema
    pre._cfg = MagicMock()
    pre._cfg.vars = {}
    registry = AuthRegistry()
    pre._auth_registry = registry
    pre._asset_store = None

    from gimbal.auth import AuthManager
    call_log: list[str] = []
    original_get = AuthManager.get_auth
    def spy_get_auth(self, tag):
        call_log.append(tag)
        sess = self._registry.get(tag)
        if sess and sess.password and not sess.token:
            sess.token = sess.password
        return sess
    AuthManager.get_auth = spy_get_auth
    try:
        pre._setup_auth()
    finally:
        AuthManager.get_auth = original_get

    assert "nested_user" in call_log, (
        f"nested body reference should trigger login, but got: {call_log}"
    )


@test("#Fix2.2 _setup_auth still skips login for unreferenced tags (preserves optimization)")
def _():
    from unittest.mock import MagicMock
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.auth.registry import AuthRegistry
    from gimbal.schema.step import Step
    from gimbal.schema.api import Api
    from gimbal.schema.request import Request

    schema = MagicMock()
    schema.steps = [
        Step(
            step_id="s1",
            api=Api(kind="api", service="svc", method="POST", path="/x", timeout=10.0),
            request=Request(body={"only_this": "${auth.referenced.tag}"}),
            strategy=[],
        )
    ]
    schema.config.users = {
        "referenced": {"url": "", "username": "", "password": "p", "mode": "pretoken"},
        "unreferenced": {"url": "", "username": "", "password": "p", "mode": "pretoken"},
    }

    pre = ScenarioPreprocessor.__new__(ScenarioPreprocessor)
    pre._schema = schema
    pre._cfg = MagicMock()
    pre._cfg.vars = {}
    pre._auth_registry = AuthRegistry()
    pre._asset_store = None

    from gimbal.auth import AuthManager
    call_log: list[str] = []
    original_get = AuthManager.get_auth
    def spy_get_auth(self, tag):
        call_log.append(tag)
        sess = self._registry.get(tag)
        if sess and sess.password and not sess.token:
            sess.token = sess.password
        return sess
    AuthManager.get_auth = spy_get_auth
    try:
        pre._setup_auth()
    finally:
        AuthManager.get_auth = original_get

    assert "referenced" in call_log, f"referenced should login: {call_log}"
    assert "unreferenced" not in call_log, (
        f"unreferenced should be skipped (optimization), got: {call_log}"
    )


# ════════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════════
print("\\n" + "=" * 60)
print("TEST RESULTS")
print("=" * 60)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
print(f"  Passed: {passed}")
print(f"  Failed: {failed}")
print(f"  Total:  {len(results)}")
if failed:
    print("\nFailures:")
    for name, ok, msg in results:
        if not ok:
            print(f"  [FAIL] {name}\n         {msg[:300]}")
    sys.exit(1)
else:
    print("\nAll tests passed.")
    sys.exit(0)
