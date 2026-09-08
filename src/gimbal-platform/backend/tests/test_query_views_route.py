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


async def test_bearer_credential_loader_path(client, monkeypatch):
    """装载通路端到端:bearer 视图 + query_alias + 真实 auth_sessions 行。

    路由 _loader 是 async 闭包(异步 DB 会话)—— runner 凭证闸必须
    await 它(与 httpx.request seam 同款双形态判别)。登录与 SUT 打桩:
    _AUTHENTICATE seam 发 token,httpx.request 回行集。
    """
    idx = [dict(_IDX[0], auth="bearer")]
    _install_plate(monkeypatch, idx)
    h = await register_and_login(client)
    seeded = await client.post("/api/auths", headers=h, json={
        "alias": "qa", "url": "http://sut/auth",
        "username": "u", "password": "p",
        "token_type": "Bearer", "expires_in": 3600,
    })
    assert seeded.status_code == 201, seeded.text

    def fake_auth(session, why):
        session.apply_token("tok-1", 3600)
    monkeypatch.setattr(run, "_AUTHENTICATE", fake_auth)
    monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(
        200, json={"d": [{"nm": "y"}]}))
    r = await client.get("/api/query-views/v1/rows",
                         params={"service_url": "http://sut",
                                 "query_alias": "qa"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["view"] == "v1" and body["rows"] == [{"nm": "y"}]
    assert body["cached"] is False and body["stale"] is False


async def test_query_user_binding_field():
    from app.schemas.scenario_composer import ServiceBinding
    b = ServiceBinding.model_validate({"authAlias": "main", "queryUser": "q1",
                                       "url": "http://s"})
    assert b.query_user == "q1" and b.auth_alias == "main"
    assert ServiceBinding.model_validate({"authAlias": "main"}).query_user is None
