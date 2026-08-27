"""Tests for the unified envelope helpers."""

from __future__ import annotations

from gimbal_plate.http.envelope import (
    EnvelopeErr,
    EnvelopeOk,
    ErrorPayload,
    PlateHTTPError,
    err_response,
    ok_response,
)


def test_ok_response_envelope_shape() -> None:
    body = ok_response({"x": 1})
    assert body["ok"] is True
    assert body["data"] == {"x": 1}


def test_err_response_envelope_shape() -> None:
    body, status = err_response("not_found", "missing", http_status=404)
    assert status == 404
    assert body["ok"] is False
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "missing"
    assert "details" not in body["error"]


def test_err_response_includes_details_when_provided() -> None:
    body, status = err_response(
        "validation_error", "bad", http_status=422, details={"field": "x"}
    )
    assert status == 422
    assert body["error"]["details"] == {"field": "x"}


def test_plate_http_error_carries_status_and_code() -> None:
    err = PlateHTTPError(
        http_status=501, code="admin_not_implemented", message="deferred"
    )
    payload = err.to_payload()
    assert payload.code == "admin_not_implemented"
    assert payload.message == "deferred"
    assert err.http_status == 501


def test_envelope_models_round_trip() -> None:
    ok = EnvelopeOk(data={"a": [1, 2]})
    err = EnvelopeErr(error=ErrorPayload(code="c", message="m"))
    assert ok.model_dump()["ok"] is True
    assert err.model_dump()["ok"] is False
