"""B1: enumerate candidate JSONPaths from a response body sample (M6 grammar).

M6 mapping (ADR 0002 §D1):
    POST /api/endpoints/{id}/resolve-paths
        → POST /api/endpoint/{id}/action/resolve-paths
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_resolve_paths_for_nested_sample(http_client: TestClient) -> None:
    sample = {
        "code": 0,
        "data": {
            "order_id": "o-1",
            "order_no": "n-1",
            "shipping": {"method": "air", "fee": 12.5},
        },
    }
    resp = http_client.post(
        "/api/endpoint/fin.order_entrust.order_add/action/resolve-paths",
        json={"response_body_sample": sample},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "endpoint"
    paths = body["data"]["paths"]
    by_path = {p["path"]: p for p in paths}
    assert "$.code" in by_path
    assert "$.data" in by_path
    assert "$.data['order_id']" in by_path
    assert "$.data['shipping']" in by_path
    assert by_path["$.data['order_id']"]["depth"] == 2


def test_resolve_paths_unknown_endpoint_returns_404(http_client: TestClient) -> None:
    resp = http_client.post(
        "/api/endpoint/missing.id/action/resolve-paths",
        json={"response_body_sample": {"a": 1}},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"


def test_resolve_paths_non_object_returns_empty(http_client: TestClient) -> None:
    resp = http_client.post(
        "/api/endpoint/fin.order_entrust.order_add/action/resolve-paths",
        json={"response_body_sample": "just a string"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["paths"] == []