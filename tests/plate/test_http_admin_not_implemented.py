"""C2: admin endpoints return 501 with explicit error code (M6 grammar).

M6 mapping (ADR 0002 §D1):
    POST /api/systems/{id}/sync    → POST /api/systems/{system}/system/action/sync

C1 (``POST /api/system/action/register``) 已实现为声明式注册,
见 ``test_declared_systems.py::TestC1RegisterAction``。
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_sync_system_returns_501(http_client: TestClient) -> None:
    resp = http_client.post("/api/systems/fin/system/action/sync")
    assert resp.status_code == 501
    err = resp.json()["error"]
    assert err["code"] == "admin_not_implemented"
    assert "fin" in err["message"]
