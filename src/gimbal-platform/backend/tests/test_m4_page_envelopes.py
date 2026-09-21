"""M4 Page 信封 + 服务端过滤契约(PG迁移方案 §4.2/§6.3)。

列表端点的统一钉子:信封四件套 {items,total,page,pageSize}、
q 下推(命中子串/前缀)、精确过滤、分页切片。旧「全量裸数组」
形状已退役 —— 断言按信封取 items。
"""
from __future__ import annotations

from tests.helpers import register_and_login


async def _mk_auth(client, headers, alias: str, token_type: str = "Bearer"):
    r = await client.post("/api/auths", headers=headers, json={
        "alias": alias, "url": f"https://svc-{alias}.example.com",
        "username": f"u_{alias}", "password": "pw123456",
        "token_type": token_type, "expires_in": 3600,
    })
    assert r.status_code == 201, r.text


async def test_auths_envelope_q_type_and_counts(client):
    h = await register_and_login(client, "m4auth", "pw123456")
    await _mk_auth(client, h, "qa1", "Bearer")
    await _mk_auth(client, h, "qa2", "Bearer")
    await _mk_auth(client, h, "basic1", "Basic")

    r = await client.get("/api/auths", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"items", "total", "page", "pageSize", "tokenTypeCounts"} <= set(body)
    assert body["total"] == 3
    # 全量类型计数(非当前页)— metaText 的服务端供给
    assert body["tokenTypeCounts"] == {"Bearer": 2, "Basic": 1}

    # q 子串命中 alias/url
    r = await client.get("/api/auths", headers=h, params={"q": "qa"})
    assert r.json()["total"] == 2
    r = await client.get("/api/auths", headers=h, params={"q": "svc-basic1"})
    assert r.json()["total"] == 1  # url 子串

    # token_type 精确 + 分页
    r = await client.get("/api/auths", headers=h,
                         params={"token_type": "Bearer", "page_size": 1})
    b = r.json()
    assert b["total"] == 2 and len(b["items"]) == 1 and b["pageSize"] == 1
    r2 = await client.get("/api/auths", headers=h,
                          params={"token_type": "Bearer", "page_size": 1, "page": 2})
    assert len(r2.json()["items"]) == 1


async def test_constants_envelope_q_and_kind(client):
    h = await register_and_login(client, "m4const", "pw123456")
    for name, kind in [("bank_id", "literal"), ("bl_no", "literal"),
                       ("gen_seq", "generator")]:
        payload = {"name": name, "description": f"desc-{name}", "entry_kind": kind,
                   "value": "v" if kind == "literal" else None}
        if kind == "generator":
            payload["spec"] = {"kind": "random_decorated", "length": 6, "head": "G"}
        r = await client.post("/api/constants", headers=h, json=payload)
        assert r.status_code == 201, r.text

    r = await client.get("/api/constants", headers=h)
    body = r.json()
    assert {"items", "total", "page", "pageSize"} <= set(body)
    assert body["total"] == 3

    assert (await client.get("/api/constants", headers=h,
                             params={"q": "bank"})).json()["total"] == 1
    assert (await client.get("/api/constants", headers=h,
                             params={"q": "desc-bl"})).json()["total"] == 1  # description 子串
    assert (await client.get("/api/constants", headers=h,
                             params={"kind": "generator"})).json()["total"] == 1
    # 分页
    r = await client.get("/api/constants", headers=h, params={"page_size": 2})
    b = r.json()
    assert len(b["items"]) == 2 and b["total"] == 3
    r2 = await client.get("/api/constants", headers=h,
                          params={"page_size": 2, "page": 2})
    assert len(r2.json()["items"]) == 1


