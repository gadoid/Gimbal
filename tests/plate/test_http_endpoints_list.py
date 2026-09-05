"""A3: list endpoints (M6 grammar — global list with filters).

M6 mapping (ADR 0002 §D1 / §D2):
    GET /api/systems/{system_id}/services/{service}/endpoints
        → GET /api/systems/{system}/endpoint        (system-scoped, no filters)
        or
        → GET /api/endpoint?service=...&method=...&q=... (global, with filters)

The system-scoped variant returns all endpoints under the system; the
global variant supports A3-style query filters (service / module / method /
q / tag).
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_endpoints_under_system(http_client: TestClient) -> None:
    resp = http_client.get("/api/systems/fin/endpoint")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "endpoint"
    items = body["data"]["items"]
    assert body["data"]["total"] == len(items) == 21
    for ep in items:
        assert ep["system"] == "fin"
        assert "id" in ep
        assert "method" in ep
        assert "path" in ep


def test_filter_by_service(http_client: TestClient) -> None:
    # fin 全部 endpoint 统一归属单一服务 fin-service:
    # 按 service 过滤应命中全部 21 个(过滤一个不存在的服务则返回 0)。
    resp = http_client.get("/api/endpoint", params={"service": "fin-service"})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert resp.json()["data"]["total"] == 21
    for ep in items:
        assert ep["system"] == "fin"
        assert ep["service"] == "fin-service"


def test_filter_by_method(http_client: TestClient) -> None:
    resp = http_client.get(
        "/api/endpoint", params={"service": "fin-service", "method": "POST"}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 1
    for ep in data["items"]:
        assert ep["method"] == "POST"


def test_filter_by_q(http_client: TestClient) -> None:
    resp = http_client.get("/api/endpoint", params={"q": "order_add"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Both ``fin.order_entrust.order_add`` and ``fin.order.order_add`` match
    # the substring "order_add" — there are 2 hits in the bundled fin system.
    assert data["total"] == 2
    for ep in data["items"]:
        assert ep["id"].endswith("order_add")