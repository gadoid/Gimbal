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
    # 2026-09-08 cost_amount_list 入册(动态取数源 §3.1),20 → 21;
    # 2026-09-09 客户域三端点入册(§13 级联链),21 → 24;
    # S1-0 B3(2026-10-07):order_add_demo 删除 + order_dispatch 停注(同坐标
    # 双注违反 F3),25 → 23
    assert body["data"]["total"] == len(items) == 23
    for ep in items:
        assert ep["system"] == "fin"
        assert "id" in ep
        assert "method" in ep
        assert "path" in ep


def test_filter_by_service(http_client: TestClient) -> None:
    # fin 全部 endpoint 统一归属单一服务 fin-service:
    # 按 service 过滤应命中全部 25 个(过滤一个不存在的服务则返回 0;
    # 2026-09-06 order_confirm 并入 fin.order.order_add,21 → 20;
    # 2026-09-08 cost_amount_list 入册,20 → 21;
    # 2026-09-09 客户域三端点入册,21 → 24;
    # 2026-09-20 order_add_demo 入册,24 → 25;S1-0 B3(2026-10-07)
    # demo 删除 + order_dispatch 停注,25 → 23。
    resp = http_client.get("/api/endpoint", params={"service": "fin-service"})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert resp.json()["data"]["total"] == 23
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
    # ``fin.order_entrust.order_add`` / ``fin.order.order_add`` 含子串
    # "order_add" — 2 命中(S1-0 B3:demo 已删、dispatch 名为 order_dispatch
    # 本就不含 "order_add" 全串)。
    assert data["total"] == 2
    for ep in data["items"]:
        assert ep["id"] in {
            "fin.order_entrust.order_add",
            "fin.order.order_add",
        }