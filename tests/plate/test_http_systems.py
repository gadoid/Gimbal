"""A1: list registered systems with service/endpoint counts."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_systems_returns_fin(http_client: TestClient) -> None:
    resp = http_client.get("/api/systems")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    systems = body["data"]["systems"]
    assert len(systems) == 1
    fin = systems[0]
    assert fin["id"] == "fin"
    assert fin["service_count"] >= 1
    assert fin["endpoint_count"] >= 1
    assert "registered_at" in fin
