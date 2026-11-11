"""执行配置 API 测试(执行配置分层①,设计方案 §4/§10)。

个人数据口径:全员可建、owner 隔离(跨 owner 一律 404);v1 只落
user scope 行。零凭证值零地址值 —— 载荷只存引用键(bindings/
carryOverrides),结构校验在 schema 层。
"""
from __future__ import annotations

from .helpers import register_and_login


async def test_exec_config_crud_roundtrip(client, fresh_db):
    await register_and_login(client, "cfgu1", "pw123456")
    u1 = await register_and_login(client, "cfgu1", "pw123456")

    systems = [{
        "service": "fin-service",
        "bindings": {"fin-service.merchant-b": "merchant-b"},
        "carryOverrides": {"merchant.grade": "B", "flag.null": None},
    }]
    r = await client.post("/api/exec-configs", headers=u1, json={
        "name": "商户B视角", "environmentId": None, "systems": systems,
        "isDefault": True})
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["name"] == "商户B视角" and row["isDefault"] is True
    assert row["environmentId"] is None
    assert row["systems"] == systems

    cid = row["id"]
    # 列表:默认在前;结构回读一致
    r = await client.get("/api/exec-configs", headers=u1)
    assert r.status_code == 200 and len(r.json()) == 1
    assert r.json()[0]["id"] == cid

    # PATCH:改名 + 换 systems;environmentId 未提供 → 不动
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u1, json={
        "name": "商户B视角@UAT",
        "systems": [{"service": "crm", "bindings": {}, "carryOverrides": {}}]})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "商户B视角@UAT"
    assert r.json()["systems"][0]["service"] == "crm"
    assert r.json()["environmentId"] is None

    # 重名 409(字典 detail,与常量池同款)
    r = await client.post("/api/exec-configs", headers=u1,
                          json={"name": "商户B视角@UAT"})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "exec_config_name_exists"

    # 未知 id 404
    r = await client.get("/api/exec-configs/99999", headers=u1)
    assert r.status_code == 404

    # 未登录 401
    r = await client.get("/api/exec-configs")
    assert r.status_code == 401


async def test_exec_config_environment_validation(client, fresh_db):
    """environmentId 引用校验:不存在 → 422 environment_not_found
    (projects 同款);建环境后可设,可显式置空(不设置)。"""
    await register_and_login(client, "cfgu2", "pw123456")
    u2 = await register_and_login(client, "cfgu2", "pw123456")

    r = await client.post("/api/exec-configs", headers=u2, json={
        "name": "c", "environmentId": 424242})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "environment_not_found"

    r = await client.post("/api/environments", headers=u2,
                          json={"name": "UAT", "lines": {}})
    env_id = r.json()["id"]

    r = await client.post("/api/exec-configs", headers=u2, json={
        "name": "c", "environmentId": env_id})
    assert r.status_code == 201 and r.json()["environmentId"] == env_id
    cid = r.json()["id"]

    # PATCH 显式置空 ≠ 未提供(model_fields_set 区分)
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u2,
                           json={"environmentId": None})
    assert r.status_code == 200 and r.json()["environmentId"] is None

    # PATCH 未提供 environmentId → 原值不动(已为 null,先设回再验)
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u2,
                           json={"environmentId": env_id})
    assert r.json()["environmentId"] == env_id
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u2,
                           json={"name": "c2"})
    assert r.json()["environmentId"] == env_id

    # PATCH 指向不存在的环境 → 422
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u2,
                           json={"environmentId": 424242})
    assert r.status_code == 422


async def test_exec_config_default_atomic_switch(client, fresh_db):
    """默认配置每 scope 至多一行:建即默认/切换/并发兜底同款 409;
    两用户各自默认互不干扰。删除默认行 → 无默认(链回落,不级联转移)。"""
    await register_and_login(client, "cfgu3", "pw123456")
    u3 = await register_and_login(client, "cfgu3", "pw123456")

    a = (await client.post("/api/exec-configs", headers=u3,
                           json={"name": "a", "isDefault": True})).json()
    b = (await client.post("/api/exec-configs", headers=u3,
                           json={"name": "b"})).json()

    # 建即默认:第二行非默认,首行仍默认
    assert a["isDefault"] is True and b["isDefault"] is False

    # 切默认
    r = await client.post(f"/api/exec-configs/{b['id']}/default", headers=u3)
    assert r.status_code == 200 and r.json()["isDefault"] is True
    r = await client.get("/api/exec-configs", headers=u3)
    defaults = [x for x in r.json() if x["isDefault"]]
    assert len(defaults) == 1 and defaults[0]["id"] == b["id"]
    # 默认在前
    assert r.json()[0]["id"] == b["id"]

    # 建 isDefault=True 的第三行 → 清旧
    c = (await client.post("/api/exec-configs", headers=u3,
                           json={"name": "c", "isDefault": True})).json()
    r = await client.get("/api/exec-configs", headers=u3)
    defaults = [x for x in r.json() if x["isDefault"]]
    assert len(defaults) == 1 and defaults[0]["id"] == c["id"]

    # 另一用户独立默认(部分唯一索引按 (scope, scope_id) 分组)
    await register_and_login(client, "cfgu4", "pw123456")
    u4 = await register_and_login(client, "cfgu4", "pw123456")
    r = await client.post("/api/exec-configs", headers=u4,
                          json={"name": "mine", "isDefault": True})
    assert r.status_code == 201
    r = await client.get("/api/exec-configs", headers=u4)
    assert len([x for x in r.json() if x["isDefault"]]) == 1

    # 删默认行 → 无默认
    r = await client.delete(f"/api/exec-configs/{c['id']}", headers=u3)
    assert r.status_code == 204
    r = await client.get("/api/exec-configs", headers=u3)
    assert all(not x["isDefault"] for x in r.json())


