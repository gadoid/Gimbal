"""Generator-catalog proxy 面单测 —— plate generators dim 代理三态。

设计: src/gimbal-platform/docs/superpowers/specs/2026-08-26-constant-pool-design.md §后端代理
与 test_strategy_catalog.py 同构: plate ok / plate 404 / plate 5xx /
连不上,验证信封解包与错误码映射(502 plate_unavailable、404
generator_kind_not_found)。
"""
from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient

from .helpers import register_and_login

_LIST_ENVELOPE = {
    "ok": True,
    "dim": "generators",
    "data": {
        "items": [
            {"kind": "uuid", "summary": "UUID"},
            {"kind": "seq", "summary": "自增序号"},
        ],
        "total": 2,
    },
}

_FULL_ENVELOPE = {
    "ok": True,
    "dim": "generators",
    "data": {
        "item": {
            "kind": "seq",
            "summary": "自增序号",
            "description": "执行内自增序号。",
            "params": [
                {"name": "prefix", "type": "string", "required": False,
                 "default": "", "description": "序号前缀"},
            ],
            "example": {"kind": "seq", "prefix": "BL", "width": 6, "start": 1},
        }
    },
}


class GeneratorPlateMock:
    """Programmable Plate mock for the generators dim endpoints.

    behaviour: ok | not_found | server_error | unavailable
    (StrategyPlateMock 模式: install() 换 plate_client 单例,
    handler 按当前 behaviour 分派。)
    """

    def __init__(self) -> None:
        self.behaviour: str = "ok"

    def install(self) -> None:
        mock = self

        async def handler(request: httpx.Request) -> httpx.Response:
            if mock.behaviour == "unavailable":
                raise httpx.ConnectError("plate down", request=request)
            if mock.behaviour == "server_error":
                return httpx.Response(500, text="boom")
            if mock.behaviour == "not_found":
                return httpx.Response(
                    404, json={"ok": False, "error": {"code": "dim_item_not_found"}}
                )
            path = request.url.path
            if path == "/api/generators":
                return httpx.Response(200, json=_LIST_ENVELOPE)
            if path.startswith("/api/generators/") and path.endswith("/full"):
                return httpx.Response(200, json=_FULL_ENVELOPE)
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
def generator_plate_mock():
    mock = GeneratorPlateMock()
    mock.install()
    try:
        yield mock
    finally:
        mock.uninstall()


async def _auth(client: AsyncClient) -> dict[str, str]:
    return await register_and_login(client, "alice", "secret-123")


@pytest.mark.parametrize("behaviour", ["ok", "server_error", "unavailable"])
async def test_b10_list_proxy_states(
    client: AsyncClient, generator_plate_mock: GeneratorPlateMock, behaviour: str
) -> None:
    generator_plate_mock.behaviour = behaviour
    headers = await _auth(client)
    r = await client.get("/api/generator-catalog", headers=headers)
    if behaviour == "ok":
        assert r.status_code == 200
        assert r.json() == _LIST_ENVELOPE["data"]["items"]
    else:
        assert r.status_code == 502
        assert r.json()["detail"]["code"] == "plate_unavailable"


async def test_b11_full_proxy_states(
    client: AsyncClient, generator_plate_mock: GeneratorPlateMock
) -> None:
    headers = await _auth(client)

    generator_plate_mock.behaviour = "ok"
    r = await client.get("/api/generator-catalog/seq/full", headers=headers)
    assert r.status_code == 200
    assert r.json()["kind"] == "seq"
    assert r.json()["example"]["kind"] == "seq"

    generator_plate_mock.behaviour = "not_found"
    r = await client.get("/api/generator-catalog/nope/full", headers=headers)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "generator_kind_not_found"
