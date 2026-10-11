"""环境组 CRUD 测试（Release v4.4 §11 V5-B；RS3 落地面）。

environments = 团队共享配置（lines 影响执行语义）——读全员，写
owner/admin；被服务别名引用的环境不可删除。
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

    # 写：member 非 owner → 403
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


async def test_environment_delete_blocked_by_alias_reference(
    client, fresh_db, plate
):
    plate.services = [{"name": "fin-service"}]
    await register_and_login(client, "envboss2", "pw123456")
    admin = await register_and_login(client, "envboss2", "pw123456")

    r = await client.post("/api/environments", headers=admin,
                          json={"name": "UAT", "lines": {}})
    env_id = r.json()["id"]

    r = await client.post("/api/service-aliases", headers=admin, json={
        "aliasName": "fin-service-uat", "baseUrl": "https://uat.fin.local",
        "environmentId": env_id})
    assert r.status_code == 201, r.text

    # 被引用 → 409；解除引用后方可删
    r = await client.delete(f"/api/environments/{env_id}", headers=admin)
    assert r.status_code == 409

    r = await client.patch("/api/service-aliases/fin-service-uat",
                           headers=admin, json={"environmentId": None})
    assert r.status_code == 200 and r.json()["environmentId"] is None

    r = await client.delete(f"/api/environments/{env_id}", headers=admin)
    assert r.status_code == 204
