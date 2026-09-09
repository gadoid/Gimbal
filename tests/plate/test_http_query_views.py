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
    # §13 客户域三级链路视图
    assert {"customer_list", "customer_part", "customer_policy"} <= names
    cl1 = by_name["customer_list"]
    assert cl1["endpoint_id"] == "fin.customer.list"
    assert cl1["query_params"] == []                    # 无参 = 现状通道
    assert "customer_id" in cl1["columns"] and "customer_name" in cl1["columns"]
    cp = by_name["customer_part"]
    assert cp["endpoint_id"] == "fin.customer.part"
    assert cp["query_params"] == ["customer_id"]
    assert cp["items"] == "$.data"                      # 单对象型(§13.4)
    assert cp["label"] == "customer_service.user_name"
    assert "handover_form.client_expand_id" in cp["columns"]
    assert cp["missing_required"] == ["customer_id"]    # 静态链视角;点击期补齐
    po3 = by_name["customer_policy"]
    assert po3["endpoint_id"] == "fin.customer.policy"
    assert po3["query_params"] == ["customer_id"]
    assert po3["params"]["status"] == "2"               # 静态预设
    assert "customer_id" not in po3["params"]           # 点击期供给,静态面不含
    assert po3["missing_required"] == ["customer_id"]


def test_capture_or_equal(http_client):
    live = _rows(http_client)
    if CAPTURE and not FIXTURE.exists():
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(live, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        pytest.skip("query-views index baseline captured")
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert live == base, "query-views 索引漂移(golden 基线)"
