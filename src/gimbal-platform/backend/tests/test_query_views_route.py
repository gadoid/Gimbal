"""rows 路由:鉴权门 / 参数 / 错误形状(spec §4.1/§6.1)。"""
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
    """01-04 后双通道二选一:无 service_url 也无 scenarioId+stepIndex →
    query_context_required(修前这里恒 service_url_required = 取数断链
    的显形;两通道语义见路由 docstring)。"""
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows", headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "query_context_required"


async def test_bearer_without_alias_422(client, monkeypatch):
    idx = [dict(_IDX[0], auth="bearer")]
    _install_plate(monkeypatch, idx)
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows",
                         params={"service_url": "http://sut"}, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "query_credential_required"


async def test_bearer_credential_loader_path(client, monkeypatch):
    """装载通路端到端:bearer 视图 + query_alias + 四件套布景(条目→ref→账户)。

    路由 _loader 是 async 闭包(异步 DB 会话)—— runner 凭证闸必须
    await 它(与 httpx.request seam 同款双形态判别)。登录与 SUT 打桩:
    _AUTHENTICATE seam 发 token,httpx.request 回行集。
    """
    idx = [dict(_IDX[0], auth="bearer")]
    _install_plate(monkeypatch, idx)
    h = await register_and_login(client)
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    from app.core import db as db_module
    from .conftest import seed_identity_fixture
    async with db_module.SessionLocal() as db:
        await seed_identity_fixture(
            db, alias="qa", username="u", password="p",
            service="svc", owner_id=uid, login_url="http://sut/auth")

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


# ── §13.3 索引代理 + rows 路由 params 点击期参数 ──────────────────

_PARAMS_IDX = [dict(_IDX[0], name="customer_part",
                    query_params=["customer_id"])]


async def test_index_proxy_shape(client, monkeypatch):
    _install_plate(monkeypatch, _PARAMS_IDX)
    h = await register_and_login(client)
    r = await client.get("/api/query-views", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["name"] == "customer_part" and i["query_params"] == ["customer_id"]
               for i in items)


async def test_rows_params_bad_json_422(client):
    h = await register_and_login(client)
    r = await client.get("/api/query-views/customer_part/rows",
                         params={"service_url": "http://sut",
                                 "params": "not-json"}, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "bad_params"


async def test_rows_params_non_object_422(client):
    h = await register_and_login(client)
    r = await client.get("/api/query-views/customer_part/rows",
                         params={"service_url": "http://sut",
                                 "params": "[1]"}, headers=h)
    assert r.status_code == 422


async def test_rows_params_non_scalar_value_422(client):
    """§13.7 手工逃生口:参数值须为标量 —— dict/list/null 污染下游序列化。"""
    h = await register_and_login(client)
    r = await client.get("/api/query-views/customer_part/rows",
                         params={"service_url": "http://sut",
                                 "params": '{"a":[1]}'}, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "bad_params"


# ── 同源兜底(2026-09-14 取数收窄 #2):service = 调用步骤的服务名 ────

async def test_rows_service_mismatch_422(client, monkeypatch):
    """视图声明 service=svc,调用步骤 service=other → 跨端点错配拒
    (否则请求打到 other 服务的 URL 上打 svc 端点的 path)。"""
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows",
                         params={"service_url": "http://sut",
                                 "service": "other"}, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "service_mismatch"


async def test_rows_service_match_ok(client, monkeypatch):
    _install_plate(monkeypatch, _IDX)   # v1 service=svc
    monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(
        200, json={"d": [{"nm": "x"}]}))
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows",
                         params={"service_url": "http://sut",
                                 "service": "svc"}, headers=h)
    assert r.status_code == 200, r.text


async def test_rows_service_absent_no_check(client, monkeypatch):
    """不传 service(旧调用方)→ 不校验,既有行为不变。"""
    _install_plate(monkeypatch, _IDX)
    monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(
        200, json={"d": [{"nm": "x"}]}))
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows",
                         params={"service_url": "http://sut"}, headers=h)
    assert r.status_code == 200, r.text


async def test_rows_params_passes_click_params(client, monkeypatch):
    captured = {}

    async def fake_fetch(name, *, refresh, service_url, owner_id,
                         query_alias, load_credential, click_params=None,
                         service=None, **_kwargs):
        # **_kwargs:§7.1 池通道后 fetch_rows 新增 cred_project_id 等
        # 键 —— 打桩面只断言本例关心的分量,签名不被 seam 锁死
        captured["click"] = click_params
        captured["service"] = service
        return run.RowsResult(name, [], False, "t", False, False)

    monkeypatch.setattr(run, "fetch_rows", fake_fetch)
    h = await register_and_login(client)
    r = await client.get("/api/query-views/customer_part/rows",
                         params={"service_url": "http://s", "service": "svc",
                                 "params": '{"customer_id":"1"}'}, headers=h)
    assert r.status_code == 200, r.text
    assert captured["click"] == {"customer_id": "1"}
    assert captured["service"] == "svc"


# ── 01-04 上下文通道:scenarioId + stepIndex → 服务端解析地址 ──────
# 修前:service_url 只能来自前端 authored config.services(地址面已随
# D2 环境退役,新场景恒空 ⇒ 恒 service_url_required)。本组钉:空
# config.services + 合法身份/环境/部署 ⇒ 查询成功;各缺口有专属错误码。

def _call_step(service: str = "svc", method: str = "GET") -> dict:
    return {
        "call": {"kind": "call", "protocol": "http", "service": service,
                 "method": method, "path": "/a", "headers": {}},
        "request": {"kind": "request", "body": {}},
    }