async def test_exec_config_owner_isolation(client, fresh_db):
    """个人数据:跨 owner 一律 404(常量池同款),列表只见本人。"""
    await register_and_login(client, "cfgown1", "pw123456")
    u1 = await register_and_login(client, "cfgown1", "pw123456")
    await register_and_login(client, "cfgown2", "pw123456")
    u2 = await register_and_login(client, "cfgown2", "pw123456")

    row = (await client.post("/api/exec-configs", headers=u1, json={
        "name": "秘密配置",
        "systems": [{"service": "fin", "bindings": {"fin.a": "a"},
                     "carryOverrides": {"k": "v"}}]})).json()

    for path, method, kwargs in [
        (f"/api/exec-configs/{row['id']}", "GET", {}),
        (f"/api/exec-configs/{row['id']}", "PATCH", {"json": {"name": "x"}}),
        (f"/api/exec-configs/{row['id']}/default", "POST", {}),
        (f"/api/exec-configs/{row['id']}/copy", "POST",
         {"json": {"name": "copy"}}),
        (f"/api/exec-configs/{row['id']}", "DELETE", {}),
    ]:
        r = await getattr(client, method.lower())(path, headers=u2, **kwargs)
        assert r.status_code == 404, f"{method} {path}: {r.status_code}"

    r = await client.get("/api/exec-configs", headers=u2)
    assert r.status_code == 200 and r.json() == []


async def test_exec_config_copy(client, fresh_db):
    """复制 = 跨配置字段复用的通道(决策 7 代价补偿):env+payload
    全拷,副本恒非默认;重名 409。"""
    await register_and_login(client, "cfgcp", "pw123456")
    u = await register_and_login(client, "cfgcp", "pw123456")

    env_id = (await client.post("/api/environments", headers=u,
                                json={"name": "SIT"})).json()["id"]
    src = (await client.post("/api/exec-configs", headers=u, json={
        "name": "基线", "environmentId": env_id, "isDefault": True,
        "systems": [{"service": "fin", "bindings": {"fin.a": "a"},
                     "carryOverrides": {"k": "v"}}]})).json()

    r = await client.post(f"/api/exec-configs/{src['id']}/copy", headers=u,
                          json={"name": "基线-变体"})
    assert r.status_code == 201, r.text
    dup = r.json()
    assert dup["id"] != src["id"]
    assert dup["name"] == "基线-变体" and dup["isDefault"] is False
    assert dup["environmentId"] == env_id and dup["systems"] == src["systems"]

    # 原默认不受副本影响
    r = await client.get("/api/exec-configs", headers=u)
    assert [x["id"] for x in r.json() if x["isDefault"]] == [src["id"]]

    # 重名 409
    r = await client.post(f"/api/exec-configs/{src['id']}/copy", headers=u,
                          json={"name": "基线-变体"})
    assert r.status_code == 409


async def test_exec_config_payload_shape_validation(client, fresh_db):
    """零凭证值零地址值:载荷结构在 schema 层校验 —— service 非空、
    bindings/值长度上限;carryOverrides 值允许 null(显式注入)。"""
    await register_and_login(client, "cfgpv", "pw123456")
    u = await register_and_login(client, "cfgpv", "pw123456")

    # service 空 → 422
    r = await client.post("/api/exec-configs", headers=u, json={
        "name": "bad", "systems": [{"service": ""}]})
    assert r.status_code == 422
    # bindings 键超长(>256?pydantic dict 键长度默认不限 —— 用值超长验证)
    r = await client.post("/api/exec-configs", headers=u, json={
        "name": "bad2",
        "systems": [{"service": "fin", "bindings": {"fin.a": "x" * 200}}]})
    assert r.status_code == 422
    # 合法最小载荷:省缺 systems = 空配置(纯环境偏好形态)
    r = await client.post("/api/exec-configs", headers=u, json={"name": "空"})
    assert r.status_code == 201 and r.json()["systems"] == []


async def test_exec_config_drift(client, fresh_db, plate):
    """③ 关联枢纽:覆盖字段 vs plate 面 diff —— orphaned(覆盖了但面
    没有)/ uncovered(面有而未覆盖,按层序合成的部分)。"""
    from tests.test_authz_s76_drift_layers import _EP, _FACE

    plate.items = [_EP]
    plate.fulls = {"fin.ep1": _FACE}
    await register_and_login(client, "cfgdr", "pw123456")
    h = await register_and_login(client, "cfgdr", "pw123456")

    cid = (await client.post("/api/exec-configs", headers=h, json={
        "name": "漂移套",
        "systems": [{"service": "fin-service", "bindings": {},
                     "carryOverrides": {"$.remark": "r", "$.old": "x"}}]
        })).json()["id"]

    r = await client.get(f"/api/exec-configs/{cid}/drift", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plateReachable"] is True
    assert body["services"] == [{
        "service": "fin-service",
        "orphaned": ["$.old"],        # 面只有 $.remark
        "uncovered": [],              # $.remark 已被覆盖
    }]

    # 跨人 404
    await register_and_login(client, "cfgdr2", "pw123456")
    h2 = await register_and_login(client, "cfgdr2", "pw123456")
    r = await client.get(f"/api/exec-configs/{cid}/drift", headers=h2)
    assert r.status_code == 404
