"""strategy dim HTTP 面单测 —— M6 通用路由上的第 8 个 dim。

设计: docs/superpowers/specs/2026-08-17-strategy-syntax-service-design.md §3.1
全部走既有通用 handler(list/detail/full/系统作用域/references),零新路由代码;
本文件验证注册后这些路由对 strategy dim 的行为。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gimbal_plate import ApiSpec, EndpointSpec, ResponseSpec
from gimbal_plate.http import create_app
from gimbal_plate.registry import PlateRegistry


def _ok(body: dict) -> None:
    assert body["ok"] is True
    assert body["dim"] == "strategy"


@pytest.fixture
def fin_client(fresh_registry: PlateRegistry) -> TestClient:
    """带一个已注册 fin endpoint 的 client —— 让 ``has_system('fin')`` 为 True。

    通用路由的 ``_resolve_system`` 以 registry 里是否有该 system 的 endpoint
    为准;共享 conftest 的 fresh_registry 按约定不注册 endpoints(docstring:
    caller's job),系统作用域路由因此 404。strategy 语法虽全局,但走的是
    同一条系统作用域路由,需要这个最小前提。只注册一个,不引入
    ALL_ENDPOINTS 的 18 条对其他用例的计数污染。
    """
    fresh_registry.register_endpoint(EndpointSpec(
        id="fin.probe.minimal", system="fin", service="probe", name="探针",
        api=ApiSpec(service="probe", method="GET", path="/probe"),
        responses={200: ResponseSpec(status=200, description="成功")},
    ))
    from fastapi.testclient import TestClient as _TC  # noqa: F811
    with _TC(create_app(registry=fresh_registry)) as client:
        yield client


def test_list_returns_three_kinds(http_client: TestClient) -> None:
    resp = http_client.get("/api/strategy")
    assert resp.status_code == 200
    body = resp.json()
    _ok(body)
    kinds = {it["kind"]: it for it in body["data"]["items"]}
    assert set(kinds.keys()) == {"extract", "assign", "assertion"}
    assert body["data"]["total"] == 3
    # light view 只有 kind/label/phase 三键
    assert set(kinds["extract"].keys()) == {"kind", "label", "phase"}
    assert kinds["extract"]["label"] == "从响应提取变量"


def test_detail_full_returns_field_descriptors(http_client: TestClient) -> None:
    resp = http_client.get("/api/strategy/extract/full")
    assert resp.status_code == 200
    body = resp.json()
    _ok(body)
    item = body["data"]["item"]
    assert item["kind"] == "extract"
    fields = {f["name"]: f for f in item["fields"]}
    assert fields["expression"]["ui_kind"] == "text"
    assert fields["expression"]["required"] is True
    assert fields["scope"]["ui_kind"] == "select"
    assert "scenario" in fields["scope"]["enum"]
    # base_fields 拆分: StrategyBase 公共字段在此,业务字段不在此
    base_names = {f["name"] for f in item["base_fields"]}
    assert "order" in base_names and "onFailure" in base_names
    assert "expression" not in base_names


def test_detail_full_assertion_operator_enum(http_client: TestClient) -> None:
    resp = http_client.get("/api/strategy/assertion/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    op = next(f for f in item["fields"] if f["name"] == "operator")
    assert op["ui_kind"] == "select"
    assert len(op["enum"]) == 14


def test_strategy_ref_excluded_404(http_client: TestClient) -> None:
    """strategy_ref 是预埋字段 —— 不在 dim 输出中,按未知 kind 处理。"""
    resp = http_client.get("/api/strategy/strategy_ref/full")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"


def test_unknown_kind_404(http_client: TestClient) -> None:
    resp = http_client.get("/api/strategy/nope")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"


def test_system_scoped_returns_same_as_global(fin_client: TestClient) -> None:
    """语法是全局的 —— 系统作用域返回与全局一致的 kinds。"""
    resp = fin_client.get("/api/systems/fin/strategy")
    assert resp.status_code == 200
    body = resp.json()
    _ok(body)
    global_kinds = {
        it["kind"] for it in fin_client.get("/api/strategy").json()["data"]["items"]
    }
    assert {it["kind"] for it in body["data"]["items"]} == global_kinds


def test_system_scoped_full_detail(fin_client: TestClient) -> None:
    resp = fin_client.get("/api/systems/fin/strategy/extract/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    assert item["kind"] == "extract"


def test_references_returns_empty_signals(http_client: TestClient) -> None:
    """strategy 走通用 /references 的 else 分支 —— 空 signals,不报错。"""
    resp = http_client.get("/api/strategy/extract/references")
    assert resp.status_code == 200
    body = resp.json()
    _ok(body)
    assert body["data"]["references"]["systems"] == []


@pytest.mark.parametrize("path", [
    "/api/strategy",
    "/api/strategy/extract",
    "/api/strategy/extract/full",
])
def test_envelope_shape(http_client: TestClient, path: str) -> None:
    """信封与其他 dim 一致: ok/dim/data + 元信息。"""
    resp = http_client.get(path)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "strategy"
    assert "data" in body
