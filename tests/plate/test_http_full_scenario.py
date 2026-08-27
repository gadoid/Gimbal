"""``/full`` scenario contract (ADR 0002 §D-D5).

M6 mapping for the full-contract surface:
    GET /api/scenario/full                 → list
    GET /api/scenario/{scenarioId}/full    → detail
    GET /api/systems/{system}/scenario/full             → list_for_system
    GET /api/systems/{system}/scenario/{scenarioId}/full → detail_for_system

Light :class:`ScenarioMinimalView` only exposes ``scenario_id`` / ``name`` /
``systems``. ``/full`` re-emits the entire :class:`Scenario` under the
``extra`` key with ``meta`` / ``config`` / ``resource`` / ``steps`` structured
inside it (ADR 0002 §11 — read-only inspection of registered scenarios).
"""
from __future__ import annotations

from fastapi.testclient import TestClient


# Seeded by conftest.py: ``scen_idx.register(fin_scenario_template())`` —
# the ScenarioIndex registers under ``scenario.scenarioId`` rather than an
# explicit ``item_id`` kwarg, so the registry key equals the scenarioId.
SCENARIO_ID = "sc-fin-default"


# ── /api/scenario/{id}/full ─────────────────────────────────────────


def test_scenario_full_exposes_extra(http_client: TestClient) -> None:
    """``/full`` exposes ``extra`` carrying ``meta`` / ``config`` / ``resource`` / ``steps``."""
    resp = http_client.get(f"/api/scenario/{SCENARIO_ID}/full")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "scenario"
    item = body["data"]["item"]

    # Top-level identity / systems keys (always present, on both light and full).
    assert item["scenario_id"] == SCENARIO_ID
    assert isinstance(item["name"], str) and item["name"]
    assert "fin" in item["systems"]
    # Full contract carries the rest under ``extra``.
    assert "extra" in item and isinstance(item["extra"], dict)


def test_scenario_full_extra_has_structured_payloads(
    http_client: TestClient,
) -> None:
    """``extra`` keys include ``meta`` / ``config`` / ``resource`` / ``steps``."""
    resp = http_client.get(f"/api/scenario/{SCENARIO_ID}/full")
    item = resp.json()["data"]["item"]
    extra = item["extra"]
    for key in ("meta", "config", "resource", "steps"):
        assert key in extra, f"expected {key!r} in extra, got {list(extra.keys())}"
    # ``meta`` is the canonical ScenarioMeta dict with system / tags / version.
    assert "name" in extra["meta"]
    assert "version" in extra["meta"]
    # ``steps`` is a list (may be empty for the bundled seed).
    assert isinstance(extra["steps"], list)


def test_scenario_full_light_excludes_extra(http_client: TestClient) -> None:
    """The light ``/api/scenario/{id}`` does NOT expose ``extra``."""
    resp = http_client.get(f"/api/scenario/{SCENARIO_ID}")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    assert "extra" not in item
    # Light contract is exactly {scenario_id, name, systems}.
    assert set(item.keys()) == {"scenario_id", "name", "systems"}


def test_scenario_full_unknown_id_returns_404(http_client: TestClient) -> None:
    resp = http_client.get("/api/scenario/no.such.scenario/full")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"


# ── /api/scenario/full ─────────────────────────────────────────────


def test_scenario_full_list_shape(http_client: TestClient) -> None:
    resp = http_client.get("/api/scenario/full")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    items = body["data"]["items"]
    # Bundled fin seed registers exactly 1 scenario.
    assert body["data"]["total"] == len(items) >= 1
    # Every item has the full {scenario_id, name, systems, extra} shape.
    for it in items:
        assert "scenario_id" in it
        assert "name" in it
        assert "systems" in it
        assert "extra" in it
        assert "meta" in it["extra"]


# ── system-scoped ──────────────────────────────────────────────────


def test_scenario_full_for_system(http_client: TestClient) -> None:
    resp = http_client.get("/api/systems/fin/scenario/full")
    assert resp.status_code == 200
    items = http_client.get("/api/systems/fin/scenario/full").json()["data"]["items"]
    assert any(it["scenario_id"] == SCENARIO_ID for it in items)
    # Every item belongs to fin.
    for it in items:
        assert "fin" in it["systems"]


def test_scenario_full_for_system_single(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/fin/scenario/{SCENARIO_ID}/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    assert item["scenario_id"] == SCENARIO_ID
    assert "extra" in item
    assert "meta" in item["extra"]


def test_scenario_full_for_system_unknown_id_returns_404(
    http_client: TestClient,
) -> None:
    resp = http_client.get("/api/systems/fin/scenario/no.such/full")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"