async def test_executions_q_scenario_name_and_id_prefix(client):
    h = await register_and_login(client, "m4exec", "pw123456")
    from app.core import db as db_module
    from app.models import Execution

    # 直插两条(读侧受测面;executions 无场景 FK,scenario_name 快照即可)
    async with db_module.SessionLocal() as s:
        s.add(Execution(scenario_id="sc-m4-a", scenario_name="订单查询",
                        owner_id=1, status="passed", total_runs=1, passed=1,
                        failed=0, config_json={}))
        s.add(Execution(scenario_id="sc-m4-b", scenario_name="委托创建",
                        owner_id=1, status="failed", total_runs=1, passed=0,
                        failed=1, config_json={}))
        await s.commit()

    r = await client.get("/api/executions", headers=h, params={"page_size": 10})
    body = r.json()
    assert body["total"] == 2
    first_id = body["items"][0]["id"]

    # q = scenario_name 子串
    r = await client.get("/api/executions", headers=h, params={"q": "订单"})
    assert r.json()["total"] == 1
    # q = id 前缀
    r = await client.get("/api/executions", headers=h, params={"q": str(first_id)})
    assert r.json()["total"] == 1
    # q 不中
    assert (await client.get("/api/executions", headers=h,
                             params={"q": "不存在"})).json()["total"] == 0


async def test_users_envelope_q_and_role(client):
    admin = await register_and_login(client, "m4admin", "pw123456")
    # 首注册即 admin;再开两个成员
    for name in ("m4u1", "m4u2"):
        r = await client.post("/api/users", headers=admin, json={
            "username": name, "password": "Test2026!"})
        assert r.status_code == 201, r.text

    r = await client.get("/api/users", headers=admin)
    body = r.json()
    assert {"items", "total", "page", "pageSize"} <= set(body)
    assert body["total"] == 3

    assert (await client.get("/api/users", headers=admin,
                             params={"q": "m4u"})).json()["total"] == 2
    assert (await client.get("/api/users", headers=admin,
                             params={"role": "member"})).json()["total"] == 2
    r = await client.get("/api/users", headers=admin, params={"page_size": 2})
    assert len(r.json()["items"]) == 2 and r.json()["total"] == 3


async def test_batches_envelope_status_and_page(client, plate):
    """批次信封:total 正确、status 过滤、detail 只构建当前页。"""
    from tests.conftest import EndpointPlateMock  # noqa: F401 — plate fixture 即该类

    admin = await register_and_login(client, "m4batch", "pw123456")
    EP = "fin.order.add"
    plate.items = [{"id": EP, "version": "1.1.0", "updated_at": None}]
    plate.fulls = {EP: {
        "id": EP, "version": "1.1.0",
        "request": {"declarations": [{"name": "amount", "state": "form"}]},
    }}
    from .test_adaptation_batches import _seed_scenario, _seed_stamp

    await _seed_scenario("sc-m4-batch")
    await _seed_stamp()
    from app.core import db as db_module
    from app.services import adaptation_service

    async with db_module.SessionLocal() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        assert detail["batchId"]

    r = await client.get("/api/adaptations/batches", headers=admin)
    body = r.json()
    assert {"items", "total", "page", "pageSize"} <= set(body)
    assert body["total"] >= 1
    r = await client.get("/api/adaptations/batches", headers=admin,
                         params={"status": "open"})
    assert r.json()["total"] >= 1
    r = await client.get("/api/adaptations/batches", headers=admin,
                         params={"status": "rolled_back"})
    assert r.json()["total"] == 0


async def test_service_aliases_envelope_q(client, plate):
    admin = await register_and_login(client, "m4alias", "pw123456")
    plate.services = [{"name": "fin-service"}]
    for alias in ("fin-service-uat", "fin-service-prod"):
        r = await client.post("/api/service-aliases", headers=admin,
                              json={"aliasName": alias})
        assert r.status_code == 201, r.text

    r = await client.get("/api/service-aliases", headers=admin)
    body = r.json()
    assert {"items", "total", "page", "pageSize"} <= set(body)
    assert body["total"] == 2

    assert (await client.get("/api/service-aliases", headers=admin,
                             params={"q": "uat"})).json()["total"] == 1
    r = await client.get("/api/service-aliases", headers=admin,
                         params={"page_size": 1})
    assert len(r.json()["items"]) == 1 and r.json()["total"] == 2
