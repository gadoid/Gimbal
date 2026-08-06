"""A3: list endpoints under a service with filters."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_endpoints_under_service(http_client: TestClient) -> None:
    resp = http_client.get(
        "/api/systems/fin/services/order_entrust/endpoints"
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    for ep in data["endpoints"]:
        assert ep["system"] == "fin"
        assert ep["service"] == "order_entrust"
        assert "id" in ep
        assert "method" in ep
        assert "path" in ep


def test_filter_by_method(http_client: TestClient) -> None:
    resp = http_client.get(
        "/api/systems/fin/services/order_entrust/endpoints",
        params={"method": "POST"},
    )
    data = resp.json()["data"]
    assert data["total"] >= 1
    for ep in data["endpoints"]:
        assert ep["method"] == "POST"


def test_filter_by_q(http_client: TestClient) -> None:
    resp = http_client.get(
        "/api/systems/fin/services/order_entrust/endpoints",
        params={"q": "order_add"},
    )
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["endpoints"][0]["id"].endswith("order_add")


def test_unknown_service_returns_404(http_client: TestClient) -> None:
    resp = http_client.get(
        "/api/systems/fin/services/does_not_exist/endpoints"
    )
    assert resp.status_code == 404
