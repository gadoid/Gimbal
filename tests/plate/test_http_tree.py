"""A2: list service / module tree under a system."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_tree_for_fin_returns_services(http_client: TestClient) -> None:
    resp = http_client.get("/api/systems/fin/tree")
    assert resp.status_code == 200
    services = resp.json()["data"]["services"]
    assert isinstance(services, list)
    assert any(svc["id"] == "order_entrust" for svc in services)
    order_entrust = next(s for s in services if s["id"] == "order_entrust")
    assert "modules" in order_entrust
    # The service-level endpoint_count lives on the module entries; ensure at
    # least one module has a non-zero count.
    assert any(m.get("endpoint_count", 0) >= 1 for m in order_entrust["modules"])


def test_tree_unknown_system_returns_404(http_client: TestClient) -> None:
    resp = http_client.get("/api/systems/nonexistent/tree")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
