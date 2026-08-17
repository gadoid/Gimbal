"""strategy_catalog 代理路由测试 —— Platform → Plate 的策略语法 dim 代理。

设计: docs/superpowers/plans/2026-08-17-strategy-syntax-service.md Task 3

用 httpx.MockTransport 替换 app.services.plate_client 的单例 client,
锁定三路行为:
* ``GET /api/strategy-catalog`` —— 200 解信封返回 items 数组;
* ``GET /api/strategy-catalog/{kind}/full`` —— 200 解信封返回 item,
  plate 404 → platform 404,plate 连不上 → 502 plate_unavailable;
* plate 5xx → 502 plate_unavailable。
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import AsyncClient

# plate /api/strategy 的标准信封(实测形状,Task 2 活体验证过)
_LIST_ENVELOPE: dict[str, Any] = {
    "ok": True,
    "dim": "strategy",
    "data": {
        "items": [
            {"kind": "extract", "label": "从响应提取变量", "phase": "after_request"},
            {"kind": "assign", "label": "准备入参赋值", "phase": "before_request"},
            {"kind": "assertion", "label": "响应断言", "phase": "verifying"},
        ],
        "total": 3,
    },
}

_FULL_ENVELOPE: dict[str, Any] = {
    "ok": True,
    "dim": "strategy",
    "data": {
        "item": {
            "kind": "extract",
            "label": "从响应提取变量",
            "phase": "after_request",
            "fields": [
                {
                    "name": "expression", "path": "$.expression",
                    "required": True, "default": None, "description": "",
                    "enum": None, "ui_kind": "text",
                },
            ],
            "base_fields": [
                {
                    "name": "order", "path": "$.order",
                    "required": False, "default": 0, "description": "",
                    "enum": None, "ui_kind": "number",
                },
            ],
        },
    },
}


class StrategyPlateMock:
    """Programmable Plate mock for the strategy dim endpoints."""

    def __init__(self) -> None:
        self.behaviour: str = "ok"  # ok | 404 | 5xx | unavailable
        self.list_calls: int = 0

    def install(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/strategy":
                self.list_calls += 1
                if self.behaviour == "ok":
                    return httpx.Response(200, json=_LIST_ENVELOPE)
                if self.behaviour == "5xx":
                    return httpx.Response(500, text="plate crashed")
                if self.behaviour == "unavailable":
                    raise httpx.ConnectError("connection refused", request=request)
            if path.startswith("/api/strategy/") and path.endswith("/full"):
                if self.behaviour == "ok":
                    return httpx.Response(200, json=_FULL_ENVELOPE)
                if self.behaviour == "404":
                    return httpx.Response(
                        404,
                        json={
                            "ok": False,
                            "error": {
                                "code": "dim_item_not_found",
                                "message": "no such kind",
                            },
                        },
                    )
                if self.behaviour == "5xx":
                    return httpx.Response(500, text="plate crashed")
                if self.behaviour == "unavailable":
                    raise httpx.ConnectError("connection refused", request=request)
            return httpx.Response(404)

        from app.services import plate_client

        plate_client.set_client_for_tests(
            httpx.AsyncClient(
                transport=httpx.MockTransport(handler), base_url="http://plate-test"
            )
        )

    def uninstall(self) -> None:
        from app.services import plate_client

        plate_client.set_client_for_tests(None)


@pytest.fixture
def strategy_plate_mock():
    mock = StrategyPlateMock()
    mock.install()
    try:
        yield mock
    finally:
        mock.uninstall()


async def _login(client: AsyncClient) -> dict[str, str]:
    await client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "password": "alicepass123",
            "display_name": "alice",
        },
    )
    r = await client.post(
        "/api/auth/login", json={"username": "alice", "password": "alicepass123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ── list ───────────────────────────────────────────────────────────

async def test_list_returns_items_array(
    client: AsyncClient, strategy_plate_mock: StrategyPlateMock
) -> None:
    headers = await _login(client)
    r = await client.get("/api/strategy-catalog", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    kinds = {it["kind"] for it in body}
    assert kinds == {"extract", "assign", "assertion"}
    assert strategy_plate_mock.list_calls == 1


async def test_list_plate_unavailable_502(
    client: AsyncClient, strategy_plate_mock: StrategyPlateMock
) -> None:
    strategy_plate_mock.behaviour = "unavailable"
    headers = await _login(client)
    r = await client.get("/api/strategy-catalog", headers=headers)
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "plate_unavailable"


async def test_list_plate_5xx_502(
    client: AsyncClient, strategy_plate_mock: StrategyPlateMock
) -> None:
    strategy_plate_mock.behaviour = "5xx"
    headers = await _login(client)
    r = await client.get("/api/strategy-catalog", headers=headers)
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "plate_unavailable"


# ── detail /full ───────────────────────────────────────────────────

async def test_full_returns_item(
    client: AsyncClient, strategy_plate_mock: StrategyPlateMock
) -> None:
    headers = await _login(client)
    r = await client.get("/api/strategy-catalog/extract/full", headers=headers)
    assert r.status_code == 200
    item = r.json()
    assert item["kind"] == "extract"
    assert item["fields"][0]["name"] == "expression"
    assert item["base_fields"][0]["name"] == "order"


async def test_full_plate_404_maps_404(
    client: AsyncClient, strategy_plate_mock: StrategyPlateMock
) -> None:
    strategy_plate_mock.behaviour = "404"
    headers = await _login(client)
    r = await client.get("/api/strategy-catalog/strategy_ref/full", headers=headers)
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["code"] in ("strategy_kind_not_found", "dim_item_not_found")


async def test_full_plate_unavailable_502(
    client: AsyncClient, strategy_plate_mock: StrategyPlateMock
) -> None:
    strategy_plate_mock.behaviour = "unavailable"
    headers = await _login(client)
    r = await client.get("/api/strategy-catalog/extract/full", headers=headers)
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "plate_unavailable"
