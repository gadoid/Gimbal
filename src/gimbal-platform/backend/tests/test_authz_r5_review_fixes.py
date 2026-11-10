"""评审第五轮必修项回归(2026-11-10,r5 review)。

* 2.1 platformize / transfer:令牌路径一律 404(个人 ∨ 项目令牌 ——
  人工治理动作不开放给机器身份;会话路径行为不变);
* 2.2 项目凭证:改 ``url`` 须同时重录 ``password``(422
  ``url_change_requires_password``);管理门与读面去 Admin+ 旁路
  (非成员 404,与选用门同口径:凭证是项目的,不是平台的);
* r3二.1 项目成员可列同事的数据集(预览剥敏感列);非属主保存按
  行位并回存量敏感列(整表保存不再丢列、存量值权威);
* r3二.2 carry ``scope=project`` 读面须成员(非成员 404;Admin+ 写
  旁路照旧);
* r3二.3 导出守区规则(原 5):项目/公共区场景导出内置凭证当空、
  直连地址不生效(属主同样);私有区属主导出照旧带本人明文(Q3)。
"""
from __future__ import annotations

from .helpers import make_draft, register_and_login, role_headers
from .inbound_fixtures import mk_token
from .test_authz_s17_platform import _mk_public_tpl
from .test_authz_s8_project_credentials import _mk_project, _uid
from .test_scenario_composer_plate_integration import (  # noqa: F401
    PlateMock,
    plate_mock,
)

_USERS = {"qa1": {"username": "u", "password": "p", "token": "t"}}


