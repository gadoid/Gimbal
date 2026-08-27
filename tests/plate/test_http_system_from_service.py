"""B3: derive system id from a fully-qualified service string (M6 grammar).

M6 mapping (ADR 0002 §D1):
    POST /api/resolve/system-from-service
        → POST /api/system/action/from-service
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_system_from_service_basic(http_client: TestClient) -> None:
    resp = http_client.post(
        "/api/system/action/from-service",
        json={"services": ["fin.tidb-test", "logi.mysql-svc"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "system"
    data = body["data"]["systems"]
    assert {"service": "fin.tidb-test", "system": "fin"} in data
    assert {"service": "logi.mysql-svc", "system": "logi"} in data


def test_system_from_service_handles_missing_dot(http_client: TestClient) -> None:
    resp = http_client.post(
        "/api/system/action/from-service",
        json={"services": ["no-dot-here"]},
    )
    assert resp.status_code == 200
    systems = resp.json()["data"]["systems"]
    assert systems[0]["system"] == ""


def test_system_from_service_empty_list(http_client: TestClient) -> None:
    resp = http_client.post(
        "/api/system/action/from-service",
        json={"services": []},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["systems"] == []