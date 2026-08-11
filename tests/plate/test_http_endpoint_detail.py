"""A4: full EndpointSpec contract (M6 grammar).

M6 mapping (ADR 0002 §D1):
    GET /api/endpoints/{endpoint_id}     → GET /api/endpoint/{endpoint_id}

Phase α: the detail handler returns the ``EndpointView.from_spec`` minimal
view (id / system / service / name / method / path / module / tags / version).
The full contract lives in ``EndpointDetailView`` and is exposed in Phase β —
see ADR 0002 §D-D6. So this test now asserts the minimal-view contract.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_endpoint_detail_returns_minimal_view(http_client: TestClient) -> None:
    resp = http_client.get("/api/endpoint/fin.order_entrust.order_add")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "endpoint"
    data = body["data"]
    item = data["item"]
    for key in ("id", "system", "service", "name", "method", "path", "version"):
        assert key in item, key
    assert item["id"] == "fin.order_entrust.order_add"
    assert item["system"] == "fin"
    assert item["service"] == "order_entrust"


def test_endpoint_detail_unknown_returns_404(http_client: TestClient) -> None:
    resp = http_client.get("/api/endpoint/does.not.exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"