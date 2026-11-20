"""执行配置 API 测试(执行配置分层①,设计方案 §4/§10)。

个人数据口径:全员可建、owner 隔离(跨 owner 一律 404);v1 只落
user scope 行。零凭证值零地址值 —— 载荷只存引用键(bindings/
carryOverrides),结构校验在 schema 层。
"""
from __future__ import annotations

from .helpers import register_and_login


async def _seed_binding_pair(
    declared: str, target: str, service: str = "fin-service",
    owner: str = "", u1: str = "bind-u1", u2: str = "bind-u2",
) -> None:
    """TOK-07 写面闸布景:声明条目与换用目标各种一条(同基础服务,
    四件套范式;同 (system,env) 第二个账户让出默认位)。账户须挂属主
    (ck_account_owner_xor_project),owner = 测试用户名。"""
    from sqlalchemy import text

    from app.core import db as db_module

    from .conftest import seed_identity_fixture

    async with db_module.SessionLocal() as s:
        uid = (await s.execute(text(
            "SELECT id FROM users WHERE username = :u"), {"u": owner})
        ).scalar()
        await seed_identity_fixture(
            s, alias=declared, username=u1, password="pw123456",
            service=service, owner_id=uid, is_default=True)
        await seed_identity_fixture(
            s, alias=target, username=u2, password="pw123456",
            service=service, owner_id=uid, is_default=False)


async def test_exec_config_crud_roundtrip(client, fresh_db):
    await register_and_login(client, "cfgu1", "pw123456")
    u1 = await register_and_login(client, "cfgu1", "pw123456")
    # TOK-07 写面闸:bindings 键/值须是已登记条目(同基础服务)
    await _seed_binding_pair("fin-service.merchant-b", "merchant-b",
                             owner="cfgu1")

    systems = [{
        "service": "fin-service",
        "aliases": ["fin-service.merchant-b", "fin-service.sit"],
        "bindings": {"fin-service.merchant-b": "merchant-b"},
        "carryOverrides": {"merchant.grade": "B", "flag.null": None},
    }]
    # §8.2:environmentId 链位退役 —— 键被静默忽略,响应无该键
    r = await client.post("/api/exec-configs", headers=u1, json={
        "name": "商户B视角", "environmentId": None, "systems": systems,
        "isDefault": True})
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["name"] == "商户B视角" and row["isDefault"] is True
    assert "environmentId" not in row
    # §8.10:aliases(圈定调用身份,管理范围)随 systems 持久化回读
    assert row["systems"] == systems

    cid = row["id"]
    # 列表:默认在前;结构回读一致
    r = await client.get("/api/exec-configs", headers=u1)
    assert r.status_code == 200 and len(r.json()) == 1
    assert r.json()[0]["id"] == cid

    # PATCH:改名 + 换 systems
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u1, json={
        "name": "商户B视角@UAT",
        "systems": [{"service": "crm", "bindings": {}, "carryOverrides": {}}]})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "商户B视角@UAT"
    assert r.json()["systems"][0]["service"] == "crm"

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


async def test_exec_config_environment_key_retired(client, fresh_db):
    """§8.2:environmentId 不再收不再校验 —— 坏 id 也 201,响应无该键。"""
    await register_and_login(client, "cfgu2", "pw123456")
    u2 = await register_and_login(client, "cfgu2", "pw123456")

    r = await client.post("/api/exec-configs", headers=u2, json={
        "name": "c", "environmentId": 424242})
    assert r.status_code == 201, r.text
    assert "environmentId" not in r.json()
    cid = r.json()["id"]

    r = await client.patch(f"/api/exec-configs/{cid}", headers=u2,
                           json={"environmentId": 424242})
    assert r.status_code == 200 and "environmentId" not in r.json()


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
    await _seed_binding_pair("fin.a", "a", service="fin", owner="cfgown1")

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
    """复制 = 跨配置字段复用的通道(决策 7 代价补偿):payload
    全拷,副本恒非默认;重名 409。"""
    await register_and_login(client, "cfgcp", "pw123456")
    u = await register_and_login(client, "cfgcp", "pw123456")
    await _seed_binding_pair("fin.a", "a", service="fin", owner="cfgcp")

    src = (await client.post("/api/exec-configs", headers=u, json={
        "name": "基线", "isDefault": True,
        "systems": [{"service": "fin", "bindings": {"fin.a": "a"},
                     "carryOverrides": {"k": "v"}}]})).json()

    r = await client.post(f"/api/exec-configs/{src['id']}/copy", headers=u,
                          json={"name": "基线-变体"})
    assert r.status_code == 201, r.text
    dup = r.json()
    assert dup["id"] != src["id"]
    assert dup["name"] == "基线-变体" and dup["isDefault"] is False
    assert dup["systems"] == src["systems"]

    # 原默认不受副本影响
    r = await client.get("/api/exec-configs", headers=u)
    assert [x["id"] for x in r.json() if x["isDefault"]] == [src["id"]]

    # 重名 409
    r = await client.post(f"/api/exec-configs/{src['id']}/copy", headers=u,
                          json={"name": "基线-变体"})
    assert r.status_code == 409


