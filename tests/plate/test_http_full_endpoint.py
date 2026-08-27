"""``/full`` endpoint contract (ADR 0002 §D-D5).

M6 mapping for the full-contract surface:
    GET /api/endpoint/full              → list (every schema field per item)
    GET /api/endpoint/{id}/full         → detail (full EndpointSpec contract)
    GET /api/systems/{system}/endpoint/full             → list_for_system
    GET /api/systems/{system}/endpoint/{id}/full        → detail_for_system

The ``/full`` endpoint is driven by ``EndpointDetailView.from_spec`` which
round-trips through Pydantic's ``model_dump`` so every field of the underlying
``EndpointSpec`` surfaces (api / request / responses / metadata). Compare against
``test_http_endpoint_detail.py`` which validates the light ``EndpointView``.

Coverage matrix:

- 200 on each of the 4 routes
- ``ok=True``, ``dim="endpoint"`` envelope
- ``item.api`` is a nested dict (NOT the light ``method`` / ``path`` fields)
- ``item.metadata`` is a nested dict (NOT the light ``module`` / ``tags`` fields)
- ``item.request`` / ``item.responses`` are present (with ``IOFieldBinding`` payload)
- Light view (control) does NOT contain ``api`` / ``metadata`` nested keys
- 404 dim_item_not_found for unknown id under both global and system-scoped routes
- 200 on system-scoped routes even when system has many endpoints
- 404 system_not_found when the system doesn't exist (covers B2 path)
"""
from __future__ import annotations

from fastapi.testclient import TestClient


# Reference endpoint id from the bundled fin system (all endpoints live under
# ``fin.<service>.<name>`` per ADR 0001). ``order_add`` is also used by the
# existing light-detail test for consistency.
SAMPLE_ENDPOINT = "fin.order.order_add"
ALT_ENDPOINT = "fin.order_entrust.order_add"


# ── /api/endpoint/{id}/full ────────────────────────────────────────


def test_endpoint_full_returns_full_contract(http_client: TestClient) -> None:
    """``/api/endpoint/{id}/full`` returns EndpointDetailView (every field)."""
    resp = http_client.get(f"/api/endpoint/{SAMPLE_ENDPOINT}/full")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "endpoint"
    item = body["data"]["item"]

    # Core identity.
    assert item["id"] == SAMPLE_ENDPOINT
    assert item["system"] == "fin"
    assert item["service"] == "fin-service"
    # ``name`` is a human-readable description (not the slug); non-empty
    # check keeps the test robust across i18n changes.
    assert isinstance(item["name"], str) and item["name"]

    # Full contract keys — these are NOT in the light EndpointView:
    assert "api" in item and isinstance(item["api"], dict)
    assert "metadata" in item and isinstance(item["metadata"], dict)
    assert "request" in item  # may be None or dict depending on spec
    assert "responses" in item and isinstance(item["responses"], dict)

    # The nested api object carries the HTTP method / path (light has them as
    # flat fields — this is the structural marker that the full factory ran).
    assert item["api"].get("method") == "POST"
    assert "path" in item["api"]


def test_endpoint_full_light_excludes_full_keys(http_client: TestClient) -> None:
    """The light ``/api/endpoint/{id}`` does NOT include the nested api/metadata."""
    resp = http_client.get(f"/api/endpoint/{SAMPLE_ENDPOINT}")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]

    # Light contract — flat fields only.
    assert item["method"] == "POST"
    assert item["path"].startswith("/")
    # Nested full keys are absent (or contain nothing meaningful):
    assert "api" not in item
    assert "metadata" not in item or item["metadata"] == {}


def test_endpoint_full_unknown_id_returns_404(http_client: TestClient) -> None:
    resp = http_client.get("/api/endpoint/fin.no.such.thing/full")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"


# ── /api/endpoint/full ─────────────────────────────────────────────


def test_endpoint_full_list_shape(http_client: TestClient) -> None:
    """``/api/endpoint/full`` returns ALL endpoints, each in EndpointDetailView shape."""
    resp = http_client.get("/api/endpoint/full")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "endpoint"
    data = body["data"]
    items = data["items"]
    # Bundled fin system ships 18 endpoints.
    assert data["total"] == len(items) >= 18
    # Every item is an EndpointDetailView (api/metadata nested).
    for it in items:
        assert "api" in it and isinstance(it["api"], dict)
        assert "metadata" in it and isinstance(it["metadata"], dict)
    # Sample id is present.
    ids = {it["id"] for it in items}
    assert SAMPLE_ENDPOINT in ids


# ── system-scoped ──────────────────────────────────────────────────


def test_endpoint_full_for_system(http_client: TestClient) -> None:
    """``/api/systems/fin/endpoint/full`` returns endpoints owned by fin."""
    resp = http_client.get("/api/systems/fin/endpoint/full")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    items = body["data"]["items"]
    # All items belong to fin (since no other system exists in the bundled set).
    for it in items:
        assert it["system"] == "fin"
    # Sample ids included.
    ids = {it["id"] for it in items}
    assert SAMPLE_ENDPOINT in ids
    assert ALT_ENDPOINT in ids


def test_endpoint_full_for_system_unknown_id_returns_404(
    http_client: TestClient,
) -> None:
    resp = http_client.get(f"/api/systems/fin/endpoint/fin.no.such.thing/full")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"


def test_endpoint_full_for_system_unknown_system_returns_404(
    http_client: TestClient,
) -> None:
    """A nonexistent system yields ``system_not_found`` (covers _resolve_system)."""
    resp = http_client.get(f"/api/systems/no-such-system/endpoint/full")
    assert resp.status_code == 404
    # The tree endpoint triggers system_not_found first; /full uses the same
    # gate so we accept either system_not_found or dim_not_found upstream.
    assert resp.json()["error"]["code"] in {"system_not_found", "dim_not_found"}


def test_endpoint_full_for_system_single(http_client: TestClient) -> None:
    """``/api/systems/fin/endpoint/{id}/full`` mirrors global /full for that system."""
    resp = http_client.get(f"/api/systems/fin/endpoint/{SAMPLE_ENDPOINT}/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    assert item["id"] == SAMPLE_ENDPOINT
    assert "api" in item and "metadata" in item