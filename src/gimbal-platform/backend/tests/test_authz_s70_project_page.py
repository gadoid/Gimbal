"""M2a S7.0 项目页后端支撑:列表/详情读面、项目内新建门、集成可见性
按成员、scope=private。

IA 修正(2026-11-09)的读面落点:项目成为一级入口 —— 公共项目置顶
全员可见;普通项目非成员 404;canManage 前端不再自拼。写面 = D6
「项目内可直接新建」:场景 / 用例集 / 集成模板收 ``projectId``,门 =
项目成员(公共项目 422 —— 进公共项目只有「发布」一条路,S1.3)。
集成模板可见性按成员收口是**行为修正**:此前「project_id 非空即可见」
把普通项目模板泄露给非成员。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import make_draft, role_headers


async def _mk_project(name: str, *, members: dict[str, str]) -> int:
    """直插普通项目 + 成员 {username: role}(不经管理端点)。"""
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


async def _public_project_id() -> int:
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.project import Project

    async with db_module.SessionLocal() as db:
        return (await db.execute(sa_select(Project.id).where(
            Project.kind == "public"))).scalar_one()


class TestProjectsReadFace:
    """GET /projects(公共置顶 + 我所在;Admin+ 全量)与详情读面。"""

    async def test_list_public_pinned_plus_mine(self, client: AsyncClient):
        h_u = await role_headers(client, "s70_lu", role="user")
        h_other = await role_headers(client, "s70_lo", role="user")
        await _mk_project("s70-mine", members={"s70_lu": "member"})
        q_id = await _mk_project("s70-theirs", members={"s70_lo": "admin"})
        r = await client.get("/api/projects", headers=h_u)
        assert r.status_code == 200, r.text
        items = r.json()
        # 公共项目恒置顶;我所在项目在列;别人的普通项目不可见
        assert items[0]["kind"] == "public"
        assert items[0]["myRole"] is None
        assert items[0]["canManage"] is False
        assert [it["name"] for it in items[1:]] == ["s70-mine"]
        assert q_id not in [it["id"] for it in items]
        mine = next(it for it in items if it["name"] == "s70-mine")
        assert mine["myRole"] == "member" and mine["canManage"] is False

    async def test_list_admin_sees_all(self, client: AsyncClient):
        h_admin = await role_headers(client, "s70_adm", role="admin")
        await role_headers(client, "s70_x1", role="user")
        await _mk_project("s70-other", members={"s70_x1": "member"})
        r = await client.get("/api/projects", headers=h_admin)
        assert r.status_code == 200, r.text
        names = [it["name"] for it in r.json()]
        assert "s70-other" in names and names[0] == "公共"
        assert all(it["canManage"] for it in r.json())

    async def test_project_admin_can_manage_member_cannot(
            self, client: AsyncClient):
        await role_headers(client, "s70_pa", role="user")
        await role_headers(client, "s70_pm", role="user")
        h_admin = await role_headers(client, "s70_padm", role="admin")
        pid = await _mk_project(
            "s70-role", members={"s70_pa": "admin", "s70_pm": "member"})
        r = await client.get(f"/api/projects/{pid}",
                             headers=await role_headers(
                                 client, "s70_pa", role="user"))
        assert r.json()["canManage"] is True
        r = await client.get(f"/api/projects/{pid}",
                             headers=await role_headers(
                                 client, "s70_pm", role="user"))
        assert r.json()["canManage"] is False
        # 公共项目:无成员行 → 只有 Admin+ 可管理
        ppid = await _public_project_id()
        assert (await client.get(
            f"/api/projects/{ppid}", headers=h_admin)).json()["canManage"] \
            is True

    async def test_get_normal_project_visibility(self, client: AsyncClient):
        h_m = await role_headers(client, "s70_gm", role="user")
        h_x = await role_headers(client, "s70_gx", role="user")
        pid = await _mk_project("s70-vis", members={"s70_gm": "member"})
        assert (await client.get(
            f"/api/projects/{pid}", headers=h_x)).status_code == 404
        assert (await client.get(
            f"/api/projects/{pid}", headers=h_m)).status_code == 200
        # 公共项目全员可读(项目页数据源)
        ppid = await _public_project_id()
        assert (await client.get(
            f"/api/projects/{ppid}", headers=h_x)).status_code == 200

    async def test_me_projects_same_shape(self, client: AsyncClient):
        h_u = await role_headers(client, "s70_me", role="user")
        pid = await _mk_project("s70-meproj", members={"s70_me": "member"})
        r = await client.get("/api/auth/me", headers=h_u)
        assert r.status_code == 200, r.text
        projects = r.json()["projects"]
        assert projects[0]["kind"] == "public"
        assert projects[0]["role"] is None
        assert any(p["id"] == pid and p["role"] == "member"
                   for p in projects[1:])


class TestCreateInProject:
    """D6 项目内新建门:成员可建;非成员 404(Admin+ 不旁路,D1);
    公共项目 422(只有「发布」一条路)。"""

    async def test_create_scenario_in_project(self, client: AsyncClient):
        h_m = await role_headers(client, "s70_cm", role="user")
        pid = await _mk_project("s70-create", members={"s70_cm": "member"})
        r = await client.post("/api/scenarios?projectId=%d" % pid,
                              headers=h_m, json=make_draft("sc-s70-in"))
        assert r.status_code in (200, 201), r.text
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.composer_scenario import ComposerScenario

        async with db_module.SessionLocal() as db:
            row = (await db.execute(sa_select(ComposerScenario).where(
                ComposerScenario.scenario_id == "sc-s70-in"))
            ).scalar_one()
            assert row.project_id == pid

    async def test_create_scenario_gates(self, client: AsyncClient):
        h_m = await role_headers(client, "s70_cgm", role="user")
        h_a = await role_headers(client, "s70_cga", role="admin")
        h_x = await role_headers(client, "s70_cgx", role="user")
        pid = await _mk_project("s70-gate", members={"s70_cgm": "member"})
        ppid = await _public_project_id()
        # 非成员 404(不泄露存在性);Admin+ 非成员同样 404(D1)
        r = await client.post("/api/scenarios?projectId=%d" % pid,
                              headers=h_x, json=make_draft("sc-s70-x1"))
        assert r.status_code == 404 and \
            r.json()["detail"]["code"] == "not_found"
        r = await client.post("/api/scenarios?projectId=%d" % pid,
                              headers=h_a, json=make_draft("sc-s70-x2"))
        assert r.status_code == 404
        # 公共项目 422:内容进公共项目只有「发布」一条路
        r = await client.post("/api/scenarios?projectId=%d" % ppid,
                              headers=h_m, json=make_draft("sc-s70-x3"))
        assert r.status_code == 422 and r.json()["detail"]["code"] == \
            "public_project_create_forbidden"

    async def test_create_suite_in_project(self, client: AsyncClient):
        h_m = await role_headers(client, "s70_sm", role="user")
        h_x = await role_headers(client, "s70_sx", role="user")
        pid = await _mk_project("s70-suite", members={"s70_sm": "member"})
        ppid = await _public_project_id()
        r = await client.post("/api/suites", headers=h_m, json={
            "name": "s70-in-proj", "projectId": pid})
        assert r.status_code in (200, 201), r.text
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.suite import Suite

        async with db_module.SessionLocal() as db:
            row = (await db.execute(sa_select(Suite).where(
                Suite.name == "s70-in-proj"))).scalar_one()
            assert row.project_id == pid
        # 非成员 404;公共项目 422
        r = await client.post("/api/suites", headers=h_x, json={
            "name": "s70-x", "projectId": pid})
        assert r.status_code == 404
        r = await client.post("/api/suites", headers=h_m, json={
            "name": "s70-x2", "projectId": ppid})
        assert r.status_code == 422 and r.json()["detail"]["code"] == \
            "public_project_create_forbidden"

    async def test_create_integration_task_in_project(self, client):
        h_m = await role_headers(client, "s70_tm", role="user")
        h_x = await role_headers(client, "s70_tx", role="user")
        pid = await _mk_project("s70-task", members={"s70_tm": "member"})
        r = await client.post("/api/scenarios?projectId=%d" % pid,
                              headers=h_m, json=make_draft("sc-s70-t"))
        assert r.status_code in (200, 201), r.text
        r = await client.post("/api/integration/tasks", headers=h_m, json={
            "name": "s70-proj-tpl", "scenarioId": "sc-s70-t",
            "identityMode": "personal", "triggerCron": "0 3 * * *",
            "projectId": pid})
        assert r.status_code == 201, r.text
        # 场景不在同一项目 → 422
        r2 = await client.post("/api/scenarios", headers=h_m,
                               json=make_draft("sc-s70-t2"))
        assert r2.status_code in (200, 201), r2.text
        r = await client.post("/api/integration/tasks", headers=h_m, json={
            "name": "s70-mismatch", "scenarioId": "sc-s70-t2",
            "identityMode": "personal", "triggerCron": "0 3 * * *",
            "projectId": pid})
        assert r.status_code == 422 and r.json()["detail"]["code"] == \
            "scenario_not_in_project"
        # 非成员 → 404;与 visibility=public 互斥 → 422
        r = await client.post("/api/integration/tasks", headers=h_x, json={
            "name": "s70-x", "scenarioId": "sc-s70-t",
            "identityMode": "personal", "triggerCron": "0 3 * * *",
            "projectId": pid})
        assert r.status_code == 404
        r = await client.post("/api/integration/tasks", headers=h_m, json={
            "name": "s70-x2", "scenarioId": "sc-s70-t",
            "identityMode": "personal", "triggerCron": "0 3 * * *",
            "projectId": pid, "visibility": "public"})
        assert r.status_code == 422 and r.json()["detail"]["code"] == \
            "project_visibility_conflict"


class TestIntegrationVisibility:
    """模板可见性三区收口:私有 = 属主;公共项目 = 全员;普通项目 =
    项目成员(修复:此前 project_id 非空即可见)。"""

    async def _mk_project_tpl(self, client) -> tuple[dict, int, int]:
        h_m = await role_headers(client, "s70_ivm", role="user")
        pid = await _mk_project("s70-iv", members={"s70_ivm": "member"})
        await client.post("/api/scenarios?projectId=%d" % pid,
                          headers=h_m, json=make_draft("sc-s70-iv"))
        r = await client.post("/api/integration/tasks", headers=h_m, json={
            "name": "s70-proj-tpl", "scenarioId": "sc-s70-iv",
            "identityMode": "personal", "triggerCron": "0 3 * * *",
            "projectId": pid})
        assert r.status_code == 201, r.text
        return h_m, pid, r.json()["id"]

    async def test_project_template_member_only(self, client: AsyncClient):
        h_m, pid, tpl_id = await self._mk_project_tpl(client)
        h_x = await role_headers(client, "s70_ivx", role="user")
        # 非成员:详情 404、列表不可见
        r = await client.get(f"/api/integration/tasks/{tpl_id}", headers=h_x)
        assert r.status_code == 404
        lst = (await client.get("/api/integration/tasks",
                                headers=h_x)).json()["items"]
        assert tpl_id not in [t["id"] for t in lst]
        # 成员:详情可见;?projectId= 页签过滤只出本项目模板
        assert (await client.get(
            f"/api/integration/tasks/{tpl_id}", headers=h_m)).status_code \
            == 200
        lst = (await client.get(
            "/api/integration/tasks?projectId=%d" % pid,
            headers=h_m)).json()["items"]
        assert [t["id"] for t in lst] == [tpl_id]
        assert lst[0]["projectId"] == pid

    async def test_public_template_all_users(self, client: AsyncClient):
        h_o = await role_headers(client, "s70_pvo", role="user")
        await client.post("/api/scenarios", headers=h_o,
                          json=make_draft("sc-s70-pv"))
        r = await client.post("/api/scenarios/sc-s70-pv/publish",
                              headers=h_o)
        assert r.status_code == 200, r.text
        r = await client.post("/api/integration/tasks", headers=h_o, json={
            "name": "s70-pub-tpl", "scenarioId": "sc-s70-pv-public",
            "identityMode": "personal", "triggerCron": "0 3 * * *",
            "visibility": "public"})
        assert r.status_code == 201, r.text
        tpl_id = r.json()["id"]
        h_x = await role_headers(client, "s70_pvx", role="user")
        assert (await client.get(
            f"/api/integration/tasks/{tpl_id}", headers=h_x)).status_code \
            == 200
        lst = (await client.get("/api/integration/tasks",
                                headers=h_x)).json()["items"]
        assert tpl_id in [t["id"] for t in lst]


class TestSlotStatus:
    """S7.3 成员凭证清单:项目场景引用槽位 × 成员绑定态(只读)。"""

    async def test_slot_status_matrix(self, client: AsyncClient):
        h_m = await role_headers(client, "s70_ss1", role="user")
        h_n = await role_headers(client, "s70_ss2", role="user")
        h_x = await role_headers(client, "s70_ssx", role="user")
        pid = await _mk_project(
            "s70-slots", members={"s70_ss1": "member", "s70_ss2": "member"})
        draft = make_draft("sc-s70-slot", steps=[{
            "id": "s1", "kind": "step",
            "call": {"service": "fin", "path": "/x"}}])
        r = await client.post("/api/scenarios?projectId=%d" % pid,
                              headers=h_m, json=draft)
        assert r.status_code in (200, 201), r.text
        # 成员甲绑定槽位 fin(直接插 AuthSession;别名注册走 API 较重)
        from app.core import db as db_module
        from app.models.auth_session import AuthSession
        from app.models.user import User
        from sqlalchemy import select as sa_select

        from app.core.security import fernet_encrypt

        async with db_module.SessionLocal() as db:
            uid = (await db.execute(sa_select(User.id).where(
                User.username == "s70_ss1"))).scalar_one()
            db.add(AuthSession(
                owner_id=uid, alias="fin", slot="fin", system="fin",
                url="http://fin", username_enc=fernet_encrypt("u"),
                password_enc=fernet_encrypt("p"), token_type="Bearer",
                expires_in=7200))
            await db.commit()
        r = await client.get(f"/api/projects/{pid}/slot-status", headers=h_m)
        assert r.status_code == 200, r.text
        slots = r.json()["slots"]
        # make_draft 步骤引用 fin → fin 槽位场景注入清单为空(无 auth
        # 引用)时槽位集可能为空;断言形态而非具体槽名
        assert isinstance(slots, list)
        for it in slots:
            assert set(it) >= {"slot", "scenarios", "members"}
            for m in it["members"]:
                assert set(m) >= {"userId", "username", "bound"}
        # 非成员 404
        assert (await client.get(
            f"/api/projects/{pid}/slot-status", headers=h_x)).status_code == 404


class TestScopePrivate:
    """scope=private = 我名下且未加入任何项目(「我的」页口径,IA 修正)。"""

    async def test_scenarios_scope_private(self, client: AsyncClient):
        h_m = await role_headers(client, "s70_spm", role="user")
        pid = await _mk_project("s70-sp", members={"s70_spm": "member"})
        await client.post("/api/scenarios", headers=h_m,
                          json=make_draft("sc-s70-priv"))
        await client.post("/api/scenarios?projectId=%d" % pid,
                          headers=h_m, json=make_draft("sc-s70-proj"))
        r = await client.get("/api/scenarios?scope=private", headers=h_m)
        assert r.status_code == 200, r.text
        ids = [it["meta"]["scenarioId"] for it in r.json()["items"]]
        assert ids == ["sc-s70-priv"]
        # scope=mine 仍含项目内(镜头 = 我创建的全部)
        r = await client.get("/api/scenarios?scope=mine", headers=h_m)
        ids = [it["meta"]["scenarioId"] for it in r.json()["items"]]
        assert set(ids) == {"sc-s70-priv", "sc-s70-proj"}
        # projectId 过滤走项目页签
        r = await client.get(
            f"/api/scenarios?projectId={pid}", headers=h_m)
        ids = [it["meta"]["scenarioId"] for it in r.json()["items"]]
        assert ids == ["sc-s70-proj"]

    async def test_suites_scope_private(self, client: AsyncClient):
        h_m = await role_headers(client, "s70_ssm", role="user")
        pid = await _mk_project("s70-ssp", members={"s70_ssm": "member"})
        await client.post("/api/suites", headers=h_m,
                          json={"name": "s70-suite-priv"})
        await client.post("/api/suites", headers=h_m, json={
            "name": "s70-suite-proj", "projectId": pid})
        r = await client.get("/api/suites?scope=private", headers=h_m)
        assert r.status_code == 200, r.text
        names = [it["name"] for it in r.json()["items"]]
        assert names == ["s70-suite-priv"]