async def test_exec_config_meta_description_tags(client, fresh_db):
    """v7:说明/标签 = 配置级元信息(payload 顶层)。roundtrip / PATCH 合并不
    丢元信息(回归钉)/ 显式清空 / 换行截断去重 / copy 携带 / 约束 422。"""
    await register_and_login(client, "cfgmeta", "pw123456")
    u = await register_and_login(client, "cfgmeta", "pw123456")

    row = (await client.post("/api/exec-configs", headers=u, json={
        "name": "元信息套",
        "description": "商户B端回归主配置",
        "tags": ["UAT", " 核心 ", "UAT", ""],
        "systems": [{"service": "fin", "bindings": {}}],
    })).json()
    # strip / 去空 / 去重
    assert row["description"] == "商户B端回归主配置"
    assert row["tags"] == ["UAT", "核心"]
    cid = row["id"]

    # 回归钉:只传 systems 的 PATCH 不得抹掉说明/标签(旧客户端/节点保存路径)
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u, json={
        "systems": [{"service": "crm", "bindings": {}}]})
    assert r.status_code == 200, r.text
    assert r.json()["description"] == "商户B端回归主配置"
    assert r.json()["tags"] == ["UAT", "核心"]
    assert r.json()["systems"][0]["service"] == "crm"

    # 显式清空
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u, json={
        "description": "", "tags": []})
    assert r.status_code == 200
    assert r.json()["description"] == "" and r.json()["tags"] == []

    # 超长标签截断(20 字),空标签丢弃
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u, json={
        "tags": ["x" * 30, ""]})
    assert r.status_code == 200
    assert r.json()["tags"] == ["x" * 20]

    # 说明超限 422
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u, json={
        "description": "d" * 2049})
    assert r.status_code == 422

    # copy 携带元信息(deepcopy)
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u, json={
        "description": "基线", "tags": ["PRE"]})
    assert r.status_code == 200
    dup = (await client.post(f"/api/exec-configs/{cid}/copy", headers=u,
                             json={"name": "元信息副本"})).json()
    assert dup["description"] == "基线" and dup["tags"] == ["PRE"]


async def test_exec_config_aliases_scope_semantics(client, fresh_db):
    """§8.10:aliases = 圈定本配置采用的调用身份条目(管理范围)——
    持久化回读 / 缺省 [](存量未圈定)/ 整体替换式 PATCH / 非法 422。"""
    await register_and_login(client, "cfgal", "pw123456")
    u = await register_and_login(client, "cfgal", "pw123456")
    await _seed_binding_pair("fin.a", "a", service="fin", owner="cfgal")

    # 缺省(存量形态):省键 → 回读补 []
    row = (await client.post("/api/exec-configs", headers=u, json={
        "name": "存量", "systems": [{"service": "fin", "bindings": {"fin.a": "a"}}]
        })).json()
    assert row["systems"][0]["aliases"] == []

    # roundtrip:圈定集合原样回读
    r = await client.patch(f"/api/exec-configs/{row['id']}", headers=u, json={
        "systems": [{"service": "fin", "aliases": ["fin.a", "fin.b"],
                     "bindings": {"fin.a": "a"}}]})
    assert r.status_code == 200, r.text
    assert r.json()["systems"][0]["aliases"] == ["fin.a", "fin.b"]

    # 整体替换:再次 PATCH 不带 aliases → 清空(替换式,非合并)
    r = await client.patch(f"/api/exec-configs/{row['id']}", headers=u, json={
        "systems": [{"service": "fin", "bindings": {}}]})
    assert r.status_code == 200
    assert r.json()["systems"][0]["aliases"] == []

    # 空串条目名 → 422(_SlotName min_length=1)
    r = await client.post("/api/exec-configs", headers=u, json={
        "name": "bad", "systems": [{"service": "fin", "aliases": [""]}]})
    assert r.status_code == 422

    # copy 携带 aliases(deepcopy)
    r = await client.patch(f"/api/exec-configs/{row['id']}", headers=u, json={
        "systems": [{"service": "fin", "aliases": ["fin.a"]}]})
    assert r.status_code == 200
    dup = (await client.post(f"/api/exec-configs/{row['id']}/copy", headers=u,
                             json={"name": "副本"})).json()
    assert dup["systems"][0]["aliases"] == ["fin.a"]


