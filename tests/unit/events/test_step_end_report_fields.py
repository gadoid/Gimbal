"""B1(2026-11-06 日志报告整理):step.end 报告面字段。

平台按 step.end 落 execution_steps,报告从步骤表渲染——本文件钉住
step.end 自带的「步骤名 / 说明 / 调用摘要 / 断言明细 / 提取值 / 失败证据」
以及脱敏、截断口径。
"""
from __future__ import annotations

from tests.unit.characterization.test_events_and_plugins import (
    http_scenario, make_engine, mock_httpx,
)
from gimbal.schema import AssertOperator, Assertion, Extract, Scope


def _run(strategy, body, status=200):
    engine, bus, *_ = make_engine()
    ends, exchanges = [], []
    bus.subscribe(lambda e: ends.append(e), "step.end")
    bus.subscribe(lambda e: exchanges.append(e), "call.exchange")
    with mock_httpx(status, body)[0]:
        result = engine.run(http_scenario(strategy=strategy))
    return result, ends, exchanges


def test_failed_assertion_detail_and_failure_evidence():
    strategy = [
        Extract(kind="extract", expression="$.call.response.body.id",
                target="oid", scope=Scope.STEP),
        Assertion(kind="assertion", target="$.call.response.status",
                  operator=AssertOperator.EQ, expected=200),
        Assertion(kind="assertion", target="$.call.response.body.id",
                  operator=AssertOperator.EQ, expected="8"),
    ]
    result, ends, _ = _run(strategy, {"id": "7"})
    assert result.failed == 1
    ev = ends[0]
    assert ev.status == "failed"
    assert ev.call_summary == "POST https://svc.example/p"
    assert ev.assertion_count == 2 and ev.assertion_passed == 1

    ok, bad = ev.assertions
    assert ok["passed"] is True and ok["operator"] == "eq"
    assert bad == {
        "name": "$.call.response.body.id",
        "target": "$.call.response.body.id",
        "operator": "eq",
        "expected": "8",
        "actual": "7",
        "passed": False,
        "message": "FAIL: actual '7', expected eq '8'",
    }
    # 步骤级提取(只进 scratch)也进入 extracts
    assert ev.extracts == [{"target": "oid", "value": "7"}]
    # 失败步骤携带调用证据(与 call.exchange 同形)
    fe = ev.failure_evidence
    assert fe["request"]["method"] == "POST"
    assert fe["response"]["status"] == 200
    assert fe["response"]["body"] == {"id": "7"}


def test_sensitive_targets_are_redacted():
    strategy = [
        Extract(kind="extract", expression="$.call.response.body.token",
                target="access_token", scope=Scope.STEP),
        Assertion(kind="assertion", target="$.call.response.body.token",
                  operator=AssertOperator.EQ, expected="nope"),
    ]
    _, ends, _ = _run(strategy, {"token": "S3CRET"})
    ev = ends[0]
    a = ev.assertions[0]
    assert a["actual"] == "***redacted***" and a["expected"] == "***redacted***"
    assert "S3CRET" not in a["message"]
    assert ev.extracts == [{"target": "access_token", "value": "***redacted***"}]


def test_oversize_values_are_truncated():
    big = "x" * 5000
    strategy = [Extract(kind="extract", expression="$.call.response.body.blob",
                        target="blob", scope=Scope.STEP)]
    _, ends, _ = _run(strategy, {"blob": big})
    v = ends[0].extracts[0]["value"]
    assert isinstance(v, str) and len(v) < 2100 and v.endswith("…(+3000)")


def test_passed_step_has_no_failure_evidence():
    strategy = [Assertion(kind="assertion", target="$.call.response.status",
                          operator=AssertOperator.EQ, expected=200)]
    result, ends, exchanges = _run(strategy, {"ok": 1})
    assert result.passed == 1
    assert ends[0].failure_evidence is None
    assert len(exchanges) == 1   # 调用证据只走 call.exchange
