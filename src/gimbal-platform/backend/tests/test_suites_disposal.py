"""权限域二期 P1:删号处置三路径下的 suite 处置。

《Suite成员层、引用分享与浏览镜头-设计方案》§7.10:
- publicize:**先删**该用户全部 suite(成员行级联),再置空场景属主
  —— 组合外键在 owner 置 NULL 时失配,顺序不可倒;
- transfer:suite/成员/场景三处 owner_id 同一事务改写(整体转让,
  库层 DEFERRED 约束拒绝拆分);
- purge:suite 全删,场景照旧删除。
"""
from __future__ import annotations

from tests.helpers import make_draft, register_and_login


async def _mk_scenario(client, headers, sid: str):
    r = await client.post("/api/scenarios", headers=headers,
                          json=make_draft(sid))
    assert r.status_code == 201, r.text


async def _mk_user(client, admin, username: str):
    r = await client.post("/api/users", headers=admin,
                          json={"username": username, "password": "Test2026!"})
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_suite(client, headers, name: str, sids: list[str]) -> int:
    r = await client.post("/api/suites", headers=headers,
                          json={"name": name, "description": ""})
    assert r.status_code == 201, r.text
    sid = r.json()["suiteId"]
    r = await client.post(f"/api/suites/{sid}/members", headers=headers,
                          json={"scenarioIds": sids})
    assert r.status_code == 200, r.text
    return sid


async def _seed_victim_with_suite(client, admin, tag: str) -> tuple[dict, int]:
    """victim 建一个场景 + 一个含该场景的 suite。"""
    victim = await _mk_user(client, admin, f"sp_{tag}_victim")
    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    from sqlalchemy import update

    # 用 victim 会话直接建(登录口令是 admin 开号的 Test2026!)
    from tests.helpers import login_user
    vh = await login_user(client, f"sp_{tag}_victim", "Test2026!")
    await _mk_scenario(client, vh, f"sc-sp-{tag}")
    async with db_module.SessionLocal() as s:
        await s.execute(update(ComposerScenario)
                        .where(ComposerScenario.scenario_id == f"sc-sp-{tag}")
                        .values(owner_id=victim["id"],
                                owner_name=f"sp_{tag}_victim"))
        await s.commit()
    sid = await _mk_suite(client, vh, f"{tag}的组", [f"sc-sp-{tag}"])
    # suite 建在 victim 会话 → owner 已是 victim;无需改写
    return victim, sid


async def test_disposal_publicize_deletes_suites_first(client):
    admin = await register_and_login(client, "sp_admin1", "pw123456")
    victim, sid = await _seed_victim_with_suite(client, admin, "pub")

    r = await client.request("DELETE", f"/api/users/{victim['id']}",
                             headers=admin, json={"disposal": "publicize"})
    assert r.status_code == 204, r.text

    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    from app.models.suite import Suite, SuiteMember
    from sqlalchemy import select

    async with db_module.SessionLocal() as s:
        assert (await s.execute(
            select(Suite).where(Suite.id == sid))).scalar_one_or_none() is None
        assert (await s.execute(
            select(SuiteMember).where(SuiteMember.suite_id == sid))
            ).scalars().all() == []
        scen = (await s.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-sp-pub"))).scalar_one()
        assert scen.visibility == "public" and scen.owner_id is None


async def test_disposal_transfer_moves_suite_wholesale(client):
    admin = await register_and_login(client, "sp_admin2", "pw123456")
    victim, sid = await _seed_victim_with_suite(client, admin, "xfer")
    keeper = await _mk_user(client, admin, "sp_xfer_keeper")

    r = await client.request(
        "DELETE", f"/api/users/{victim['id']}", headers=admin,
        json={"disposal": "transfer", "transfer_to": keeper["id"]})
    assert r.status_code == 204, r.text

    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    from app.models.suite import Suite, SuiteMember
    from sqlalchemy import select

    async with db_module.SessionLocal() as s:
        suite = (await s.execute(
            select(Suite).where(Suite.id == sid))).scalar_one()
        member = (await s.execute(
            select(SuiteMember).where(SuiteMember.suite_id == sid))
        ).scalar_one()
        scen = (await s.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-sp-xfer"))).scalar_one()
        # 三处 owner 同一事务整体改写(不可拆分)
        assert suite.owner_id == keeper["id"]
        assert member.owner_id == keeper["id"]
        assert scen.owner_id == keeper["id"]


async def test_disposal_purge_removes_suites_and_scenarios(client):
    admin = await register_and_login(client, "sp_admin3", "pw123456")
    victim, sid = await _seed_victim_with_suite(client, admin, "purge")

    r = await client.request("DELETE", f"/api/users/{victim['id']}",
                             headers=admin, json={"disposal": "purge"})
    assert r.status_code == 204, r.text

    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    from app.models.suite import Suite
    from sqlalchemy import select

    async with db_module.SessionLocal() as s:
        assert (await s.execute(
            select(Suite).where(Suite.id == sid))).scalar_one_or_none() is None
        assert (await s.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-sp-purge"))
        ).scalar_one_or_none() is None