async def test_exec_config_entry_name_domain_128(client, fresh_db):
    """条目名域 = service_identities.alias_name String(128)(2026-11-19
    订正):65–128 字符条目名进 aliases 与 bindings 值不再 422 —— 旧
    _SlotName(64) 系退役 slot 列口径,与注册表创建域(max_length=128)
    不一致曾致长条目名「能进 bindings、进圈定即 422」。"""
    await register_and_login(client, "cfgdom", "pw123456")
    u = await register_and_login(client, "cfgdom", "pw123456")

    long_name = "fin." + "x" * 100          # 104 字符:> 64 且 ≤ 128
    declared = "decl." + "y" * 100          # 105 字符声明键
    await _seed_binding_pair(declared, long_name, service="fin",
                             owner="cfgdom", u1="dom-u1", u2="dom-u2")
    r = await client.post("/api/exec-configs", headers=u, json={
        "name": "长条目名", "systems": [{
            "service": "fin", "aliases": [long_name],
            "bindings": {declared: long_name}}]})
    assert r.status_code == 201, r.text
    s = r.json()["systems"][0]
    assert s["aliases"] == [long_name]
    assert s["bindings"][declared] == long_name

    # 超 128 仍 422(对齐注册表创建域)
    r = await client.post("/api/exec-configs", headers=u, json={
        "name": "超限", "systems": [{"service": "fin",
                                     "aliases": ["z" * 129]}]})
    assert r.status_code == 422


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

async def test_exec_config_bindings_write_gate(client, fresh_db):
    """TOK-07(2026-11-20 审计):换用槽位写面闸 —— 目标/声明不存在 422、
    跨基础服务 422(运行时 precheck 只拦不存在,跨基础服务由此补拦);
    PATCH 显式 systems 同口径,不带 systems(合并式)不触发。"""
    await register_and_login(client, "cfggate", "pw123456")
    u = await register_and_login(client, "cfggate", "pw123456")
    await _seed_binding_pair("fin.a", "a", service="fin", owner="cfggate")
    await _seed_binding_pair("crm.x", "crm.y", service="crm", owner="cfggate",
                             u1="crm-u1", u2="crm-u2")

    # 换用目标不存在
    r = await client.post("/api/exec-configs", headers=u, json={
        "name": "bad-target", "systems": [
            {"service": "fin", "bindings": {"fin.a": "ghost"}}]})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "slot_alias_unknown"

    # 跨基础服务换用:fin 声明 → crm 条目(凭证注入原地址的攻击面)
    r = await client.post("/api/exec-configs", headers=u, json={
        "name": "cross-base", "systems": [
            {"service": "fin", "bindings": {"fin.a": "crm.x"}}]})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "slot_alias_mismatch"

    # 声明条目自身不存在
    r = await client.post("/api/exec-configs", headers=u, json={
        "name": "bad-declared", "systems": [
            {"service": "fin", "bindings": {"ghost": "a"}}]})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "slot_alias_unknown"

    # 合法:同基础服务放行
    r = await client.post("/api/exec-configs", headers=u, json={
        "name": "ok", "systems": [
            {"service": "fin", "bindings": {"fin.a": "a"}}]})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]

    # PATCH 显式 systems:同口径拦截
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u, json={
        "systems": [{"service": "fin", "bindings": {"fin.a": "crm.y"}}]})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "slot_alias_mismatch"

    # PATCH 不带 systems(合并式):不触发校验,改名放行
    r = await client.patch(f"/api/exec-configs/{cid}", headers=u,
                           json={"name": "ok-2"})
    assert r.status_code == 200, r.text
