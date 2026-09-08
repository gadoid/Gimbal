"""GET /api/query-views 只读聚合路由(spec §3.4)+ 索引 golden。"""
import json
import os
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "query_views_index.json"
CAPTURE = bool(os.environ.get("GIMBAL_GOLDEN_CAPTURE"))


def _rows(http_client):
    r = http_client.get("/api/query-views")
    assert r.status_code == 200
    body = r.json()
    data = body.get("data") or body  # 信封或裸,以实现为准但必须稳定
    return data["items"]


def test_route_shape(http_client):
    items = _rows(http_client)
    names = {i["name"] for i in items}
    assert {"cost_list", "pending_orders"} <= names
    by_name = {i["name"]: i for i in items}
    po = by_name["pending_orders"]
    assert po["endpoint_id"] == "fin.order_entrust.order_page"
    assert po["method"] == "POST" and po["query_safe"] is True
    assert po["params"]["entrust_status"] == "1"
    assert "order_no" in po["columns"] and "bl_no" in po["columns"]
    cl = by_name["cost_list"]
    assert cl["endpoint_id"] == "fin.cost.amount_list"
    assert cl["columns"] == ["cost_name", "cost_id"]
    assert cl["auth"] == "bearer"


def test_capture_or_equal(http_client):
    live = _rows(http_client)
    if CAPTURE and not FIXTURE.exists():
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(live, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        pytest.skip("query-views index baseline captured")
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert live == base, "query-views 索引漂移(golden 基线)"
