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
        from sqlalchemy import text as _t
        from sqlalchemy import update

        from tests.helpers import default_space_id
        # UPC M2:归属换主 + 搬进 victim 默认空间(处置面按区判内容;
        # 方案随迁,延迟复合 FK)
        _home = await default_space_id(s, victim["id"])
        await s.execute(_t(
            "SET CONSTRAINTS fk_scheme_scenario_zone, "
            "fk_scheme_combo_zone DEFERRED"))
        await s.execute(update(ComposerScenario)
                        .where(ComposerScenario.scenario_id == "sc-p2-pub")
                        .values(owner_id=victim["id"], owner_name="p2_pub_victim",
                                project_id=_home))
        from app.models.composer_run_scheme import ComposerRunScheme

        await s.execute(update(ComposerRunScheme)
                        .where(ComposerRunScheme.scenario_id == "sc-p2-pub")
                        .values(project_id=_home))
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
        from app.services.zone import public_project_id
        assert scen.project_id == await public_project_id(s)  # 转公共库
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

    async with db_module.SessionLocal() as s:
        from sqlalchemy import text as _t
        from sqlalchemy import update

        from tests.helpers import default_space_id
        _home = await default_space_id(s, victim["id"])
        await s.execute(_t(
            "SET CONSTRAINTS fk_scheme_scenario_zone, "
            "fk_scheme_combo_zone DEFERRED"))
        await s.execute(update(ComposerScenario)
                        .where(ComposerScenario.scenario_id == "sc-p2-t")
                        .values(owner_id=victim["id"], owner_name="p2_t_victim",
                                project_id=_home))
        from app.models.composer_run_scheme import ComposerRunScheme

        await s.execute(update(ComposerRunScheme)
                        .where(ComposerRunScheme.scenario_id == "sc-p2-t")
                        .values(project_id=_home))
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
        from sqlalchemy import text as _t
        from sqlalchemy import update

        from tests.helpers import default_space_id
        _home = await default_space_id(s, victim["id"])
        await s.execute(_t(
            "SET CONSTRAINTS fk_scheme_scenario_zone, "
            "fk_scheme_combo_zone DEFERRED"))
        await s.execute(update(ComposerScenario)
                        .where(ComposerScenario.scenario_id == "sc-p2-purge")
                        .values(owner_id=victim["id"], project_id=_home))
        from app.models.composer_run_scheme import ComposerRunScheme

        await s.execute(update(ComposerRunScheme)
                        .where(ComposerRunScheme.scenario_id == "sc-p2-purge")
                        .values(project_id=_home))
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


async def _seed_combo_bound_scheme(client, admin, victim, tag: str):
    """在 admin 默认空间经 API 建组合 + 场景 + 绑定方案,再整体搬进
    victim 默认空间(处置面按区判内容;§20.2 延迟复合 FK)。"""
    from sqlalchemy import select, text as _t, update

    from app.core import db as db_module
    from app.models.account_combo import AccountCombo
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.models.composer_scenario import ComposerScenario
    from tests.conftest import seed_identity_fixture
    from tests.helpers import default_space_id

    uid = (await client.get("/api/auth/me", headers=admin)
           ).json()["user"]["id"]
    async with db_module.SessionLocal() as s:
        admin_space = await default_space_id(s, uid)
        # 组合条目须指向已登记身份别名(所有者域内登记)
        await seed_identity_fixture(
            s, alias=f"p2-h2-{tag}", username="u", password="p",
            service="fin-service", owner_id=victim["id"])
        await s.commit()
    sid = f"sc-p2h2-{tag}"
    combo_id = (await client.post(
        f"/api/projects/{admin_space}/account-combos", headers=admin,
        json={"name": f"处置组合{tag}", "entries": [
            {"service": "fin-service", "alias": f"p2-h2-{tag}"}]})
    ).json()["id"]
    await _mk_scenario(client, admin, sid)
    r = await client.post(f"/api/scenarios/{sid}/run-schemes",
                          headers=admin,
                          json={"name": f"绑定方案{tag}", "isDefault": False,
                                "accountComboId": combo_id,
                                "dataSetSelection": [],
                                "injectionEntryIds": [],
                                "serviceBindings": {}, "options": {
                                    "step_from": None, "step_to": None,
                                    "n_runs": 1, "parallel": 1,
                                    "subscribe": None}})
    assert r.status_code == 201, r.text

    async with db_module.SessionLocal() as s:
        _home = await default_space_id(s, victim["id"])
        await s.execute(_t(
            "SET CONSTRAINTS fk_scheme_scenario_zone, "
            "fk_scheme_combo_zone DEFERRED"))
        await s.execute(update(ComposerScenario).where(
            ComposerScenario.scenario_id == sid
        ).values(owner_id=victim["id"], owner_name=victim["username"],
                 project_id=_home))
        await s.execute(update(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == sid
        ).values(project_id=_home))
        await s.execute(update(AccountCombo).where(
            AccountCombo.id == combo_id
        ).values(project_id=_home))
        await s.commit()
    return sid


async def test_disposal_severs_combo_bindings(client):
    """评审 H2 收口:绑定组合的方案随处置迁出私有空间时,组合绑定解离
    为 blocked(combo_missing)—— 不再撞 fk_scheme_combo_zone 让删号
    500;组合本身随私有容器处置消失;publicize 与 transfer 两分支。"""
    from sqlalchemy import select

    from app.core import db as db_module
    from app.models.account_combo import AccountCombo
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.models.composer_scenario import ComposerScenario
    from app.services.zone import public_project_id

    admin = await _admin(client, "p2h2admin")

    # ── publicize:方案迁公共项目,绑定解离 ─────────────────────────
    victim = await _mk_user(client, admin, "p2_h2_pub")
    sid = await _seed_combo_bound_scheme(client, admin, victim, "pub")
    r = await client.request("DELETE", f"/api/users/{victim['id']}",
                             headers=admin, json={"disposal": "publicize"})
    assert r.status_code == 204, r.text
    async with db_module.SessionLocal() as s:
        scen = (await s.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == sid))).scalar_one()
        assert scen.project_id == await public_project_id(s)
        rows = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == sid))).scalars().all()
        row = next(x for x in rows if x.name == "绑定方案pub")
        assert row.repair_status == "blocked"
        assert row.repair_reason == "combo_missing"
        assert row.account_combo_id is None
        assert (await s.execute(select(AccountCombo).where(
            AccountCombo.project_id == scen.project_id))).scalars().all() == []

    # ── transfer:方案迁受让人空间,绑定解离 ────────────────────────
    victim2 = await _mk_user(client, admin, "p2_h2_tr_victim")
    keeper = await _mk_user(client, admin, "p2_h2_tr_keeper")
    sid2 = await _seed_combo_bound_scheme(client, admin, victim2, "tr")
    r = await client.request(
        "DELETE", f"/api/users/{victim2['id']}", headers=admin,
        json={"disposal": "transfer", "transfer_to": keeper["id"]})
    assert r.status_code == 204, r.text
    async with db_module.SessionLocal() as s:
        from tests.helpers import default_space_id

        _keeper_space = await default_space_id(s, keeper["id"])
        scen2 = (await s.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == sid2))).scalar_one()
        assert scen2.project_id == _keeper_space
        rows2 = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == sid2))).scalars().all()
        row2 = next(x for x in rows2 if x.name == "绑定方案tr")
        assert row2.repair_status == "blocked"
        assert row2.repair_reason == "combo_missing"
        assert row2.account_combo_id is None
        assert (await s.execute(select(AccountCombo).where(
            AccountCombo.project_id == _keeper_space
        ))).scalars().all() == []
