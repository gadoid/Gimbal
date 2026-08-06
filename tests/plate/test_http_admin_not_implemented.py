"""C1/C2: admin endpoints return 501 with explicit error code."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_register_system_returns_501(http_client: TestClient) -> None:
    resp = http_client.post(
        "/api/systems",
        json={"name": "x", "source_url": "x", "auth_method": "none", "sync_mode": "manual"},
    )
    assert resp.status_code == 501
    err = resp.json()["error"]
    assert err["code"] == "admin_not_implemented"
    assert "deferred" in err["message"]


def test_sync_system_returns_501(http_client: TestClient) -> None:
    resp = http_client.post("/api/systems/fin/sync")
    assert resp.status_code == 501
    err = resp.json()["error"]
    assert err["code"] == "admin_not_implemented"
    assert "fin" in err["message"]
