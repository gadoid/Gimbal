"""实例 × 凭证匹配聚合端点(A 级批次,2026-11-18)。

GET /api/projects/{pid}/instance-credential-matches?envId= — 配置页
「服务实例 × 凭证匹配」分区原由前端拼 5 路端点,此处一次拉齐:行 =
环境下的注册簿实例,按 (system, env) 拼部署地址(经服务主档翻译
name→system)+ 项目凭证(成员视图 username 脱敏)+ 个人池计数。

门与项目凭证列表同口径:普通项目成员(Admin+ 非成员同 404)、
公共项目 409。
"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import register_and_login, role_headers


async def _uid(client: AsyncClient, token_headers: dict, username: str) -> int:
    roster = (await client.get(
        "/api/users/roster", headers=token_headers)).json()["items"]
    return next(u["id"] for u in roster if u["username"] == username)


async def _seed_matrix(client: AsyncClient) -> tuple[int, dict, dict, dict]:
    """布景:SIT 环境 + fin 实例 + fin-api 服务/部署 + 项目(pa 管理员
    /mb 成员)+ 项目凭证 + mb 个人凭证。返回 (env, pid, h_pa, h_mb)。"""
    await register_and_login(client, "icm_root", "pw123456")
    admin = await register_and_login(client, "icm_root", "pw123456")
    h_pa = await role_headers(client, "icm_pa", role="user")
    h_mb = await role_headers(client, "icm_mb", role="user")
    h_out = await role_headers(client, "icm_out", role="user")
    pa_uid = await _uid(client, admin, "icm_pa")
    mb_uid = await _uid(client, admin, "icm_mb")

    r = await client.post("/api/environments", headers=admin,
                          json={"name": "SIT"})
    assert r.status_code == 201, r.text
    env = r.json()["id"]

    r = await client.put(f"/api/services/instances/fin/{env}", headers=admin,
                         json={"loginUrl": "https://sit.fin.local/auth",
                               "line": "1.0"})
    assert r.status_code == 201, r.text
    r = await client.post("/api/services", headers=admin, json={
        "name": "fin-api", "system": "fin", "kind": "external"})
    assert r.status_code == 201, r.text
    r = await client.post("/api/deployments", headers=admin, json={
        "baseService": "fin-api", "envId": env,
        "baseUrl": "https://sit.fin.local/api"})
    assert r.status_code == 201, r.text

    pid = (await client.post("/api/projects", headers=admin, json={
        "name": "icm-proj", "description": "",
        "firstAdminUserId": pa_uid})).json()["id"]
    assert (await client.post(f"/api/projects/{pid}/members", headers=h_pa,
                              json={"userId": mb_uid})).status_code == 201

    # 项目凭证(管理面:pa)
    r = await client.post(f"/api/projects/{pid}/credentials", headers=h_pa,
                          json={"system": "fin", "envId": env,
                                "username": "svc-fin", "password": "secret123",
                                "isDefault": True})
    assert r.status_code == 201, r.text
    # mb 的个人凭证
    r = await client.post("/api/auths", headers=h_mb, json={
        "system": "fin", "envId": env,
        "username": "mb-personal", "password": "secret456"})
    assert r.status_code == 201, r.text

    # 路人非成员 → 404(读面不因存在泄露)
    r = await client.get(f"/api/projects/{pid}/instance-credential-matches",
                         params={"envId": env}, headers=h_out)
    assert r.status_code == 404, r.text
    return env, pid, h_pa, h_mb


async def test_match_matrix_admin_vs_member_view(client, fresh_db):
    """聚合行:地址经主档翻译归系统行;管理员见 username / 成员脱敏;
    个人池只回计数。"""
    env, pid, h_pa, h_mb = await _seed_matrix(client)

    r = await client.get(f"/api/projects/{pid}/instance-credential-matches",
                         params={"envId": env}, headers=h_pa)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["envId"] == env and body["canManage"] is True
    assert len(body["instances"]) == 1
    row = body["instances"][0]
    assert row["system"] == "fin" and row["loginUrl"] == "https://sit.fin.local/auth"
    assert row["line"] == "1.0"
    assert row["addresses"] == [{"service": "fin-api",
                                 "baseUrl": "https://sit.fin.local/api"}]
    assert row["projectCredentials"] == [{"id": row["projectCredentials"][0]["id"],
                                          "username": "svc-fin",
                                          "isDefault": True}]
    assert row["personalCount"] == 0              # pa 本人没有个人凭证

    # 成员视图:canManage=false、username 脱敏、个人池计数 = 1
    r = await client.get(f"/api/projects/{pid}/instance-credential-matches",
                         params={"envId": env}, headers=h_mb)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["canManage"] is False
    row = body["instances"][0]
    assert row["projectCredentials"][0]["username"] == ""
    assert row["personalCount"] == 1


async def test_match_scoped_to_env(client, fresh_db):
    """行集按 envId 收敛:另一环境的实例/地址/凭证不进结果。"""
    env, pid, h_pa, _h_mb = await _seed_matrix(client)
    admin = await register_and_login(client, "icm_root", "pw123456")

    other = (await client.post("/api/environments", headers=admin,
                               json={"name": "UAT"})).json()["id"]
    r = await client.put(f"/api/services/instances/logi/{other}",
                         headers=admin, json={"loginUrl": "https://uat/x"})
    assert r.status_code == 201, r.text

    r = await client.get(f"/api/projects/{pid}/instance-credential-matches",
                         params={"envId": other}, headers=h_pa)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [i["system"] for i in body["instances"]] == ["logi"]
    assert body["instances"][0]["addresses"] == []
    assert body["instances"][0]["projectCredentials"] == []
