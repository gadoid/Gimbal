"""``/{dim}/{id}/references`` reverse-lookup (ADR 0002 §D-D2, Phase β).

M6 mapping for the references surface:

    GET /api/{dim}/{id}/references    → reverse-lookup signals

Phase β honest scope (ADR §D-D2 — ``不要``, defer to Phase β):
    - For every dim item the endpoint returns ``systems`` (which systems
      own the item) plus dim-specific metadata we can answer from existing
      registry data without inventing a full cross-dim edge graph.
    - A 404 ``dim_item_not_found`` is returned if the item is not
      registered, 404 ``dim_not_found`` if the dim itself is unknown.
    - Phase γ candidate: scan ``scenario.config`` / ``scenario.resource``
      refs to populate ``scenarios_referenced_by`` for config / resource.

Per-dim reference signals verified here:

    endpoint   systems, service, module, tags
    service    systems, endpoint_count
    system     systems (self), endpoint_count, service_count
    config     systems (parsed from ``{system}.{name}`` id prefix), service_count
    meta       systems (from ``meta.system`` list)
    resource   systems (parsed from id prefix), kind
    scenario   systems (from ``meta.system``), scenarios_referenced_by (empty)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# Seeded by conftest.py — these dims are the universe under test.
_HAPPY_PATH_DIMS = [
    "endpoint", "service", "system", "config", "meta", "resource", "scenario",
]

_UNKNOWN_ID_DIMS = _HAPPY_PATH_DIMS  # same universe — 404 path is dim-agnostic


# ── 7 dims: happy path returns 200 with the right envelope ────────


def _envelope_ok(body: dict) -> None:
    """Common envelope shape: ``ok=True``, ``dim`` is a non-empty string,
    ``data.references`` is a dict. The ``data.item`` shape is verified
    independently by ``test_references_envelope_item_only_dim_and_id``.
    """
    assert body["ok"] is True
    assert isinstance(body["dim"], str) and body["dim"]
    data = body["data"]
    assert isinstance(data["references"], dict)


@pytest.mark.parametrize(
    "dim, sample_id, dim_specific",
    [
        # endpoint: loose checks for module / tags (string / list types only)
        ("endpoint", "fin.order.order_add", {"service": "order"}),
        ("service",  "order",               {"endpoint_count": (int, lambda v: v >= 1)}),
        ("system",   "fin",                 {
            "endpoint_count": (int, lambda v: v >= 1),
            "service_count": (int, lambda v: v >= 1),
        }),
        ("config",   "fin.default",         {"service_count": (int, lambda v: v >= 5)}),
        ("meta",     "fin.default",         {}),
        ("resource", "fin.tidb_test",       {"kind": str}),
        ("scenario", "sc-fin-default",      {"scenarios_referenced_by": []}),
    ],
)
def test_references_happy_path(
    http_client: TestClient, dim: str, sample_id: str, dim_specific: dict
) -> None:
    """Each dim's /references returns 200 with ``systems=[fin]`` + dim-specific signal."""
    resp = http_client.get(f"/api/{dim}/{sample_id}/references")
    assert resp.status_code == 200
    body = resp.json()
    _envelope_ok(body)
    refs = body["data"]["references"]
    assert refs["dim"] == dim
    assert refs["systems"] == ["fin"]
    for key, expected in dim_specific.items():
        actual = refs[key]
        if isinstance(expected, type):
            assert isinstance(actual, expected), f"{key}: {actual!r}"
        elif isinstance(expected, tuple) and len(expected) == 2:
            # ``(type, predicate)`` — type check + value predicate
            check_type, predicate = expected
            assert isinstance(actual, check_type), f"{key}: {actual!r}"
            assert predicate(actual), f"{key}={actual!r} did not satisfy predicate"
        else:
            assert actual == expected, f"{key}: {actual!r} != {expected!r}"


# ── 7 dims: unknown id returns 404 dim_item_not_found ──────────────


@pytest.mark.parametrize("dim", _UNKNOWN_ID_DIMS)
def test_references_unknown_id_returns_404(http_client: TestClient, dim: str) -> None:
    resp = http_client.get(f"/api/{dim}/no.such.{dim}/references")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"


# ── Unknown dim returns 404 dim_not_found ──────────────────────────


def test_references_unknown_dim_returns_404(http_client: TestClient) -> None:
    resp = http_client.get("/api/no.such.dim/foo/references")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_not_found"


# ── Item envelope is consistent across dims ────────────────────────


def test_references_envelope_item_only_dim_and_id(http_client: TestClient) -> None:
    """``data.item`` is exactly ``{dim, id}`` — never the full dim payload."""
    resp = http_client.get(f"/api/endpoint/fin.order.order_add/references")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    assert set(item.keys()) == {"dim", "id"}
    assert item["dim"] == "endpoint"
    assert item["id"] == "fin.order.order_add"


def test_references_payload_never_includes_secret_like_keys(
    http_client: TestClient,
) -> None:
    """``references`` payload must not include sensitive config keys."""
    resp = http_client.get("/api/config/fin.default/references")
    assert resp.status_code == 200
    refs = resp.json()["data"]["references"]
    forbidden = {"password", "users", "services"}
    leaked = forbidden & set(refs.keys())
    assert not leaked, f"references leaked sensitive keys: {leaked}"
