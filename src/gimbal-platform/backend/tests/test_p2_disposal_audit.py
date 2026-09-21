"""P2-2/P2-3:删号资源处置三选一 + 审计日志。"""
from __future__ import annotations

from tests.helpers import make_draft, register_and_login


async def _mk_scenario(client, headers, sid: str):
    r = await client.post("/api/scenarios", headers=headers, json=make_draft(sid))
    assert r.status_code == 201, r.text


async def _mk_user(client, admin, username: str):
    r = await client.post("/api/users", headers=admin,
                          json={"username": username, "password": "Test2026!"})
    assert r.status_code == 201, r.text
    return r.json()


async def _admin(client, name="p2admin"):
    return await register_and_login(client, name, "pw123456")


async def test_disposal_publicize(client):
    """默认处置:私有场景转公共库,台账保留 + 已注销标注。"""
    admin = await _admin(client)
    victim = await _mk_user(client, admin, "p2_pub_victim")
    await _mk_scenario(client, admin, "sc-p2-pub")  # admin 自己建的场景
    # 把场景转给 victim(owner_id 改写)
    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario

    async with db_module.SessionLocal() as s:
        from sqlalchemy import update
        await s.execute(update(ComposerScenario)
                        .where(ComposerScenario.scenario_id == "sc-p2-pub")
                        .values(owner_id=victim["id"], owner_name="p2_pub_victim"))
        await s.commit()
        # 台账:victim 的一条执行
        from app.models.execution import Execution
        s.add(Execution(scenario_id="sc-p2-pub", owner_id=victim["id"],
                        owner_name="p2_pub_victim", status="passed",
                        total_runs=1, passed=1, failed=0, config_json={}))
        await s.commit()

    r = await client.delete(f"/api/users/{victim['id']}", headers=admin)
    assert r.status_code == 204, r.text

    async with db_module.SessionLocal() as s:
        from sqlalchemy import select
        scen = (await s.execute(select(ComposerScenario)
                                .where(ComposerScenario.scenario_id == "sc-p2-pub"))
                ).scalar_one()
        assert scen.visibility == "public"          # 转公共库
        assert scen.owner_id is None                 # 台账式归属快照
        assert scen.owner_name == "p2_pub_victim"    # 署名保留
        ex = (await s.execute(select(Execution)
                              .where(Execution.scenario_id == "sc-p2-pub"))
              ).scalar_one()
        assert ex.owner_id is None and ex.owner_name == "p2_pub_victim"


async def test_disposal_transfer(client):
    """转让:场景 owner_id 改写 + 受让人收通知 + 个人别名转共享。"""
    admin = await _admin(client, "p2admin_t")
    victim = await _mk_user(client, admin, "p2_t_victim")
    keeper = await _mk_user(client, admin, "p2_t_keeper")
    await _mk_scenario(client, admin, "sc-p2-t")
    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    from app.models.service_alias import ServiceAlias

    async with db_module.SessionLocal() as s:
        from sqlalchemy import update
        await s.execute(update(ComposerScenario)
                        .where(ComposerScenario.scenario_id == "sc-p2-t")
                        .values(owner_id=victim["id"], owner_name="p2_t_victim"))
        # victim 的个人别名
        s.add(ServiceAlias(alias_name="p2-t-alias", base_service="b",
                           owner_user_id=victim["id"]))
        await s.commit()

    r = await client.request(
        "DELETE", f"/api/users/{victim['id']}", headers=admin,
        json={"disposal": "transfer", "transfer_to": keeper["id"]})
    assert r.status_code == 204, r.text

    async with db_module.SessionLocal() as s:
        from sqlalchemy import select
        scen = (await s.execute(select(ComposerScenario)
                                .where(ComposerScenario.scenario_id == "sc-p2-t"))
                ).scalar_one()
        assert scen.owner_id == keeper["id"]          # 归属改写
        alias = (await s.execute(select(ServiceAlias)
                                 .where(ServiceAlias.alias_name == "p2-t-alias"))
                 ).scalar_one()
        assert alias.owner_user_id is None            # 个人别名转共享

    # 受让人收 resource_transferred 通知
    keeper_h = await register_and_login(client, "p2_t_keeper", "Test2026!")
    r = await client.get("/api/notifications?unreadOnly=false", headers=keeper_h)
    notes = r.json()["items"]
    assert any(n["type"] == "resource_transferred" for n in notes)

    # transfer 缺 transfer_to → 422
    v2 = await _mk_user(client, admin, "p2_t_v2")
    r = await client.request("DELETE", f"/api/users/{v2['id']}", headers=admin,
                             json={"disposal": "transfer"})
    assert r.status_code == 422


async def test_disposal_purge(client):
    """purge:场景(含数据集/方案/收藏级联)一并删除,台账保留。"""
    admin = await _admin(client, "p2admin_p")
    victim = await _mk_user(client, admin, "p2_p_victim")
    await _mk_scenario(client, admin, "sc-p2-purge")
    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario

    async with db_module.SessionLocal() as s:
        from sqlalchemy import update
        await s.execute(update(ComposerScenario)
                        .where(ComposerScenario.scenario_id == "sc-p2-purge")
                        .values(owner_id=victim["id"]))
        await s.commit()

    r = await client.request("DELETE", f"/api/users/{victim['id']}", headers=admin,
                             json={"disposal": "purge"})
    assert r.status_code == 204, r.text

    async with db_module.SessionLocal() as s:
        from sqlalchemy import select
        scen = (await s.execute(select(ComposerScenario)
                                .where(ComposerScenario.scenario_id == "sc-p2-purge"))
                ).scalar_one_or_none()
        assert scen is None


async def test_audit_logs_endpoint_and_trail(client):
    """审计:特权写落 trail,admin 分页查询 + 动作过滤;member 403。"""
    from app.core import db as db_module
    from app.models.permission import AuditLog
    from app.services import audit as audit_svc

    admin = await _admin(client, "p2admin_a")
    member_h = await register_and_login(client, "p2_a_member", "pw123456")
    await _mk_user(client, admin, "p2_a_new")   # user.create 落审计

    async with db_module.SessionLocal() as s:
        await audit_svc.record(s, actor_id=None, actor_name="系统",
                               action="announcement.publish",
                               detail={"title": "t"})

    r = await client.get("/api/admin/audit-logs", headers=member_h)
    assert r.status_code == 403

    r = await client.get("/api/admin/audit-logs", headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"items", "total", "page", "pageSize", "actions"} <= set(body)
    assert "user.create" in body["actions"]
    actions = [it["action"] for it in body["items"]]
    assert "user.create" in actions
    assert "announcement.publish" in actions

    # 动作过滤
    r = await client.get("/api/admin/audit-logs", headers=admin,
                         params={"action": "user.create"})
    assert all(it["action"] == "user.create" for it in r.json()["items"])

    # 删号审计(user.delete 带 disposal 详情)
    victim = await _mk_user(client, admin, "p2_a_victim")
    await client.request("DELETE", f"/api/users/{victim['id']}", headers=admin,
                         json={"disposal": "publicize"})
    r = await client.get("/api/admin/audit-logs", headers=admin,
                         params={"action": "user.delete"})
    items = r.json()["items"]
    assert items and items[0]["detail"]["disposal"] == "publicize"
