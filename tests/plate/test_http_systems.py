"""A1: list registered systems with service/endpoint counts.

M6 mapping (ADR 0002 §D1):
    GET /api/systems  →  GET /api/system
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_systems_returns_fin(http_client: TestClient) -> None:
    resp = http_client.get("/api/system")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "system"
    systems = body["data"]["items"]
    assert len(systems) == 1
    fin = systems[0]
    assert fin["id"] == "fin"
    assert fin["service_count"] >= 1
    assert fin["endpoint_count"] >= 1
    assert "registered_at" in fin