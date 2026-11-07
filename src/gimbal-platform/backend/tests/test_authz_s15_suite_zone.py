"""M2a S1.5:suite 同区约束端点验收(应用层 422 单点 + 触发器兜底)。"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import make_draft, role_headers


async def _mk_project(name: str, members: dict[str, str]) -> int:
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.project import Project, ProjectMember
    from app.models.user import User

    async with db_module.SessionLocal() as db:
        proj = Project(name=name, kind="normal", description="")
        db.add(proj)
        await db.flush()
        for uname, role in members.items():
            uid = (await db.execute(sa_select(User.id).where(
                User.username == uname))).scalar_one()
            db.add(ProjectMember(project_id=proj.id, user_id=uid,
                                 role=role))
        await db.commit()
        return proj.id


async def _move(sid: str, pid: int | None) -> None:
    from sqlalchemy import select as sa_select, update as _upd

    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario

    async with db_module.SessionLocal() as db:
        row = (await db.execute(sa_select(ComposerScenario).where(
            ComposerScenario.scenario_id == sid))).scalar_one()
        row.project_id = pid
        await db.commit()


class TestSameZoneConstraint:
    async def test_private_suite_rejects_others_scenario(self, client):
        """私有区同属主规则保留:私有套件加他人场景 → 422
        suite_member_cross_zone(旧口径是 404 一刀切)。"""
        h_a = await role_headers(client, "s15_a", role="user")
        h_b = await role_headers(client, "s15_b", role="user")
        await client.post("/api/scenarios", headers=h_a,
                          json=make_draft("sc-s15-own"))
        await client.post("/api/scenarios", headers=h_b,
                          json=make_draft("sc-s15-other"))
        r = await client.post("/api/suites", headers=h_a,
                              json={"name": "s15-priv", "description": ""})
        sid = r.json()["suiteId"]
        r = await client.post(f"/api/suites/{sid}/members", headers=h_a,
                              json={"scenarioIds": ["sc-s15-other"]})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "suite_member_cross_zone"
        # 自己的场景照常 200
        r = await client.post(f"/api/suites/{sid}/members", headers=h_a,
                              json={"scenarioIds": ["sc-s15-own"]})
        assert r.status_code == 200, r.text

    async def test_project_suite_accepts_other_members_scenario(self, client):
        """S1.5 解锁:项目套件可容纳其他成员的场景(同 project_id,
        属主无关)—— D1「权限只看项目角色」的成员层落地。"""
        h_a = await role_headers(client, "s15_pa", role="user")
        h_b = await role_headers(client, "s15_pb", role="user")
        await client.post("/api/scenarios", headers=h_a,
                          json=make_draft("sc-s15-ma"))
        await client.post("/api/scenarios", headers=h_b,
                          json=make_draft("sc-s15-mb"))
        r = await client.post("/api/suites", headers=h_a,
                              json={"name": "s15-proj", "description": ""})
        suite_id = r.json()["suiteId"]
        pid = await _mk_project(
            "s15-zone", members={"s15_pa": "admin", "s15_pb": "member"})
        await _move("sc-s15-ma", pid)
        await _move("sc-s15-mb", pid)
        # 套件进项目(同区)
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.suite import Suite as _Suite

        async with db_module.SessionLocal() as db:
            row = (await db.execute(sa_select(_Suite).where(
                _Suite.id == suite_id))).scalar_one()
            row.project_id = pid
            await db.commit()

        r = await client.post(f"/api/suites/{suite_id}/members",
                              headers=h_a,
                              json={"scenarioIds": ["sc-s15-ma", "sc-s15-mb"]})
        assert r.status_code == 200, r.text
        members = r.json()["members"]
        assert {m["scenarioId"] for m in members} == {
            "sc-s15-ma", "sc-s15-mb"}

    async def test_cross_zone_rejected_both_ways(self, client):
        h_a = await role_headers(client, "s15_ca", role="user")
        await client.post("/api/scenarios", headers=h_a,
                          json=make_draft("sc-s15-cp"))
        await client.post("/api/scenarios", headers=h_a,
                          json=make_draft("sc-s15-cv"))
        r = await client.post("/api/suites", headers=h_a,
                              json={"name": "s15-cross", "description": ""})
        suite_id = r.json()["suiteId"]
        pid = await _mk_project("s15-xzone", members={"s15_ca": "admin"})
        await _move("sc-s15-cv", pid)   # 场景进项目,套件仍私有

        # 私有套件 + 项目场景 → 422
        r = await client.post(f"/api/suites/{suite_id}/members", headers=h_a,
                              json={"scenarioIds": ["sc-s15-cv"]})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "suite_member_cross_zone"

        # 项目套件 + 私有场景 → 422
        from app.core import db as db_module
        from sqlalchemy import select as sa_select

        from app.models.suite import Suite as _Suite

        async with db_module.SessionLocal() as db:
            row = (await db.execute(sa_select(_Suite).where(
                _Suite.id == suite_id))).scalar_one()
            row.project_id = pid
            await db.commit()
        r = await client.post(f"/api/suites/{suite_id}/members", headers=h_a,
                              json={"scenarioIds": ["sc-s15-cp"]})
        assert r.status_code == 422, r.text

    async def test_composition_same_gate(self, client):
        """put_composition 与 add_members 同一单点:他人场景 → 422。"""
        h_a = await role_headers(client, "s15_ta", role="user")
        h_b = await role_headers(client, "s15_tb", role="user")
        await client.post("/api/scenarios", headers=h_a,
                          json=make_draft("sc-s15-ta"))
        await client.post("/api/scenarios", headers=h_b,
                          json=make_draft("sc-s15-tb"))
        r = await client.post("/api/suites", headers=h_a,
                              json={"name": "s15-comp", "description": ""})
        suite_id = r.json()["suiteId"]
        r = await client.put(f"/api/suites/{suite_id}/composition",
                             headers=h_a,
                             json={"rev": 0, "mode": "aggregate",
                                   "members": [{"scenarioId": "sc-s15-tb"}],
                                   "modeConfig": {}})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "suite_member_cross_zone"

    async def test_direct_sql_rejected_by_trigger(self, client):
        """直插绕过应用层 → 同区触发器拒绝(库层兜底;conftest 建库
        即挂与 0042 同源的触发器)。"""
        import sqlalchemy.exc

        from sqlalchemy import text

        from app.core import db as db_module
        import pytest

        h_a = await role_headers(client, "s15_da", role="user")
        h_b = await role_headers(client, "s15_db", role="user")
        await client.post("/api/scenarios", headers=h_a,
                          json=make_draft("sc-s15-da"))
        await client.post("/api/scenarios", headers=h_b,
                          json=make_draft("sc-s15-db"))
        r = await client.post("/api/suites", headers=h_a,
                              json={"name": "s15-trg", "description": ""})
        suite_id = r.json()["suiteId"]
        with pytest.raises(sqlalchemy.exc.DBAPIError):
            async with db_module.SessionLocal() as db:
                await db.execute(text(
                    "INSERT INTO suite_members "
                    "(suite_id, scenario_id, role, sort, added_at) "
                    "VALUES (:sid, :scen, 'main', 0, now())"),
                    {"sid": suite_id, "scen": "sc-s15-db"})
                await db.commit()
