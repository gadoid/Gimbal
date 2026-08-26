"""``/full`` config contract (ADR 0002 §D-D5).

M6 mapping for the full-contract surface:
    GET /api/config/full                  → list (every schema field per item)
    GET /api/config/{id}/full             → detail (full Config contract)
    GET /api/systems/{system}/config/full             → list_for_system
    GET /api/systems/{system}/config/{id}/full        → detail_for_system

Critical assertions (vs the light ``ConfigView`` in
``test_http_admin_not_implemented.py`` and the no-test-yet light list):

- ``/full`` exposes ``users[].password`` (light DROPS it)
- ``/full`` exposes the ``extra`` key (light does not declare it)
- The seeded fin config has 6 service URLs and 1 user (``tester_a``).
"""
from __future__ import annotations

from fastapi.testclient import TestClient


# Seeded by conftest.py: ``cfg_idx.register(fin_config_template(),
# item_id=f"{FIN_SYSTEM}.default")``.
CONFIG_ID = "fin.default"


# ── /api/config/{id}/full ──────────────────────────────────────────


def test_config_full_exposes_password(http_client: TestClient) -> None:
    """``/full`` exposes the ``users[].password`` field (light DROPS it)."""
    resp = http_client.get(f"/api/config/{CONFIG_ID}/full")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "config"
    item = body["data"]["item"]

    assert item["users"], "seeded fin config should have at least 1 user"
    first_user = next(iter(item["users"].values()))
    # Light ConfigView drops these fields by NOT declaring them — full must
    # declare them and re-emit them.
    assert "password" in first_user, (
        f"expected password in /full user dict, got keys={list(first_user.keys())}"
    )


def test_config_full_exposes_extra_key(http_client: TestClient) -> None:
    """``/full`` exposes the ``extra`` field that light ConfigView omits."""
    resp = http_client.get(f"/api/config/{CONFIG_ID}/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    # ConfigDetailView declares ``extra``; ConfigView does not.
    assert "extra" in item


def test_config_full_keeps_other_keys(http_client: TestClient) -> None:
    """``/full`` carries the same top-level keys as light (plus extra)."""
    resp = http_client.get(f"/api/config/{CONFIG_ID}/full")
    item = resp.json()["data"]["item"]
    for key in ("setup", "teardown", "services", "users", "time_policy", "vars"):
        assert key in item, f"missing key {key!r} in /full config item"


def test_config_full_services_dict(http_client: TestClient) -> None:
    """The bundled fin config carries the single fin-service URL."""
    resp = http_client.get(f"/api/config/{CONFIG_ID}/full")
    item = resp.json()["data"]["item"]
    services = item["services"]
    assert isinstance(services, dict)
    # fin 全部 endpoint 统一归属单一部署单元 fin-service。
    assert set(services) == {"fin-service"}
    assert all(v.startswith("https://") for v in services.values())


def test_config_full_users_contain_known_user(http_client: TestClient) -> None:
    """The bundled fin config has ``tester_a`` as a known seeded user."""
    resp = http_client.get(f"/api/config/{CONFIG_ID}/full")
    item = resp.json()["data"]["item"]
    users = item["users"]
    assert "tester_a" in users, f"expected tester_a, got tags={list(users.keys())}"


# ── /api/config/full ───────────────────────────────────────────────


def test_config_full_list_shape(http_client: TestClient) -> None:
    resp = http_client.get("/api/config/full")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    items = body["data"]["items"]
    # At least the seeded fin config.
    assert body["data"]["total"] == len(items) >= 1
    # Every item is a ConfigDetailView (extra present, users[*].password present).
    for it in items:
        assert "extra" in it
        if it["users"]:
            first_user = next(iter(it["users"].values()))
            assert "password" in first_user


def test_config_full_unknown_id_returns_404(http_client: TestClient) -> None:
    resp = http_client.get("/api/config/no.such.config/full")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"


# ── system-scoped ──────────────────────────────────────────────────


def test_config_full_for_system(http_client: TestClient) -> None:
    resp = http_client.get("/api/systems/fin/config/full")
    assert resp.status_code == 200
    body = resp.json()
    items = body["data"]["items"]
    # The conftest seeds exactly one fin config.
    assert any(
        u and "password" in next(iter(u.values()))
        for it in items for u in [it["users"]]
    )


def test_config_full_for_system_single(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/fin/config/{CONFIG_ID}/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    assert "extra" in item
    first_user = next(iter(item["users"].values()))
    assert "password" in first_user


def test_config_full_for_system_unknown_id_returns_404(
    http_client: TestClient,
) -> None:
    resp = http_client.get("/api/systems/fin/config/no.such/full")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"