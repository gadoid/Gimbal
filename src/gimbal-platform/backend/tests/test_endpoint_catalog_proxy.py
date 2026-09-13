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

from app.core.config import settings
from app.services import plate_client

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

    behaviour: ok | server_error | unavailable | bad_envelope | not_found | rejected
    (``not_found`` / ``rejected`` 只作用于 /full:plate 分别答 404 与 401,
    用于「端点不存在」与「plate 拒了这次请求」两条映射)。
    ``full_envelope`` 是 /full 的响应信封;None ⇒ /full 走 404。
    (GeneratorPlateMock 模式: install() 换 plate_client 单例,
    handler 按当前 behaviour 分派。)
    """

    def __init__(self) -> None:
        self.behaviour: str = "ok"
        # /full 的信封;None 时走 404(既有 resolve-paths 用例不受影响)
        self.full_envelope: dict | None = None

    def install(self) -> None:
        mock = self

        async def handler(request: httpx.Request) -> httpx.Response:
            if mock.behaviour == "unavailable":
                raise httpx.ConnectError("plate down", request=request)
            if mock.behaviour == "server_error":
                return httpx.Response(500, text="boom")
            if mock.behaviour == "bad_envelope":
                return httpx.Response(200, json={"ok": True, "data": {}})
            if request.url.path.endswith("/full"):
                if mock.behaviour == "not_found":
                    return httpx.Response(404, json={"ok": False})
                if mock.behaviour == "rejected":
                    return httpx.Response(401, json={"ok": False})
                if mock.full_envelope is None:
                    return httpx.Response(404)
                return httpx.Response(200, json=mock.full_envelope)
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


# ── GET /{endpoint_id}/full:item 原样 + declared_surface ──────────────
_FULL_ENVELOPE = {
    "ok": True,
    "dim": "endpoint",
    "data": {
        "item": {
            "request": {"declarations": [{"path": "$.customer.id"}]},
            "responses": {"200": {}},
        }
    },
}


async def test_full_surface_is_declared_half_only(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock
) -> None:
    """declared_surface = 声明半(含 $ 与容器前缀);item 必须原样并存。

    item 的第二个消费者是候选树 UI(buildTree/prefillBindings)—— 本任务只
    **增加**字段,不得裁剪 item。
    """
    endpoint_plate_mock.full_envelope = _FULL_ENVELOPE
    headers = await _auth(client)
    r = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["declared_surface"] == ["$", "$.customer", "$.customer.id"]
    # 整体比对(不只看 request):漏了 responses 键同样是「裁剪 item」,也要红。
    assert {k: v for k, v in body.items() if k != "declared_surface"} == \
        _FULL_ENVELOPE["data"]["item"]


async def test_full_surface_empty_decls_is_just_dollar(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock
) -> None:
    """真无声明 → ["$"],**不是** null —— 空目录与降级是两件事。"""
    endpoint_plate_mock.full_envelope = {
        "ok": True, "dim": "endpoint",
        "data": {"item": {"request": {"declarations": []}, "responses": {}}},
    }
    headers = await _auth(client)
    r = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
    assert r.json()["declared_surface"] == ["$"]


async def test_full_empty_item_is_served_not_an_error(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock
) -> None:
    """空 item ``{}`` 是**合法 item** → 200 + 空声明树 ``["$"]``,不是信封坏。

    取数层只校验 item 是 dict,故 ``{}`` 通过并入缓存;代理据此判 ``is None`` 判真
    ⇒ 正常服务。**不得**改用真值判等(`if not item`)把它并成「信封不可用」——
    ``{}`` 是有意义的 falsy 值(§5),它意味着「这个端点还没有声明树」。
    """
    endpoint_plate_mock.full_envelope = {
        "ok": True, "dim": "endpoint", "data": {"item": {}},
    }
    headers = await _auth(client)
    r = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert {k: v for k, v in body.items() if k != "declared_surface"} == {}
    assert body["declared_surface"] == ["$"]


async def test_full_surface_is_null_when_declarations_are_garbage(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock
) -> None:
    """item 在但 declarations 是垃圾值 → declared_surface **显式 null**(降级)。

    ⚠ `null` 只有这一个入口:`item` 本身不可得时代理直接 502,前端根本
    看不到这个字段。spec §2.2 说「降级 → null」指的是本条,plan 在此写明。
    """
    endpoint_plate_mock.full_envelope = {
        "ok": True, "dim": "endpoint",
        "data": {"item": {"request": {"declarations": "garbage"}, "responses": {}}},
    }
    headers = await _auth(client)
    r = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
    assert r.status_code == 200
    assert r.json()["declared_surface"] is None


@pytest.mark.parametrize("behaviour,expected,code", [
    ("unavailable", 502, "plate_unavailable"),        # 连不上:没拿到响应
    ("server_error", 502, "plate_unavailable"),       # 5xx:plate 挂了
    ("not_found", 404, "endpoint_not_found"),         # 拿到了 404
    ("rejected", 502, "plate_rejected"),              # 非 404 的 4xx:plate 拒了请求
    ("bad_envelope", 502, "plate_invalid_envelope"),  # 200 但信封里没有 item
])
async def test_full_failure_states(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock,
    behaviour: str, expected: int, code: str,
) -> None:
    """四种失败各有各的码,不得合并(§5):连不上 / 5xx / 端点不存在 / plate 拒绝 / 信封不可用。

    `plate_invalid_envelope` **收窄到 200**:它专指「拿到了 200 但信封里没有可用
    item」。plate 的 4xx(此处 401)是**它拒绝了这次请求**,不是信封坏 —— 压成
    `plate_invalid_envelope` 会把两个状态合并,并让前端看不出该不该重试。
    """
    endpoint_plate_mock.full_envelope = _FULL_ENVELOPE
    endpoint_plate_mock.behaviour = behaviour
    headers = await _auth(client)
    r = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
    assert r.status_code == expected
    detail = r.json()["detail"]
    assert detail["code"] == code
    if behaviour == "rejected":
        # message 必须带上 plate 的真实状态码(否则 4xx 的真话在链路上丢了)
        assert "401" in detail["message"]


async def test_full_stale_snapshot_survives_a_refresh_404(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock, monkeypatch
) -> None:
    """回退的旧快照 + 那次刷新拿的是 404 ⇒ 200(item + 面),**不是** endpoint_not_found。

    钉住 404 映射必须嵌在 ``item is None`` 里:刷新 404 时旧快照仍在回退窗内 ⇒
    ``item`` 是好的、``stale=True``、``status=404`` 三者同时成立 —— 无条件的
    ``status == 404 → endpoint_not_found`` 会把一次健康的旧契约服务(按旧面注入,
    是**有意**的 fail-open)报成「端点不存在」。
    """
    endpoint_plate_mock.full_envelope = _FULL_ENVELOPE
    headers = await _auth(client)
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.0)          # 立即过期
    monkeypatch.setattr(settings, "DECLARED_PATHS_STALE_WINDOW_SEC", 3600.0)
    first = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
    assert first.status_code == 200
    assert first.json()["declared_surface"] == ["$", "$.customer", "$.customer.id"]

    endpoint_plate_mock.behaviour = "not_found"        # 刷新失败:plate 答 404
    r = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert {k: v for k, v in body.items() if k != "declared_surface"} == \
        _FULL_ENVELOPE["data"]["item"]
    assert body["declared_surface"] == ["$", "$.customer", "$.customer.id"]


class _RecordingTransport(httpx.AsyncBaseTransport):
    """记录**逐请求**读超时的替身(生产链路经 ``timeout`` 扩展交给传输层)。

    httpx 的客户端级超时与逐请求超时都落到同一处,故读到的那个值回答了「代理
    用的是哪条上限」—— 判别力全落在这个值上,不涉及时序断言(无 sleep、无
    「用时 < N」这类会随环境漂移的断言)。
    """

    def __init__(self, handler) -> None:
        self._handler = handler
        self.seen_reads: list[float | None] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # §5 例外:两侧同为「未提供 timeout 扩展」的缺省形(None / {}),
        # 合并后 .get("read") 仍得 None。
        self.seen_reads.append((request.extensions.get("timeout") or {}).get("read"))
        return await self._handler(request)


async def test_full_uses_the_soft_fetch_timeout(client: AsyncClient) -> None:
    """``/full`` 代理走**软取**上限(3s),不是 ``PLATE_TIMEOUT_SEC``(30s)。

    本任务的**用户可见行为变更**就落在这一处:冷缓存 + 慢 plate 时,候选树从
    「等 30s 后报错」变「3s 后降级/供旧面」。客户端照生产设 30s,故读到的若是
    30.0 就说明这条路径又退回了客户端级上限(判别力所在)。
    """
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_FULL_ENVELOPE)

    transport = _RecordingTransport(handler)
    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=transport,
        base_url="http://plate-test",
        timeout=settings.PLATE_TIMEOUT_SEC,          # 生产同款 30s
    ))
    try:
        headers = await _auth(client)
        r = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
        assert r.status_code == 200
    finally:
        plate_client.set_client_for_tests(None)
    assert transport.seen_reads == [
        pytest.approx(settings.DECLARED_PATHS_TIMEOUT_SEC)
    ]
    assert settings.DECLARED_PATHS_TIMEOUT_SEC < settings.PLATE_TIMEOUT_SEC
