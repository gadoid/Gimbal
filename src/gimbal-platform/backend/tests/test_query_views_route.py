"""rows 路由:鉴权门 / 参数 / 错误形状 / query_user 键(spec §4.1/§6.1)。"""
import httpx
import pytest

from app.services import query_view_runner as run
from tests.helpers import register_and_login


@pytest.fixture(autouse=True)
def _reset_runner():
    """索引 memo/缓存是模块级状态——每例隔离,防前例 IDX 污染后例断言。"""
    run.reset_state_for_tests()
    yield
    run.reset_state_for_tests()


def _install_plate(monkeypatch, items):
    from app.services import plate_client
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"items": items, "total": len(items)}})
    # 收尾恢复靠 conftest autouse _default_plate_stub 的 LIFO reset
    # (set_client_for_tests(None)),与既有 plate-mock 测试同款约定。
    plate_client.set_client_for_tests(
        httpx.AsyncClient(transport=httpx.MockTransport(handler),
                          base_url="http://plate-test"))


_IDX = [{
    "name": "v1", "endpoint_id": "t.a", "system": "t", "service": "svc",
    "method": "GET", "path": "/api/a", "params": {}, "items": "$.d[*]",
    "label": "nm", "columns": ["nm"], "query_safe": False,
    "missing_required": [], "auth": "none", "timeout_seconds": 5.0,
}]


async def test_requires_auth(client):
    r = await client.get("/api/query-views/v1/rows")
    assert r.status_code == 401


async def test_ok_shape(client, monkeypatch):
    _install_plate(monkeypatch, _IDX)
    monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(
        200, json={"d": [{"nm": "x"}]}))
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows",
                         params={"service_url": "http://sut"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["view"] == "v1" and body["rows"] == [{"nm": "x"}]
    assert body["cached"] is False and body["stale"] is False
    assert body["truncated"] is False and "fetched_at" in body


async def test_unknown_view_404_shape(client, monkeypatch):
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client)
    r = await client.get("/api/query-views/nope/rows",
                         params={"service_url": "http://sut"}, headers=h)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "unknown_view"


async def test_missing_service_url_422(client, monkeypatch):
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows", headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "service_url_required"


async def test_bearer_without_alias_422(client, monkeypatch):
    idx = [dict(_IDX[0], auth="bearer")]
    _install_plate(monkeypatch, idx)
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows",
                         params={"service_url": "http://sut"}, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "query_credential_required"


async def test_query_user_binding_field():
    from app.schemas.scenario_composer import ServiceBinding
    b = ServiceBinding.model_validate({"authAlias": "main", "queryUser": "q1",
                                       "url": "http://s"})
    assert b.query_user == "q1" and b.auth_alias == "main"
    assert ServiceBinding.model_validate({"authAlias": "main"}).query_user is None
