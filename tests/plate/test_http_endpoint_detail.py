"""A4: full EndpointSpec contract."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_endpoint_detail_returns_full_contract(http_client: TestClient) -> None:
    resp = http_client.get("/api/endpoints/fin.order_entrust.order_add")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for key in (
        "id", "system", "service", "name", "api",
        "request", "responses", "metadata", "version",
    ):
        assert key in data, key
    assert "fields" in data["request"]
    # JSON object keys are always strings; allow either form for clarity.
    assert any(k == 200 or k == "200" for k in data["responses"].keys())
    assert "fields" in data["responses"]["200"]
    assert "assertable_fields" in data["responses"]["200"]


def test_endpoint_detail_unknown_returns_404(http_client: TestClient) -> None:
    resp = http_client.get("/api/endpoints/does.not.exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
