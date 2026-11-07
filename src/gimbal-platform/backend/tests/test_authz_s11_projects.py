"""M2a S1.1 项目维度授权:区谓词落点 / 执行可见 / me.projects / 影子写 / D5 闸。

表 B 的区谓词全叉积在 test_authz_matrix_b(快照推导);这里测**落点**:
端点与查询真的走了新谓词,以及 D1 关键回归(移出项目的创建人)。
S1.2 才做写面 132 处归类 —— 本文件不测项目写面端点(写闸此刻仍走
属主单判,S1.2 收编)。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import make_draft, role_headers


async def _mk_project(name: str, *, members: dict[str, str]) -> int:
    """直插普通项目 + 成员 {username: role};返回项目 id(普通项目
    不经 API 创建 —— S1.4 才有项目管理端点)。"""
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


async def _uid(username: str) -> int:
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.user import User

    async with db_module.SessionLocal() as db:
        return (await db.execute(sa_select(User.id).where(
            User.username == username))).scalar_one()


async def _move_scenario_to_project(sid: str, pid: int | None) -> None:
    """场景进区(单会话内 load→set→commit;游离实例的属性改动不落库)。"""
    from app.core import db as db_module

    async with db_module.SessionLocal() as db:
        from sqlalchemy import select as sa_select

        from app.models.composer_scenario import ComposerScenario
        row = (await db.execute(sa_select(ComposerScenario).where(
            ComposerScenario.scenario_id == sid))).scalar_one()
        row.project_id = pid
        await db.commit()


async def _scenario_row(sid: str):
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario

    async with db_module.SessionLocal() as db:
        return (await db.execute(sa_select(ComposerScenario).where(
            ComposerScenario.scenario_id == sid))).scalar_one()


class TestProjectReadZone:
    """表 B scenario.read 落点:member 可读普通项目场景;非成员与
    移出项目的创建人(D1 回归)404;列表跟随 visibility_clause。"""

    async def test_member_reads_project_scenario(self, client: AsyncClient):
        h_owner = await role_headers(client, "s11_cr", role="user")
        r = await client.post("/api/scenarios", headers=h_owner,
                              json=make_draft("sc-s11-a"))
        assert r.status_code in (200, 201), r.text
        # 成员用户先注册,再建项目(创建人**不是**成员 = D1 形态)
        await role_headers(client, "s11_mem", role="user")
        pid = await _mk_project(
            "s11-proj", members={"s11_mem": "member"})

        # 进普通项目(影子:visibility 保持 private)
        await _move_scenario_to_project("sc-s11-a", pid)

        # 项目成员可读
        h_mem = await role_headers(client, "s11_mem", role="user")
        r = await client.get("/api/scenarios/sc-s11-a", headers=h_mem)
        assert r.status_code == 200, r.text
        # 成员列表可见(visibility_clause 第三支)
        r = await client.get("/api/scenarios", headers=h_mem)
        assert r.status_code == 200
        assert any(i["meta"]["scenarioId"] == "sc-s11-a"
                   for i in r.json()["items"]), "项目场景应出现在成员列表"

    async def test_nonmember_and_removed_creator_get_404(
            self, client: AsyncClient):
        """非成员 404;移出项目的创建人同样 404(D1:project_id 非空时
        属主身份不给任何权限 —— 全动词失效的关键回归)。"""
        h_owner = await role_headers(client, "s11_cr2", role="user")
        r = await client.post("/api/scenarios", headers=h_owner,
                              json=make_draft("sc-s11-b"))
        assert r.status_code in (200, 201), r.text
        await role_headers(client, "s11_mem2", role="user")
        pid = await _mk_project("s11-proj2", members={"s11_mem2": "member"})
        await _move_scenario_to_project("sc-s11-b", pid)

        # 非成员路人
        h_other = await role_headers(client, "s11_pass", role="user")
        assert (await client.get(
            "/api/scenarios/sc-s11-b", headers=h_other)).status_code == 404
        # 创建人(未入项目)
        assert (await client.get(
            "/api/scenarios/sc-s11-b", headers=h_owner)).status_code == 404
        # admin 也不旁路(W3 口径不变;公共治理只发生在公共项目)
        h_adm = await role_headers(client, "s11_adm", role="admin")
        assert (await client.get(
            "/api/scenarios/sc-s11-b", headers=h_adm)).status_code == 404

    async def test_can_run_project_scenario_member_only(self, client):
        """表 B scenario.run 落点:member 可跑;创建人(移出)与
        非成员不可跑(公共项目不开执行的反面在 strips 套件)。"""
        from app.core import db as db_module
        from app.core.deps import get_current_user  # noqa: F401 仅为文档性引用
        from app.routers._ownership import can_run_scenario

        h_owner = await role_headers(client, "s11_cr3", role="user")
        r = await client.post("/api/scenarios", headers=h_owner,
                              json=make_draft("sc-s11-c"))
        assert r.status_code in (200, 201), r.text
        await role_headers(client, "s11_mem3", role="user")
        await role_headers(client, "s11_pass3", role="user")
        pid = await _mk_project("s11-proj3", members={"s11_mem3": "member"})
        await _move_scenario_to_project("sc-s11-c", pid)

        class _U:
            def __init__(self, uid: int):
                self.id = uid

        async with db_module.SessionLocal() as db:
            row = await _scenario_row("sc-s11-c")
            assert await can_run_scenario(
                db, _U(await _uid("s11_mem3")), scenario_id="sc-s11-c",
                owner_id=row.owner_id, project_id=pid) is True
            assert await can_run_scenario(
                db, _U(await _uid("s11_cr3")), scenario_id="sc-s11-c",
                owner_id=row.owner_id, project_id=pid) is False
            assert await can_run_scenario(
                db, _U(await _uid("s11_pass3")), scenario_id="sc-s11-c",
                owner_id=row.owner_id, project_id=pid) is False


class TestExecutionProjectVisibility:
    """can_view_execution 项目分支:成员可见项目执行;移出后不可见;
    私有执行(快照空)仍只有发起人。"""

    async def _mk_exec(self, *, owner: str, project_id: int | None) -> int:
        from app.core import db as db_module
        from app.models.execution import Execution

        async with db_module.SessionLocal() as db:
            ex = Execution(scenario_id="sc-s11-x",
                           owner_id=await _uid(owner))
            ex.project_id = project_id
            db.add(ex)
            await db.commit()
            return ex.id

    async def test_member_sees_project_execution(self, client: AsyncClient):
        await role_headers(client, "s11_run", role="user")     # 发起人
        await role_headers(client, "s11_memb", role="user")    # 成员
        await role_headers(client, "s11_outs", role="user")    # 路人
        pid = await _mk_project("s11-projx",
                                members={"s11_memb": "member"})
        ex_id = await self._mk_exec(owner="s11_run", project_id=pid)

        h_mem = await role_headers(client, "s11_memb", role="user")
        r = await client.get(f"/api/executions/{ex_id}", headers=h_mem)
        assert r.status_code == 200, r.text
        # 列表也含项目执行
        r = await client.get("/api/executions", headers=h_mem)
        assert any(e["id"] == ex_id for e in r.json()["items"])

        # 路人 404;发起人自己 200
        h_out = await role_headers(client, "s11_outs", role="user")
        assert (await client.get(
            f"/api/executions/{ex_id}", headers=h_out)).status_code == 404
        h_run = await role_headers(client, "s11_run", role="user")
        assert (await client.get(
            f"/api/executions/{ex_id}", headers=h_run)).status_code == 200

    async def test_removed_member_loses_execution_view(
            self, client: AsyncClient):
        from sqlalchemy import delete as sa_delete

        from app.core import db as db_module
        from app.models.project import ProjectMember

        await role_headers(client, "s11_run2", role="user")
        await role_headers(client, "s11_memb2", role="user")
        pid = await _mk_project("s11-projy",
                                members={"s11_memb2": "member"})
        ex_id = await self._mk_exec(owner="s11_run2", project_id=pid)
        h_mem = await role_headers(client, "s11_memb2", role="user")
        assert (await client.get(
            f"/api/executions/{ex_id}", headers=h_mem)).status_code == 200
        # 移出项目 → 不可见(404)
        async with db_module.SessionLocal() as db:
            await db.execute(sa_delete(ProjectMember).where(
                ProjectMember.project_id == pid,
                ProjectMember.user_id == await _uid("s11_memb2")))
            await db.commit()
        assert (await client.get(
            f"/api/executions/{ex_id}", headers=h_mem)).status_code == 404

    async def test_private_execution_owner_only(self, client: AsyncClient):
        await role_headers(client, "s11_run3", role="user")
        await role_headers(client, "s11_memb3", role="user")
        await _mk_project("s11-projz", members={"s11_memb3": "member"})
        ex_id = await self._mk_exec(owner="s11_run3", project_id=None)
        h_mem = await role_headers(client, "s11_memb3", role="user")
        assert (await client.get(
            f"/api/executions/{ex_id}", headers=h_mem)).status_code == 404
        h_run = await role_headers(client, "s11_run3", role="user")
        assert (await client.get(
            f"/api/executions/{ex_id}", headers=h_run)).status_code == 200


class TestMeProjects:
    """/auth/me.projects:我所在的普通项目(角色来自成员行)。"""

    async def test_projects_listing(self, client: AsyncClient):
        await role_headers(client, "s11_pu", role="user")
        await role_headers(client, "s11_nobody", role="user")
        pid = await _mk_project(
            "s11-me-proj", members={"s11_pu": "admin"})

        h = await role_headers(client, "s11_pu", role="user")
        r = await client.get("/api/auth/me", headers=h)
        assert r.status_code == 200, r.text
        projects = r.json()["projects"]
        assert projects == [{"id": pid, "name": "s11-me-proj",
                             "kind": "normal", "role": "admin"}]

        h2 = await role_headers(client, "s11_nobody", role="user")
        assert (await client.get("/api/auth/me", headers=h2)
                ).json()["projects"] == []


class TestShadowWrite:
    """影子不变式:发布/下架同步翻转 project_id(0041 回填的运行时面)。"""

    async def test_publish_unpublish_flips_project(self, client: AsyncClient):
        from app.services.zone import public_project_id

        h = await role_headers(client, "s11_sh", role="user")
        r = await client.post("/api/scenarios", headers=h,
                              json=make_draft("sc-s11-sh"))
        assert r.status_code in (200, 201), r.text
        r = await client.post("/api/scenarios/sc-s11-sh/publish", headers=h)
        assert r.status_code == 200, r.text

        from app.core import db as db_module

        async with db_module.SessionLocal() as db:
            pid = await public_project_id(db)
        row = await _scenario_row("sc-s11-sh")
        assert row.visibility == "public" and row.project_id == pid

        r = await client.post(
            "/api/scenarios/sc-s11-sh/unpublish", headers=h)
        assert r.status_code == 200, r.text
        row = await _scenario_row("sc-s11-sh")
        assert row.visibility == "private" and row.project_id is None


class TestD5GateProjectScenarios:
    """D5 闸升级(project_id IS NOT NULL):普通项目场景可被批次代改
    (「S1 后含项目场景」);私有场景照旧 409(test_authz_wrapup 已覆盖)。"""

    async def test_batch_op_on_project_scenario(self, client: AsyncClient):
        h_owner = await role_headers(client, "s11_bcr", role="user")
        r = await client.post("/api/scenarios", headers=h_owner,
                              json=make_draft("sc-s11-d5"))
        assert r.status_code in (200, 201), r.text
        await role_headers(client, "s11_bmem", role="user")
        pid = await _mk_project("s11-projd5",
                                members={"s11_bmem": "member"})
        await _move_scenario_to_project("sc-s11-d5", pid)

        from tests.test_authz_wrapup import _open_carry_batch

        h_adm = await role_headers(client, "s11_badm", role="admin")
        bid = await _open_carry_batch(client, h_adm)
        r = await client.post(f"/api/adaptations/batches/{bid}/ops",
                              headers=h_adm,
                              json={"opType": "renameField",
                                    "scenarioId": "sc-s11-d5",
                                    "payload": {"from": "$.a", "to": "$.b"}})
        assert r.status_code == 201, r.text
