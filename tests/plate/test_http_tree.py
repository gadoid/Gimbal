"""A2: per-dim tree under a system (M6 grammar).

M6 mapping (ADR 0002 §D1):
    GET /api/systems/{system_id}/tree           → GET /api/systems/{system}/{dim}/tree
    (404 on unknown system → error.code == 'system_not_found')

Phase α: the generic tree handler returns the dim's ``list_for_system``
output under ``data.tree``; for ``system`` dim this is the system summary
dict. Per-dim richer tree shapes (service-with-modules, endpoint-by-method)
are deferred to Phase β — see ADR 0002 §D-D7.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_tree_for_fin_returns_system_summary(http_client: TestClient) -> None:
    resp = http_client.get("/api/systems/fin/system/tree")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "system"
    tree = body["data"]["tree"]
    assert isinstance(tree, list)
    assert len(tree) == 1
    assert tree[0]["id"] == "fin"
    assert tree[0]["service_count"] >= 1
    assert tree[0]["endpoint_count"] >= 1


def test_tree_unknown_system_returns_404(http_client: TestClient) -> None:
    resp = http_client.get("/api/systems/nonexistent/system/tree")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "system_not_found"