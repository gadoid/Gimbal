"""环境组 CRUD 测试（Release v4.4 §11 V5-B；RS3 落地面）。

environments = 团队共享配置（lines 影响执行语义）——读全员，写
Admin+（ops.write，2026-11-11 统一，不再认属主）。
"""
from __future__ import annotations

from app.core import db as db_module
from app.models import Environment

from .helpers import register_and_login


async def test_environment_crud_roundtrip(client, fresh_db):
    await register_and_login(client, "envboss", "pw123456")   # 首注册 = admin
    admin = await register_and_login(client, "envboss", "pw123456")

    r = await client.post("/api/environments", headers=admin, json={
        "name": "SIT", "description": "集成环境",
        "lines": {"fin": "1.0", "platform": "1.0"}})
    assert r.status_code == 201, r.text
    env = r.json()
    assert env["name"] == "SIT"
    assert env["lines"] == {"fin": "1.0", "platform": "1.0"}
    env_id = env["id"]

    # 重名 409
    r = await client.post("/api/environments", headers=admin,
                          json={"name": "SIT"})
    assert r.status_code == 409

    # 读全员
    member = await register_and_login(client, "envm", "pw123456")
    r = await client.get("/api/environments", headers=member)
    assert r.status_code == 200 and len(r.json()) == 1
    r = await client.get(f"/api/environments/{env_id}", headers=member)
    assert r.status_code == 200 and r.json()["name"] == "SIT"

    # 写：平台 user（无 ops.write）→ 403
    r = await client.put(f"/api/environments/{env_id}", headers=member,
                         json={"lines": {"fin": "2.0"}})
    assert r.status_code == 403

    # owner（创建者）可改
    r = await client.put(f"/api/environments/{env_id}", headers=admin,
                         json={"lines": {"fin": "2.0"}})
    assert r.status_code == 200 and r.json()["lines"] == {"fin": "2.0"}

    # 404
    r = await client.get("/api/environments/99999", headers=admin)
    assert r.status_code == 404


async def test_environment_delete_cascades_deployments(
    client, fresh_db, plate
):
    """authz M2a S6:别名不再挂环境(删列),删环境不再被别名引用拦截;
    该环境的部署地址随之级联删除(FK CASCADE)。"""
    plate.services = [{"name": "fin-service"}]
    await register_and_login(client, "envboss2", "pw123456")
    admin = await register_and_login(client, "envboss2", "pw123456")

    r = await client.post("/api/environments", headers=admin,
                          json={"name": "UAT", "lines": {}})
    env_id = r.json()["id"]
    r = await client.post("/api/deployments", headers=admin, json={
        "baseService": "fin-service", "envId": env_id,
        "baseUrl": "https://uat.fin.local"})
    assert r.status_code == 201, r.text

    r = await client.delete(f"/api/environments/{env_id}", headers=admin)
    assert r.status_code == 204
    r = await client.get("/api/deployments", headers=admin)
    assert all(d["envId"] != env_id for d in r.json())


async def test_environment_rename(client, fresh_db):
    """环境降级为轻量标签(2026-11-18):name 可改;重名 409;空名 422。

    id 引用面(实例/部署/账户/条目)全部按 id 挂靠,改名不触碰外键。"""
    await register_and_login(client, "envrename", "pw123456")
    admin = await register_and_login(client, "envrename", "pw123456")

    r = await client.post("/api/environments", headers=admin,
                          json={"name": "SIT", "description": ""})
    assert r.status_code == 201, r.text
    env_id = r.json()["id"]
    r = await client.post("/api/environments", headers=admin,
                          json={"name": "UAT"})
    assert r.status_code == 201, r.text

    # 改名成功
    r = await client.put(f"/api/environments/{env_id}", headers=admin,
                         json={"name": "SIT-2"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "SIT-2"

    # 撞另一环境名 → 409
    r = await client.put(f"/api/environments/{env_id}", headers=admin,
                         json={"name": "UAT"})
    assert r.status_code == 409

    # 空名 → 422(模型 min_length 拦截) / 全空白 → 422(路由 strip 后)
    r = await client.put(f"/api/environments/{env_id}", headers=admin,
                         json={"name": "  "})
    assert r.status_code == 422

    # 只改描述不传 name → 名字不动
    r = await client.put(f"/api/environments/{env_id}", headers=admin,
                         json={"description": "只改说明"})
    assert r.status_code == 200 and r.json()["name"] == "SIT-2"


async def test_environment_resolve_tag(client, fresh_db):
    """标签即环境(2026-11-18):/resolve 按名幂等登记 → 实例标签落地。"""
    await register_and_login(client, "envtag", "pw123456")
    admin = await register_and_login(client, "envtag", "pw123456")

    r = await client.post("/api/environments/resolve", headers=admin,
                          json={"name": "SIT-2"})
    assert r.status_code == 200, r.text
    env = r.json()
    assert env["name"] == "SIT-2"
    # 已存在 → 幂等返回同一行
    r = await client.post("/api/environments/resolve", headers=admin,
                          json={"name": "SIT-2"})
    assert r.status_code == 200 and r.json()["id"] == env["id"]

    # 空白标签 → 422
    r = await client.post("/api/environments/resolve", headers=admin,
                          json={"name": "  "})
    assert r.status_code == 422

    # 写门:普通用户 403
    member = await register_and_login(client, "envtag2", "pw123456")
    r = await client.post("/api/environments/resolve", headers=member,
                          json={"name": "UAT"})
    assert r.status_code == 403
