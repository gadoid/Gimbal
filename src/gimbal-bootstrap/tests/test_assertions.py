"""断言求值器 —— 让「passed」有证据，而不是数 POST 个数。"""

import pytest

from gimbal_bootstrap.assertions import MISSING, evaluate, resolve

RESP = {
    "call": {
        "response": {
            "status": 200,
            "body": {
                "status": "ok",
                "items": [{"id": 1}, {"id": 2}],
                "user": {"username": "sb-abc", "role": "member"},
                "total": 7,
            },
        }
    }
}


def test_resolve_reads_nested_paths():
    assert resolve(RESP, "$.call.response.status") == 200
    assert resolve(RESP, "$.call.response.body.user.username") == "sb-abc"
    assert resolve(RESP, "$.call.response.body.items[0].id") == 1


def test_resolve_returns_sentinel_for_missing_path():
    assert resolve(RESP, "$.call.response.body.nope") is MISSING
    assert resolve(RESP, "$.call.response.body.user.nope.deeper") is MISSING


def test_eq_and_ne():
    assert evaluate(RESP, {"target": "$.call.response.status", "operator": "eq", "expected": 200})
    assert not evaluate(RESP, {"target": "$.call.response.status", "operator": "eq", "expected": 500})
    assert evaluate(RESP, {"target": "$.call.response.status", "operator": "ne", "expected": 500})


def test_eq_compares_nested_object():
    a = {"target": "$.call.response.body.user", "operator": "eq",
         "expected": {"username": "sb-abc", "role": "member"}}
    assert evaluate(RESP, a)


def test_exists_passes_on_present_even_if_null():
    assert evaluate(RESP, {"target": "$.call.response.body.items", "operator": "exists"})
    assert evaluate(RESP, {"target": "$.call.response.body.nope", "operator": "exists"}) is False


def test_empty_operator():
    assert evaluate(RESP, {"target": "$.call.response.body.items", "operator": "empty"}) is False
    assert evaluate(RESP, {"target": "$.call.response.body.nope", "operator": "empty"}) is True


def test_length_eq():
    assert evaluate(RESP, {"target": "$.call.response.body.items", "operator": "length_eq",
                           "expected": 2})
    assert not evaluate(RESP, {"target": "$.call.response.body.items", "operator": "length_eq",
                               "expected": 3})


def test_comparison_operators():
    for op, exp, want in (("gt", 3, True), ("gte", 7, True), ("lt", 99, True), ("lte", 7, True)):
        assert evaluate(RESP, {"target": "$.call.response.body.total",
                               "operator": op, "expected": exp}) is want, op
    assert not evaluate(RESP, {"target": "$.call.response.body.total",
                               "operator": "gt", "expected": 99})


def test_in_operator():
    assert evaluate(RESP, {"target": "$.call.response.body.status", "operator": "in",
                           "expected": ["ok", "degraded"]})
    assert not evaluate(RESP, {"target": "$.call.response.body.status", "operator": "in",
                               "expected": ["nope"]})
    assert evaluate(RESP, {"target": "$.call.response.body.status", "operator": "not_in",
                           "expected": ["nope"]})


def test_contains_on_string_and_array():
    assert evaluate(RESP, {"target": "$.call.response.body.user.username",
                           "operator": "contains", "expected": "abc"})
    assert evaluate(RESP, {"target": "$.call.response.body.items", "operator": "contains",
                           "expected": {"id": 2}})
    assert not evaluate(RESP, {"target": "$.call.response.body.items",
                                "operator": "not_contains", "expected": {"id": 2}})


def test_eq_against_missing_path_fails_not_raises():
    """契约声明了但响应没有 —— 必须判失败，不能抛异常把整条用例带崩。"""
    assert not evaluate(RESP, {"target": "$.call.response.body.ghost",
                               "operator": "eq", "expected": 1})


def test_unknown_operator_fails_loudly():
    with pytest.raises(ValueError, match="未知 operator"):
        evaluate(RESP, {"target": "$.call.response.status", "operator": "wat", "expected": 1})
