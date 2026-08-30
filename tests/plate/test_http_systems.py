"""A1: list registered systems with service/endpoint counts.

M6 mapping (ADR 0002 §D1):
    GET /api/systems  →  GET /api/system
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_systems_returns_fin_and_common(http_client: TestClient) -> None:
    resp = http_client.get("/api/system")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "system"
    systems = body["data"]["items"]
    # fin:endpoint 派生;common:声明式通用层(register_common_dims)。
    ids = [s["id"] for s in systems]
    assert ids == ["common", "fin"]
    fin = next(s for s in systems if s["id"] == "fin")
    assert fin["service_count"] >= 1
    assert fin["endpoint_count"] >= 1
    assert "registered_at" in fin
    common = next(s for s in systems if s["id"] == "common")
    assert common["endpoint_count"] == 0
