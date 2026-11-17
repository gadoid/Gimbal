"""服务说明读写面(registry rework §1.1;P1-7 续期)。

``service_meta`` 表与 ``/api/service-meta`` 端点已退役:说明是服务主档
``services.description`` 的一列(前端 api/service-meta.ts 保形门面)。
本文件按原语义等价覆盖到主档面:

* 读全员(CurrentUser):注册簿/矩阵/子页展示都不是秘密;
* 写 Admin+(MemberUser = ops.write):POST 登记 + PATCH 改说明;
* description 1024 封顶(超长 422);
* 删除保护:部署/条目挂靠 → 409。
"""
from __future__ import annotations

from .test_carry_api import _admin
from .test_scenario_visibility_and_copy import _member


async def test_read_all_write_gate_and_description(client, fresh_db):
    admin = await _admin(client)
    member = await _member(client, "meta_member")

    # 空主档 → services []
    r = await client.get("/api/services", headers=member)
    assert r.status_code == 200, r.text
    assert r.json()["services"] == []

    # 读全员;写面:普通用户 403(ops.write)
    r = await client.post("/api/services", headers=member,
                          json={"name": "fin-service"})
    assert r.status_code == 403
    assert "capability_forbidden" in r.text

    # admin 登记(说明随建落列)
    r = await client.post("/api/services", headers=admin, json={
        "name": "fin-service", "system": "fin", "kind": "plate",
        "description": "交易核心服务,负责订单/支付"})
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "fin-service"
    assert "交易核心" in r.json()["description"]

    # admin PATCH 改说明(旧 upsert 语义的等价面:同服务覆写,不新增行)
    r = await client.patch("/api/services/fin-service", headers=admin,
                           json={"description": "交易核心(v2 描述)"})
    assert r.status_code == 200, r.text
    assert "交易核心(v2 描述)" in r.json()["description"]

    rows = (await client.get("/api/services", headers=member)
            ).json()["services"]
    assert len(rows) == 1
    assert rows[0]["description"] == "交易核心(v2 描述)"

    # 多服务:按 (system, name) 排序
    r = await client.post("/api/services", headers=admin, json={
        "name": "agent-sys", "system": "agent", "kind": "external",
        "description": "第三方网关"})
    assert r.status_code == 201, r.text
    r = await client.get("/api/services", headers=member)
    names = [s["name"] for s in r.json()["services"]]
    assert names == ["agent-sys", "fin-service"]

    # 重复登记 409;未知服务 PATCH 404
    r = await client.post("/api/services", headers=admin,
                          json={"name": "fin-service"})
    assert r.status_code == 409
    r = await client.patch("/api/services/ghost-svc", headers=admin,
                           json={"description": "x"})
    assert r.status_code == 404

    # 超长 422(主档说明 1024 封顶;service_meta 时代是 512)
    r = await client.post("/api/services", headers=admin, json={
        "name": "long-svc", "description": "x" * 1025})
    assert r.status_code == 422


async def test_delete_guarded_by_hooks(client, fresh_db):
    """删主档:无挂靠 204;有身份条目挂靠 → 409 service_in_use。"""
    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models import Environment, Service, ServiceIdentity

    admin = await _admin(client)
    await client.post("/api/services", headers=admin,
                      json={"name": "free-svc", "kind": "external"})
    r = await client.delete("/api/services/free-svc", headers=admin)
    assert r.status_code == 204, r.text

    await client.post("/api/services", headers=admin,
                      json={"name": "hooked-svc", "kind": "external"})
    async with db_module.SessionLocal() as s:
        s.add(Environment(name="测试", is_default=True))
        await s.flush()
        env = (await s.execute(sa.select(Environment.id).where(
            Environment.name == "测试"))).scalar_one()
        svc_id = (await s.execute(sa.select(Service.id).where(
            Service.name == "hooked-svc"))).scalar_one()
        _ = svc_id
        s.add(ServiceIdentity(alias_name="hooked-svc-x",
                              base_service="hooked-svc", env_id=env,
                              ref_mode="default"))
        await s.commit()
    r = await client.delete("/api/services/hooked-svc", headers=admin)
    assert r.status_code == 409, r.text
    assert "service_in_use" in r.text


async def test_import_catalog_batch(client, fresh_db, monkeypatch):
    """M5 对账横幅「立即批量映射」:批量登记 → system/kind 取目录聚合行;
    幂等(第二次全 skipped);names 子集;plate 不可达降级。"""
    from app.services import plate_client

    admin = await _admin(client)

    async def fake_rows(*, refresh: bool = False):
        return [
            {"name": "fin-service", "system": "fin", "endpointCount": 3,
             "kind": "sut"},
            {"name": "jira-sync", "system": "jira", "endpointCount": 1,
             "kind": "integration"},
        ]

    monkeypatch.setattr(plate_client, "catalog_service_rows", fake_rows)

    r = await client.post("/api/services/import-catalog", headers=admin,
                          json={})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["created"] == ["fin-service", "jira-sync"]
    assert out["skipped"] == []
    assert out["unregistered"] == []

    rows = (await client.get("/api/services", headers=admin)
            ).json()["services"]
    by_name = {s["name"]: s for s in rows}
    assert by_name["fin-service"]["system"] == "fin"
    assert by_name["fin-service"]["kind"] == "plate"      # sut → plate
    assert by_name["jira-sync"]["kind"] == "integration"  # integration 保形

    # 幂等:第二次无可导入(候选 = 目录 − 主档 = 空),skipped 也空
    r = await client.post("/api/services/import-catalog", headers=admin,
                          json={})
    assert r.json()["created"] == []
    assert r.json()["skipped"] == []
    assert r.json()["unregistered"] == []

    # names 子集:已在主档 → skipped;不在目录 → skipped
    r = await client.post("/api/services/import-catalog", headers=admin,
                          json={"names": ["fin-service", "ghost-svc"]})
    assert r.json()["created"] == []
    assert sorted(r.json()["skipped"]) == ["fin-service", "ghost-svc"]

    # 普通成员无权(写面 = ops.write)
    member = await _member(client, "import_member")
    r = await client.post("/api/services/import-catalog", headers=member,
                          json={})
    assert r.status_code == 403


async def test_import_catalog_plate_unreachable(client, fresh_db,
                                                monkeypatch):
    from app.services import plate_client

    admin = await _admin(client)

    async def boom(*, refresh: bool = False):
        raise RuntimeError("plate down")

    monkeypatch.setattr(plate_client, "catalog_service_rows", boom)
    r = await client.post("/api/services/import-catalog", headers=admin,
                          json={})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["plateReachable"] is False
    assert out["created"] == []