def _bearer(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ── 2.1 platformize / transfer:令牌一律 404 ──────────────────────

class TestPlatformizeTransferTokenDenied:
    async def test_personal_and_project_tokens_404(self, client):
        # 模板属主(普通用户)+ Admin+(平台角色,兼任下述项目管理员)
        h_own = await role_headers(client, "r5_pz_own", role="user")
        h_adm = await role_headers(client, "r5_pz_adm", role="admin")
        tid = await _mk_public_tpl(client, h_own, "sc-r5-pz", "r5-tpl")
        # 个人令牌(Admin 名下)+ 项目令牌(Admin 为负责人)
        _, personal = await mk_token(user_id=await _uid("r5_pz_adm"))
        pid = await _mk_project("r5-pz", members={"r5_pz_adm": "admin"})
        r = await client.post(f"/api/projects/{pid}/tokens", headers=h_adm,
                              json={"name": "r5-proj"})
        assert r.status_code == 201, r.text
        project_tok = r.json()["token"]
        # 令牌路径:两个端点都 404(修前:随负责人全用户权限 200)
        for h in (_bearer(personal), _bearer(project_tok)):
            assert (await client.post(
                f"/api/integration/tasks/{tid}/platformize",
                headers=h)).status_code == 404
            assert (await client.post(
                f"/api/integration/tasks/{tid}/transfer", headers=h,
                json={"toUserId": await _uid("r5_pz_adm")}
            )).status_code == 404
        # 会话路径行为不变:Admin+ platformize 200;转移给第三者 200
        # (r5_pz_3rd 在此注册为在职普通用户,作受让人)
        assert (await client.post(
            f"/api/integration/tasks/{tid}/platformize",
            headers=h_adm)).status_code == 200
        await role_headers(client, "r5_pz_3rd", role="user")
        r = await client.post(f"/api/integration/tasks/{tid}/transfer",
                              headers=h_adm,
                              json={"toUserId": await _uid("r5_pz_3rd")})
        assert r.status_code == 200, r.text


# ── 2.2 项目凭证:url 改动须重录密码 + Admin+ 不旁路 ──────────────

class TestProjectCredentialUrlPasswordAndGate:
    async def test_url_change_requires_password(self, client):
        h_a = await register_and_login(client, "r5_ca", "pw123456")
        pid = await _mk_project("r5-cred", members={"r5_ca": "admin"})
        base = f"/api/projects/{pid}/credentials"
        r = await client.post(base, headers=h_a, json={
            "alias": "qa1", "url": "http://real-auth", "username": "u1",
            "password": "p1x2y3z", "system": "fin"})
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        # 单改 url → 422(拨测/执行会把存量密码发往新地址)
        r = await client.patch(f"{base}/{cid}", headers=h_a,
                               json={"url": "https://attacker.example/c"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "url_change_requires_password"
        # 同值 url 不算改动(无密码可改其他字段)
        r = await client.patch(f"{base}/{cid}", headers=h_a,
                               json={"url": "http://real-auth",
                                     "username": "u2"})
        assert r.status_code == 200, r.text
        assert r.json()["url"] == "http://real-auth"
        # url + password 一起 → 200
        r = await client.patch(f"{base}/{cid}", headers=h_a,
                               json={"url": "http://new-auth",
                                     "password": "p2x3y4z"})
        assert r.status_code == 200 and r.json()["url"] == "http://new-auth"

    async def test_admin_plus_no_bypass(self, client):
        h_a = await register_and_login(client, "r5_ga", "pw123456")
        h_m = await register_and_login(client, "r5_gm", "pw123456")
        h_ops = await role_headers(client, "r5_ops", role="admin")
        pid = await _mk_project("r5-gate", members={"r5_ga": "admin",
                                                    "r5_gm": "member"})
        base = f"/api/projects/{pid}/credentials"
        r = await client.post(base, headers=h_a, json={
            "alias": "qa1", "url": "http://a", "username": "u1",
            "password": "p1x2y3z", "system": "fin"})
        cid = r.json()["id"]
        # Admin+ 非成员:读面 404、写面 404、拨测 404(修前:可维护可
        # 导出 —— 与选用门「Admin+ 不旁路」自相矛盾)
        assert (await client.get(base, headers=h_ops)).status_code == 404
        assert (await client.post(base, headers=h_ops, json={
            "alias": "x", "url": "http://b", "username": "u",
            "password": "p12345"})).status_code == 404
        assert (await client.patch(f"{base}/{cid}", headers=h_ops,
                                   json={"url": "http://evil"}
                                   )).status_code == 404
        assert (await client.post(f"{base}/{cid}/test",
                                  headers=h_ops)).status_code == 404
        # 成员读面不受影响(无用户名视图);项目管理员照旧全权
        r = await client.get(base, headers=h_m)
        assert r.status_code == 200
        assert r.json()["items"][0]["username"] == "" \
            and r.json()["canManage"] is False
        assert (await client.get(base, headers=h_a)
                ).json()["canManage"] is True


# ── r3二.1 数据集:成员可列同事 + 保存不丢敏感列 ──────────────────

class TestDataSetMemberListingAndSensitiveKeep:
    async def test_member_lists_and_save_keeps_sensitive(self, client):
        h_a = await register_and_login(client, "r5_da", "pw123456")
        h_b = await register_and_login(client, "r5_db", "pw123456")
        h_x = await register_and_login(client, "r5_dx", "pw123456")
        pid = await _mk_project("r5-ds", members={"r5_da": "admin",
                                                  "r5_db": "member"})
        draft = make_draft("sc-r5-ds", vars_map={
            "user": "u0", "password": "p0", "remark": "r0"})
        r = await client.post(f"/api/scenarios?projectId={pid}",
                              headers=h_a, json=draft)
        assert r.status_code in (200, 201), r.text
        r = await client.post("/api/scenarios/sc-r5-ds/data-sets",
                              headers=h_a, json={
                                  "name": "参数表", "rows": [
                                      {"user": "u1", "password": "secret1",
                                       "remark": "a"},
                                      {"user": "u2", "password": "secret2",
                                       "remark": "b"}]})
        assert r.status_code == 201, r.text
        ds = r.json()
        # 成员可列同事的数据集(修前:owned 过滤 → 0 条);预览剥敏感列
        r = await client.get("/api/data-sets?scenarioId=sc-r5-ds",
                             headers=h_b)
        assert r.status_code == 200 and len(r.json()) == 1
        preview = r.json()[0]["preview"]
        assert preview and "password" not in preview[0]
        # 非成员仍不可见(列表空)
        assert (await client.get("/api/data-sets?scenarioId=sc-r5-ds",
                                 headers=h_x)).json() == []
        # 成员读 → 脱敏 + __rowKey(r6 二.1:写面按它并回正确的行)
        r = await client.get(f"/api/data-sets/{ds['datasetId']}",
                             headers=h_b)
        assert r.status_code == 200
        assert all("password" not in row for row in r.json()["rows"])
        assert all("__rowKey" in row for row in r.json()["rows"])
        rows = [{"user": row["user"], "remark": row["remark"] + "!",
                 "__rowKey": row["__rowKey"],
                 "password": "GUESSED"}     # 读者看不到真值 → 存量权威
                for row in r.json()["rows"]]
        r = await client.put(f"/api/data-sets/{ds['datasetId']}", headers=h_b,
                             json={"name": "参数表", "rows": rows})
        assert r.status_code == 200, r.text
        r = await client.get(f"/api/data-sets/{ds['datasetId']}",
                             headers=h_a)
        got = r.json()["rows"]
        # 敏感列按行键并回存量值(成员提交的猜测值不生效),普通列更新;
        # __rowKey 不落库
        assert got[0]["password"] == "secret1" \
            and got[1]["password"] == "secret2", got
        assert got[0]["remark"] == "a!" and got[1]["remark"] == "b!"
        assert all("__rowKey" not in row for row in got)
        # 属主保存原样(不并回逻辑,明文自见)
        r = await client.put(f"/api/data-sets/{ds['datasetId']}", headers=h_a,
                             json={"name": "参数表", "rows": [
                                 {"user": "u9", "password": "new",
                                  "remark": "z"}]})
        assert r.status_code == 200
        assert r.json()["rows"][0]["password"] == "new"

    async def test_row_key_merge_survives_delete_insert_reorder(
            self, client):
        """r6 二.1:按行号并回会在删/插/重排后串号(bob 拿到 alice 的
        密码)—— 行键并回后:删行值随行走、插行不并回、重排不串号。"""
        h_a = await register_and_login(client, "r6_da", "pw123456")
        h_b = await register_and_login(client, "r6_db", "pw123456")
        pid = await _mk_project("r6-ds", members={"r6_da": "admin",
                                                  "r6_db": "member"})
        draft = make_draft("sc-r6-ds", vars_map={
            "user": "u0", "password": "p0", "remark": "r0"})
        r = await client.post(f"/api/scenarios?projectId={pid}",
                              headers=h_a, json=draft)
        assert r.status_code in (200, 201), r.text
        r = await client.post("/api/scenarios/sc-r6-ds/data-sets",
                              headers=h_a, json={
                                  "name": "参数表", "rows": [
                                      {"user": "alice", "password": "PW-ALICE",
                                       "remark": "a"},
                                      {"user": "bob", "password": "PW-BOB",
                                       "remark": "b"}]})
        assert r.status_code == 201, r.text
        ds = r.json()["datasetId"]
        view = (await client.get(f"/api/data-sets/{ds}",
                                 headers=h_b)).json()["rows"]
        alice, bob = view
        # ① 重排(bob 在前)+ 删 alice 行 → bob 不得拿到 PW-ALICE
        rows = [{"user": bob["user"], "remark": "b2",
                 "__rowKey": bob["__rowKey"]}]
        r = await client.put(f"/api/data-sets/{ds}", headers=h_b,
                             json={"name": "参数表", "rows": rows})
        assert r.status_code == 200, r.text
        got = (await client.get(f"/api/data-sets/{ds}",
                                headers=h_a)).json()["rows"]
        assert len(got) == 1 and got[0]["user"] == "bob", got
        assert got[0]["password"] == "PW-BOB", got
        # ② 重新做两行,插行(新行无键不并回)+ 顶插重排不串号
        view = (await client.get(f"/api/data-sets/{ds}",
                                 headers=h_a)).json()["rows"]
        assert (await client.put(f"/api/data-sets/{ds}", headers=h_a,
                                 json={"name": "参数表", "rows": [
                                     {"user": "alice", "password": "PW-ALICE",
                                      "remark": "a"},
                                     {"user": "bob", "password": "PW-BOB",
                                      "remark": "b"}]})
                ).status_code == 200
        view = (await client.get(f"/api/data-sets/{ds}",
                                 headers=h_b)).json()["rows"]
        alice, bob = view
        rows = [{"user": "carol", "remark": "c"},               # 新行无键
                {"user": bob["user"], "remark": "b3",
                 "__rowKey": bob["__rowKey"]},
                {"user": alice["user"], "remark": "a3",
                 "__rowKey": alice["__rowKey"]}]
        r = await client.put(f"/api/data-sets/{ds}", headers=h_b,
                             json={"name": "参数表", "rows": rows})
        assert r.status_code == 200, r.text
        got = (await client.get(f"/api/data-sets/{ds}",
                                headers=h_a)).json()["rows"]
        assert got[0]["user"] == "carol" and "password" not in got[0], got
        assert got[1]["password"] == "PW-BOB", got      # 键随行,不串号
        assert got[2]["password"] == "PW-ALICE", got
        # ③ 未知键 = 新行(不并回);键值被成员改掉同此
        rows = [{"user": "mallory", "remark": "m",
                 "__rowKey": "deadbeefdeadbeef"}]
        r = await client.put(f"/api/data-sets/{ds}", headers=h_b,
                             json={"name": "参数表", "rows": rows})
        assert r.status_code == 200
        got = (await client.get(f"/api/data-sets/{ds}",
                                headers=h_a)).json()["rows"]
        assert got[0]["user"] == "mallory" and "password" not in got[0]


# ── r3二.2 carry scope=project 读面须成员 ────────────────────────

class TestCarryProjectReadGate:
    async def test_non_member_404_member_reads(self, client):
        h_a = await register_and_login(client, "r5_ta", "pw123456")
        h_m = await register_and_login(client, "r5_tm", "pw123456")
        h_x = await register_and_login(client, "r5_tx", "pw123456")
        pid = await _mk_project("r5-carry", members={"r5_ta": "admin",
                                                     "r5_tm": "member"})
        # 项目管理员写项目层绑定
        r = await client.put("/api/carry/bindings/r5-svc", headers=h_a,
                             params={"scope": "project", "projectId": pid},
                             json={"bindings": {"$.k": "proj"}})
        assert r.status_code == 200, r.text
        # 非成员:单服务读 / defaults 读都 404(修前:200 带出项目层值)
        assert (await client.get(
            "/api/carry/bindings/r5-svc", headers=h_x,
            params={"scope": "project", "projectId": pid})).status_code == 404
        assert (await client.get(
            "/api/carry/defaults", headers=h_x,
            params={"scope": "project", "projectId": pid})).status_code == 404
        # 成员照读
        r = await client.get("/api/carry/bindings/r5-svc", headers=h_m,
                             params={"scope": "project", "projectId": pid})
        assert r.status_code == 200 and r.json()["bindings"] == {"$.k": "proj"}


# ── r3二.3 导出守区规则 ──────────────────────────────────────────

class TestExportZoneRules:
    async def test_project_export_strips_builtin(self, client, plate_mock):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "r5_ea", "pw123456")
        pid = await _mk_project("r5-exp", members={"r5_ea": "member"})

        def _draft(sid: str) -> dict:
            d = make_draft(sid)
            d["definition"]["config"]["users"] = dict(_USERS)
            d["definition"]["config"]["services"] = {
                "svc": {"baseUrl": "http://direct-inner"}}
            return d

        # 私有区(属主本人):内置凭证与直连地址照旧(Q3 口径不变)
        r = await client.post("/api/scenarios", headers=h,
                              json=_draft("sc-r5-priv"))
        assert r.status_code in (200, 201), r.text
        r = await client.get("/api/scenarios/sc-r5-priv/export", headers=h)
        assert r.status_code == 200, r.text
        cfg = r.json()["config"]
        assert cfg["users"] == _USERS
        assert cfg["services"]["svc"]["baseUrl"] == "http://direct-inner"
        # 项目区(属主本人创建):导出守区规则 —— 内置凭证当空、直连
        # 地址不生效(修前:属主导出带出明文)
        r = await client.post(f"/api/scenarios?projectId={pid}",
                              headers=h, json=_draft("sc-r5-proj"))
        assert r.status_code in (200, 201), r.text
        r = await client.get("/api/scenarios/sc-r5-proj/export", headers=h)
        assert r.status_code == 200, r.text
        cfg = r.json()["config"]
        assert cfg["users"] == {}
        assert "svc" not in (cfg.get("services") or {})
