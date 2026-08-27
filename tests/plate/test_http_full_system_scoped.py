"""System-scoped ``/{id}/full`` membership check (ADR 0002 §D-D5).

Tests ``_item_belongs_to_system`` — the helper that backs the system-scoped
detail routes for both light and ``/full`` paths. The original implementation
relied on ``getattr(it, "id") or it.get("id")`` which raised
``AttributeError`` on Pydantic models without a uniform ``.id`` attribute
(``Config`` / ``Mock`` / ``Scenario``); the helper now compares by object
identity against the index's ``list_for_system`` output.

Coverage matrix:

- 200 on each /full system-scoped detail route (4 dims × 1 id = 4 cases)
- 200 on each light system-scoped detail route (the light paths share the
  same helper — see routes_grammar.py:get_dim_item_for_system)
- 404 ``dim_item_not_found`` when an id exists in the global registry but
  not in the requested system (the negative case the helper must reject)
- 404 ``system_not_found`` when the system itself doesn't exist
"""
from __future__ import annotations

from fastapi.testclient import TestClient


# All ids exist in the bundled fin seed.
SAMPLE_ENDPOINT  = "fin.order.order_add"
SAMPLE_CONFIG    = "fin.default"
SAMPLE_RESOURCE  = "fin.tidb_test"
SAMPLE_SCENARIO  = "sc-fin-default"


# ── 4 dims: full system-scoped detail must return 200 ──────────────


def test_endpoint_full_for_system(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/fin/endpoint/{SAMPLE_ENDPOINT}/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    assert item["id"] == SAMPLE_ENDPOINT
    # Full contract marker.
    assert "api" in item and "metadata" in item


def test_config_full_for_system(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/fin/config/{SAMPLE_CONFIG}/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    # Full contract marker (light does NOT declare extra; full does).
    assert "extra" in item


def test_resource_full_for_system(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/fin/resource/{SAMPLE_RESOURCE}/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    # Full contract marker.
    assert "extra" in item and "image" in item["extra"]


def test_scenario_full_for_system(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/fin/scenario/{SAMPLE_SCENARIO}/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    # Full contract marker.
    assert "extra" in item and "meta" in item["extra"]


# ── 4 dims: light system-scoped detail must ALSO return 200 ────────
# These cover the light path which shares the _item_belongs_to_system
# helper. Before the fix, /api/systems/fin/config/fin.default returned
# 500 internal_error due to "Config object has no attribute 'get'".


def test_endpoint_light_for_system(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/fin/endpoint/{SAMPLE_ENDPOINT}")
    assert resp.status_code == 200
    assert resp.json()["data"]["item"]["id"] == SAMPLE_ENDPOINT


def test_config_light_for_system(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/fin/config/{SAMPLE_CONFIG}")
    assert resp.status_code == 200


def test_resource_light_for_system(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/fin/resource/{SAMPLE_RESOURCE}")
    assert resp.status_code == 200
    assert resp.json()["data"]["item"]["name"] == SAMPLE_RESOURCE


def test_scenario_light_for_system(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/fin/scenario/{SAMPLE_SCENARIO}")
    assert resp.status_code == 200
    assert resp.json()["data"]["item"]["scenario_id"] == SAMPLE_SCENARIO


# ── 4 dims: 4 dims: id exists but the requested system doesn't ──────


def test_endpoint_full_wrong_system_returns_404(http_client: TestClient) -> None:
    """The id exists globally but is NOT under ``other``. Must 404, not 500."""
    resp = http_client.get(
        f"/api/systems/other/endpoint/{SAMPLE_ENDPOINT}/full"
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] in {
        "system_not_found",
        "dim_item_not_found",
    }


def test_config_full_wrong_system_returns_404(http_client: TestClient) -> None:
    resp = http_client.get(
        f"/api/systems/other/config/{SAMPLE_CONFIG}/full"
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] in {
        "system_not_found",
        "dim_item_not_found",
    }


def test_resource_full_wrong_system_returns_404(http_client: TestClient) -> None:
    resp = http_client.get(
        f"/api/systems/other/resource/{SAMPLE_RESOURCE}/full"
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] in {
        "system_not_found",
        "dim_item_not_found",
    }


def test_scenario_full_wrong_system_returns_404(http_client: TestClient) -> None:
    resp = http_client.get(
        f"/api/systems/other/scenario/{SAMPLE_SCENARIO}/full"
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] in {
        "system_not_found",
        "dim_item_not_found",
    }


# ── light path negative coverage ───────────────────────────────────


def test_config_light_wrong_system_returns_404(http_client: TestClient) -> None:
    """Regression guard: the light path also depends on _item_belongs_to_system."""
    resp = http_client.get(f"/api/systems/other/config/{SAMPLE_CONFIG}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] in {
        "system_not_found",
        "dim_item_not_found",
    }


def test_resource_light_wrong_system_returns_404(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/other/resource/{SAMPLE_RESOURCE}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] in {
        "system_not_found",
        "dim_item_not_found",
    }


def test_scenario_light_wrong_system_returns_404(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/other/scenario/{SAMPLE_SCENARIO}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] in {
        "system_not_found",
        "dim_item_not_found",
    }