async def _save_scenario(client, headers, scenario_id: str, steps: list) -> None:
    from tests.helpers import make_draft
    r = await client.post("/api/scenarios", headers=headers,
                          json=make_draft(scenario_id, steps=steps))
    assert r.status_code == 201, r.text


async def test_context_channel_resolves_url(client, monkeypatch):
    """空 config.services + 四件套布景 → 上下文通道查询成功(断链收口主钉)。"""
    from app.core import db as db_module
    from .conftest import seed_identity_fixture

    _install_plate(monkeypatch, _IDX)          # 视图 v1:service=svc,auth=none
    hit = {}

    def fake_request(m, u, **kw):
        hit["url"] = u
        return httpx.Response(200, json={"d": [{"nm": "z"}]})
    monkeypatch.setattr(httpx, "request", fake_request)
    h = await register_and_login(client)
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    async with db_module.SessionLocal() as db:
        await seed_identity_fixture(
            db, alias="svc", username="su", password="sp",
            service="svc", owner_id=uid,
            env_name="查询环境", login_url=None,   # auth=none:登录口不需要
            base_url="https://svc-deploy.internal")
    await _save_scenario(client, h, "sc-ctx-ok", [_call_step("svc")])

    r = await client.get("/api/query-views/v1/rows",
                          params={"scenarioId": "sc-ctx-ok", "stepIndex": 0},
                          headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows"] == [{"nm": "z"}]
    # SUT 打到的 = 部署表地址(上下文解析,不是任何 authored services 值)
    assert hit["url"] == "https://svc-deploy.internal/api/a"


async def test_context_channel_bearer_owner_identity(client, monkeypatch):
    """bearer 视图经上下文通道:query_alias 缺省 = 步骤生效别名(执行
    视角),凭证按场景属主装载端到端打桩。"""
    from app.core import db as db_module
    from .conftest import seed_identity_fixture

    idx = [dict(_IDX[0], auth="bearer")]
    _install_plate(monkeypatch, idx)
    h = await register_and_login(client)
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    async with db_module.SessionLocal() as db:
        await seed_identity_fixture(
            db, alias="svc", username="su", password="sp",
            service="svc", owner_id=uid,
            env_name="查询环境", login_url="https://svc-deploy.internal/auth",
            base_url="https://svc-deploy.internal")
    await _save_scenario(client, h, "sc-ctx-bearer", [_call_step("svc")])

    def fake_auth(session, why):
        session.apply_token("tok-ctx", 3600)
    monkeypatch.setattr(run, "_AUTHENTICATE", fake_auth)
    monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(
        200, json={"d": [{"nm": "y"}]}))
    r = await client.get("/api/query-views/v1/rows",
                         params={"scenarioId": "sc-ctx-bearer", "stepIndex": 0},
                         headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["rows"] == [{"nm": "y"}]


async def test_context_scenario_not_found_404(client, monkeypatch):
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows",
                         params={"scenarioId": "sc-nope", "stepIndex": 0},
                         headers=h)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "scenario_not_found"


async def test_context_unreadable_scenario_404(client, monkeypatch):
    """他人私有场景 → 404 同码(不泄露存在性,draft 读闸同口径)。"""
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client)
    await _save_scenario(client, h, "sc-ctx-other", [_call_step("svc")])
    other = await register_and_login(client, "ctxother", "other-pass-1")
    r = await client.get("/api/query-views/v1/rows",
                         params={"scenarioId": "sc-ctx-other", "stepIndex": 0},
                         headers=other)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "scenario_not_found"


async def test_context_bad_step_index_422(client, monkeypatch):
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client)
    await _save_scenario(client, h, "sc-ctx-idx", [_call_step("svc")])
    r = await client.get("/api/query-views/v1/rows",
                         params={"scenarioId": "sc-ctx-idx", "stepIndex": 9},
                         headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "query_context_required"


async def test_context_step_without_service_422(client, monkeypatch):
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client)
    await _save_scenario(client, h, "sc-ctx-nosvc", [_call_step("")])
    r = await client.get("/api/query-views/v1/rows",
                         params={"scenarioId": "sc-ctx-nosvc", "stepIndex": 0},
                         headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "step_service_required"


async def test_context_deployment_missing_422(client, monkeypatch):
    """服务未登记/环境链全空 → deployment_url_missing(不再被
    service_url_required 掩盖 —— 用户能看到具体缺的是部署事实)。"""
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client)
    await _save_scenario(client, h, "sc-ctx-nodep", [_call_step("svc")])
    r = await client.get("/api/query-views/v1/rows",
                         params={"scenarioId": "sc-ctx-nodep", "stepIndex": 0},
                         headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "deployment_url_missing"


async def test_context_service_mismatch_422(client, monkeypatch):
    """视图声明服务 ≠ 步骤服务 → service_mismatch(上下文通道把步骤
    服务自动下推,跨服务错配在打 SUT 前被拒)。"""
    from app.core import db as db_module
    from .conftest import seed_identity_fixture

    _install_plate(monkeypatch, _IDX)          # 视图 v1 属服务 svc
    h = await register_and_login(client)
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    async with db_module.SessionLocal() as db:
        await seed_identity_fixture(
            db, alias="other", username="ou", password="op",
            service="other", owner_id=uid,
            env_name="查询环境", login_url=None,
            base_url="https://other-deploy.internal")
    await _save_scenario(client, h, "sc-ctx-mix", [_call_step("other")])
    r = await client.get("/api/query-views/v1/rows",
                         params={"scenarioId": "sc-ctx-mix", "stepIndex": 0},
                         headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "service_mismatch"
