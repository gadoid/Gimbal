"""Endpoint-catalog resolve-paths 代理面单测 —— plate dim action 代理三态。

设计: B1 路径推断(resolve-paths)由 plate 实现源(响应样本 → 候选
JSONPath,数组展开下标),平台代理让前端只打一个 API 面。与
test_generator_catalog_proxy.py 同构: plate ok / plate 5xx /
连不上,验证信封解包与错误码映射(502 plate_unavailable)。

action 名是连字符 ``resolve-paths``(fin 系统 endpoint dim 注册名,
见 gimbal_plate/systems/fin/dimensions.py),不是下划线。
"""
from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient

from .helpers import register_and_login

_OK_ENVELOPE = {
    "ok": True,
    "data": {
        "paths": [
            {"path": "$.code", "depth": 1, "extracted_by_default": False},
            {"path": "$.data['data'][0]['order_id']", "depth": 4, "extracted_by_default": False},
        ]
    },
}

_SAMPLE = {"code": 0, "data": {"data": [{"order_id": "BL123"}], "total": 1}}


class EndpointPlateMock:
    """Programmable Plate mock for the endpoint resolve-paths action.

    behaviour: ok | server_error | unavailable | bad_envelope
    (GeneratorPlateMock 模式: install() 换 plate_client 单例,
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
            if mock.behaviour == "bad_envelope":
                return httpx.Response(200, json={"ok": True, "data": {}})
            if request.url.path == "/api/endpoint/action/resolve-paths":
                return httpx.Response(200, json=_OK_ENVELOPE)
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
def endpoint_plate_mock():
    mock = EndpointPlateMock()
    mock.install()
    try:
        yield mock
    finally:
        mock.uninstall()


async def _auth(client: AsyncClient) -> dict[str, str]:
    return await register_and_login(client, "alice", "secret-123")


async def test_resolve_paths_ok(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock
) -> None:
    """ok: 解 data.paths 返回候选数组(含数组下标路径原样透传)。"""
    headers = await _auth(client)
    r = await client.post(
        "/api/endpoint-catalog/resolve-paths",
        json={"response_body_sample": _SAMPLE},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json() == _OK_ENVELOPE["data"]["paths"]


async def test_resolve_paths_bad_sample_422(client: AsyncClient) -> None:
    """response_body_sample 缺失 → 422(FastAPI 校验),不透传 plate。"""
    headers = await _auth(client)
    r = await client.post("/api/endpoint-catalog/resolve-paths", json={}, headers=headers)
    assert r.status_code == 422


@pytest.mark.parametrize("behaviour", ["server_error", "unavailable", "bad_envelope"])
async def test_resolve_paths_failure_states(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock, behaviour: str
) -> None:
    """plate 5xx / 连不上 / 信封缺 paths → 502 plate_invalid_envelope 或 plate_unavailable。"""
    endpoint_plate_mock.behaviour = behaviour
    headers = await _auth(client)
    r = await client.post(
        "/api/endpoint-catalog/resolve-paths",
        json={"response_body_sample": _SAMPLE},
        headers=headers,
    )
    assert r.status_code == 502
    assert r.json()["detail"]["code"] in {"plate_unavailable", "plate_invalid_envelope"}
