"""Health check test for the plate HTTP service."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gimbal_plate.http import create_app


def test_healthz_returns_ok() -> None:
    app = create_app(registry=__import__("gimbal_plate.registry", fromlist=["PlateRegistry"]).PlateRegistry())
    with TestClient(app) as client:
        resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
