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
    """直插普通项目 + 成员(UPC §20 布景守卫单点:无 admin 自动补
    守夜人 —— 活跃普通项目 ≥1 有效 admin 的库层不变量)。"""
    from tests.helpers import mk_normal_project

    return await mk_normal_project(name, members)


async def _uid(username: str) -> int:
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.user import User

    async with db_module.SessionLocal() as db:
        return (await db.execute(sa_select(User.id).where(
            User.username == username))).scalar_one()


async def _move_scenario_to_project(sid: str, pid: int | None) -> None:
    """场景进区(UPC M2:跨项目移动是专门事务 —— 延迟复合 FK + 方案随迁;
    pid=None = 搬回属主默认私有空间,旧「置空」写法随 NOT NULL 退役)。"""
    from app.core import db as db_module

    async with db_module.SessionLocal() as db:
        from sqlalchemy import select as sa_select
        from sqlalchemy import text as sa_text

        from app.models.composer_run_scheme import ComposerRunScheme
        from app.models.composer_scenario import ComposerScenario
        row = (await db.execute(sa_select(ComposerScenario).where(
            ComposerScenario.scenario_id == sid))).scalar_one()
        target = pid
        if target is None:
            from tests.helpers import default_space_id

            target = await default_space_id(db, row.owner_id)
        await db.execute(sa_text(
            "SET CONSTRAINTS fk_scheme_scenario_zone, "
            "fk_scheme_combo_zone DEFERRED"))
        row.project_id = target
        await db.execute(sa_update_helper(
            ComposerRunScheme, sid, target))
        await db.commit()


def sa_update_helper(model, sid: str, target: int):
    from sqlalchemy import update

    return (update(model).where(model.scenario_id == sid)
            .values(project_id=target))


async def _scenario_row(sid: str):
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario

    async with db_module.SessionLocal() as db:
        return (await db.execute(sa_select(ComposerScenario).where(
            ComposerScenario.scenario_id == sid))).scalar_one_or_none()


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
        # S7.0 + UPC M1:与 GET /projects 同口径 —— 公共置顶(role=None)
        # + 我的普通项目 + 我的默认私有空间(§4;私有空间 role=None,
        # 治理由 owner_id 表达,无成员行)
        assert projects[0]["kind"] == "public"
        assert projects[0]["role"] is None
        # 公共之后按 id 序:默认空间先于普通项目(布景顺序决定)
        rest = projects[1:]
        assert [(p_["kind"], p_["isDefault"]) for p_ in rest] == [
            ("private", True), ("normal", False)]
        normal = next(p_ for p_ in rest if p_["kind"] == "normal")
        assert normal["id"] == pid and normal["role"] == "admin"

        h2 = await role_headers(client, "s11_nobody", role="user")
        # 非成员者只剩公共项目与自己的默认私有空间(不再看见他人项目)
        others = [p_ for p_ in (
            await client.get("/api/auth/me", headers=h2)
        ).json()["projects"] if p_["kind"] != "public"]
        assert [(p_["kind"], p_["isDefault"]) for p_ in others] == [
            ("private", True)]


class TestShadowWrite:
    """S1.3 发布 = 复制:公共副本确定性 id/恒剥离/forked_from;原件恒
    私有;下架(在原件上调)删副本、原件无损。"""

    async def test_publish_creates_copy_unpublish_removes(self, client):
        from app.services.zone import public_project_id

        h = await role_headers(client, "s11_sh", role="user")
        draft = make_draft("sc-s11-sh")
        r = await client.post("/api/scenarios", headers=h, json=draft)
        assert r.status_code in (200, 201), r.text
        from tests.helpers import seed_legacy_users
        await seed_legacy_users("sc-s11-sh", {"acct": {"url": "u"}})
        r = await client.post("/api/scenarios/sc-s11-sh/publish", headers=h)
        assert r.status_code == 200, r.text

        from app.core import db as db_module

        async with db_module.SessionLocal() as db:
            pid = await public_project_id(db)
        copy = await _scenario_row("sc-s11-sh-public")
        assert copy is not None
        assert copy.project_id == pid
        assert copy.forked_from_id == "sc-s11-sh"
        assert not ((copy.payload["definition"].get("config") or {})
                    .get("users")), "公共副本落库即无凭证"
        orig = await _scenario_row("sc-s11-sh")
        # UPC M2:原件留在属主默认私有空间(真实容器;旧「置空」断言退役)
        from app.core import db as _dbm
        from tests.helpers import default_space_id

        async with _dbm.SessionLocal() as _s:
            _home = await default_space_id(_s, orig.owner_id)
        assert orig.project_id == _home
        assert (orig.payload["definition"]["config"]["users"]
                == {"acct": {"url": "u"}}), "原件不动"

        r = await client.post("/api/scenarios/sc-s11-sh/unpublish", headers=h)
        assert r.status_code == 200, r.text
        assert await _scenario_row("sc-s11-sh-public") is None
        orig = await _scenario_row("sc-s11-sh")
        assert (orig.payload["definition"]["config"]["users"]
                == {"acct": {"url": "u"}}), "下架后原件无损"


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


class TestProjectWriteZone:
    """S1.2 写闸区感知:成员可写/可删项目内容;移出创建人与非成员不行
    (表 B write/delete = owner ∨ member ∨ maintainer / +public_admin)。"""

    async def test_member_updates_and_creator_cannot(self, client):
        h_owner = await role_headers(client, "s12_cr", role="user")
        r = await client.post("/api/scenarios", headers=h_owner,
                              json=make_draft("sc-s12-a"))
        assert r.status_code in (200, 201), r.text
        await role_headers(client, "s12_mem", role="user")
        pid = await _mk_project("s12-proj", members={"s12_mem": "member"})
        await _move_scenario_to_project("sc-s12-a", pid)

        # 成员 PUT(全量 draft)→ 200
        h_mem = await role_headers(client, "s12_mem", role="user")
        r = await client.put("/api/scenarios/sc-s12-a", headers=h_mem,
                             json=make_draft("sc-s12-a"))
        assert r.status_code == 200, r.text
        # 移出项目的创建人(读闸即 404)与非成员 404
        r = await client.put("/api/scenarios/sc-s12-a", headers=h_owner,
                             json=make_draft("sc-s12-a"))
        assert r.status_code == 404, r.text

    async def test_member_deletes_project_scenario(self, client):
        """S1-f:普通项目里成员即可删除(删除记入动态流与审计由
        activity/audit 面覆盖,这里钉住权限面)。"""
        h_owner = await role_headers(client, "s12_cr2", role="user")
        r = await client.post("/api/scenarios", headers=h_owner,
                              json=make_draft("sc-s12-b"))
        assert r.status_code in (200, 201), r.text
        await role_headers(client, "s12_mem2", role="user")
        pid = await _mk_project("s12-proj2", members={"s12_mem2": "member"})
        await _move_scenario_to_project("sc-s12-b", pid)
        h_mem = await role_headers(client, "s12_mem2", role="user")
        r = await client.delete("/api/scenarios/sc-s12-b", headers=h_mem)
        assert r.status_code == 204, r.text

    async def test_member_patches_project_suite(self, client):
        h_owner = await role_headers(client, "s12_cr3", role="user")
        await client.post("/api/scenarios", headers=h_owner,
                          json=make_draft("sc-s12-c"))
        r = await client.post("/api/suites", headers=h_owner,
                              json={"name": "s12-suite", "description": ""})
        assert r.status_code == 201, r.text
        suite_id = r.json()["suiteId"]
        # 成员加入项目(场景与 suite 同进项目)
        await role_headers(client, "s12_mem3", role="user")
        pid = await _mk_project("s12-proj3", members={"s12_mem3": "member"})
        await _move_scenario_to_project("sc-s12-c", pid)
        from app.core import db as db_module
        from sqlalchemy import select as sa_select
        from app.models.suite import Suite

        async with db_module.SessionLocal() as db:
            row = (await db.execute(sa_select(Suite).where(
                Suite.id == suite_id))).scalar_one()
            row.project_id = pid
            await db.commit()

        h_mem = await role_headers(client, "s12_mem3", role="user")
        r = await client.patch(f"/api/suites/{suite_id}", headers=h_mem,
                               json={"description": "成员改的"})
        assert r.status_code == 200, r.text
        # 成员列表可见该 suite(zone_read_clause)
        r = await client.get("/api/suites", headers=h_mem)
        assert r.status_code == 200
        assert any(x["suiteId"] == suite_id for x in r.json()["items"])

    async def test_report_definitions_list_zone(self, client):
        """报告定义列表三区:项目定义对成员可见,对路人不可见。"""
        from app.core import db as db_module
        from app.models.report_definition import ReportDefinitionRow

        await role_headers(client, "s12_cr4", role="user")
        await role_headers(client, "s12_mem4", role="user")
        await role_headers(client, "s12_out4", role="user")
        pid = await _mk_project("s12-proj4", members={"s12_mem4": "member"})
        async with db_module.SessionLocal() as db:
            db.add(ReportDefinitionRow(
                name="s12-rd", description="",
                definition={"selection": {}, "projection": []},
                owner_id=await _uid("s12_cr4"), project_id=pid))
            await db.commit()

        h_mem = await role_headers(client, "s12_mem4", role="user")
        r = await client.get("/api/report-definitions", headers=h_mem)
        assert any(d["name"] == "s12-rd" for d in r.json()["items"])
        h_out = await role_headers(client, "s12_out4", role="user")
        r = await client.get("/api/report-definitions", headers=h_out)
        assert not any(d["name"] == "s12-rd" for d in r.json()["items"])

    async def test_publish_copy_run_semantics(self, client):
        """S1.3:发布 = 复制后,原件恒私有可跑(属主);公共副本对
        所有人不可执行(影子期 run 例外已删,表 B run 公共 = —)。"""
        from app.core import db as db_module
        from app.routers._ownership import can_run_scenario
        from app.services.zone import public_project_id

        h = await role_headers(client, "s11_sho", role="user")
        r = await client.post("/api/scenarios", headers=h,
                              json=make_draft("sc-s11-sho"))
        assert r.status_code in (200, 201), r.text
        r = await client.post("/api/scenarios/sc-s11-sho/publish", headers=h)
        assert r.status_code == 200, r.text
        await role_headers(client, "s11_shx", role="user")

        class _U:
            def __init__(self, uid: int):
                self.id = uid

        async with db_module.SessionLocal() as db:
            orig = await _scenario_row("sc-s11-sho")
            copy = await _scenario_row("sc-s11-sho-public")
            pid = await public_project_id(db)
            # 原件:属主可跑,路人不可
            assert await can_run_scenario(
                db, _U(await _uid("s11_sho")), scenario_id="sc-s11-sho",
                owner_id=orig.owner_id, project_id=None) is True
            assert await can_run_scenario(
                db, _U(await _uid("s11_shx")), scenario_id="sc-s11-sho",
                owner_id=orig.owner_id, project_id=None) is False
            # 公共副本:属主与路人都不开执行(公共 = 副本,无例外)
            assert await can_run_scenario(
                db, _U(await _uid("s11_sho")), scenario_id="sc-s11-sho-public",
                owner_id=copy.owner_id, project_id=pid) is False
            assert await can_run_scenario(
                db, _U(await _uid("s11_shx")), scenario_id="sc-s11-sho-public",
                owner_id=copy.owner_id, project_id=pid) is False


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


class TestProjectWriteZone:
    """S1.2 写闸区感知:成员可写/可删项目内容;移出创建人与非成员不行
    (表 B write/delete = owner ∨ member ∨ maintainer / +public_admin)。"""

    async def test_member_updates_and_creator_cannot(self, client):
        h_owner = await role_headers(client, "s12_cr", role="user")
        r = await client.post("/api/scenarios", headers=h_owner,
                              json=make_draft("sc-s12-a"))
        assert r.status_code in (200, 201), r.text
        await role_headers(client, "s12_mem", role="user")
        pid = await _mk_project("s12-proj", members={"s12_mem": "member"})
        await _move_scenario_to_project("sc-s12-a", pid)

        # 成员 PUT(全量 draft)→ 200
        h_mem = await role_headers(client, "s12_mem", role="user")
        r = await client.put("/api/scenarios/sc-s12-a", headers=h_mem,
                             json=make_draft("sc-s12-a"))
        assert r.status_code == 200, r.text
        # 移出项目的创建人(读闸即 404)与非成员 404
        r = await client.put("/api/scenarios/sc-s12-a", headers=h_owner,
                             json=make_draft("sc-s12-a"))
        assert r.status_code == 404, r.text

    async def test_member_deletes_project_scenario(self, client):
        """S1-f:普通项目里成员即可删除(删除记入动态流与审计由
        activity/audit 面覆盖,这里钉住权限面)。"""
        h_owner = await role_headers(client, "s12_cr2", role="user")
        r = await client.post("/api/scenarios", headers=h_owner,
                              json=make_draft("sc-s12-b"))
        assert r.status_code in (200, 201), r.text
        await role_headers(client, "s12_mem2", role="user")
        pid = await _mk_project("s12-proj2", members={"s12_mem2": "member"})
        await _move_scenario_to_project("sc-s12-b", pid)
        h_mem = await role_headers(client, "s12_mem2", role="user")
        r = await client.delete("/api/scenarios/sc-s12-b", headers=h_mem)
        assert r.status_code == 204, r.text

    async def test_member_patches_project_suite(self, client):
        h_owner = await role_headers(client, "s12_cr3", role="user")
        await client.post("/api/scenarios", headers=h_owner,
                          json=make_draft("sc-s12-c"))
        r = await client.post("/api/suites", headers=h_owner,
                              json={"name": "s12-suite", "description": ""})
        assert r.status_code == 201, r.text
        suite_id = r.json()["suiteId"]
        # 成员加入项目(场景与 suite 同进项目)
        await role_headers(client, "s12_mem3", role="user")
        pid = await _mk_project("s12-proj3", members={"s12_mem3": "member"})
        await _move_scenario_to_project("sc-s12-c", pid)
        from app.core import db as db_module
        from sqlalchemy import select as sa_select
        from app.models.suite import Suite

        async with db_module.SessionLocal() as db:
            row = (await db.execute(sa_select(Suite).where(
                Suite.id == suite_id))).scalar_one()
            row.project_id = pid
            await db.commit()

        h_mem = await role_headers(client, "s12_mem3", role="user")
        r = await client.patch(f"/api/suites/{suite_id}", headers=h_mem,
                               json={"description": "成员改的"})
        assert r.status_code == 200, r.text
        # 成员列表可见该 suite(zone_read_clause)
        r = await client.get("/api/suites", headers=h_mem)
        assert r.status_code == 200
        assert any(x["suiteId"] == suite_id for x in r.json()["items"])

    async def test_report_definitions_list_zone(self, client):
        """报告定义列表三区:项目定义对成员可见,对路人不可见。"""
        from app.core import db as db_module
        from app.models.report_definition import ReportDefinitionRow

        await role_headers(client, "s12_cr4", role="user")
        await role_headers(client, "s12_mem4", role="user")
        await role_headers(client, "s12_out4", role="user")
        pid = await _mk_project("s12-proj4", members={"s12_mem4": "member"})
        async with db_module.SessionLocal() as db:
            db.add(ReportDefinitionRow(
                name="s12-rd", description="",
                definition={"selection": {}, "projection": []},
                owner_id=await _uid("s12_cr4"), project_id=pid))
            await db.commit()

        h_mem = await role_headers(client, "s12_mem4", role="user")
        r = await client.get("/api/report-definitions", headers=h_mem)
        assert any(d["name"] == "s12-rd" for d in r.json()["items"])
        h_out = await role_headers(client, "s12_out4", role="user")
        r = await client.get("/api/report-definitions", headers=h_out)
        assert not any(d["name"] == "s12-rd" for d in r.json()["items"])


class TestS13PublishSemantics:
    """S1.3 发布新语义端点验收:重发布同 id 刷新、迁移行下架保护、
    suite 深拷贝两闸、集成公开两闸。"""

    async def test_republish_same_id_refreshes_copy(self, client):
        h = await role_headers(client, "s13_rp", role="user")
        r = await client.post("/api/scenarios", headers=h,
                              json=make_draft("sc-s13-rp"))
        assert r.status_code in (200, 201), r.text
        assert (await client.post(
            "/api/scenarios/sc-s13-rp/publish", headers=h)).status_code == 200

        # 原件改名后重发布:同副本 id,内容刷新
        draft2 = make_draft("sc-s13-rp")
        draft2["definition"]["meta"]["name"] = "改名后"
        r = await client.put("/api/scenarios/sc-s13-rp", headers=h,
                             json=draft2)
        assert r.status_code == 200, r.text
        r = await client.post("/api/scenarios/sc-s13-rp/publish", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["meta"]["scenarioId"] == "sc-s13-rp-public"
        assert r.json()["meta"]["name"] == "改名后"
        assert await _scenario_row("sc-s13-rp-public") is not None

    async def test_unpublish_migrated_original_409(self, client):
        """存量迁入的无原件公共行(forked_from_id 空):下架 409,引导
        先复制到私有区留底。"""
        from app.core import db as db_module
        from app.services.zone import apply_public, public_project_id

        h = await role_headers(client, "s13_mg", role="user")
        r = await client.post("/api/scenarios", headers=h,
                              json=make_draft("sc-s13-mg"))
        assert r.status_code in (200, 201), r.text
        from sqlalchemy import select as sa_select

        from app.models.composer_scenario import ComposerScenario
        from sqlalchemy import text as sa_text

        from app.models.composer_run_scheme import ComposerRunScheme
        from sqlalchemy import update as sa_upd

        async with db_module.SessionLocal() as db:
            row = (await db.execute(sa_select(ComposerScenario).where(
                ComposerScenario.scenario_id == "sc-s13-mg"))).scalar_one()
            _pub = await public_project_id(db)
            # 模拟 0040 迁入(§20.2:方案随迁 + 延迟复合 FK)
            await db.execute(sa_text(
                "SET CONSTRAINTS fk_scheme_scenario_zone, "
                "fk_scheme_combo_zone DEFERRED"))
            apply_public(row, _pub)
            await db.execute(sa_upd(ComposerRunScheme).where(
                ComposerRunScheme.scenario_id == "sc-s13-mg"
            ).values(project_id=_pub))
            await db.commit()

        r = await client.post("/api/scenarios/sc-s13-mg/unpublish", headers=h)
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "public_copy_is_original"

    async def test_suite_publish_requires_public_members(self, client):
        h = await role_headers(client, "s13_sq", role="user")
        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-s13-sq"))
        r = await client.post("/api/suites", headers=h,
                              json={"name": "s13-suite", "description": ""})
        suite_id = r.json()["suiteId"]
        r = await client.post(f"/api/suites/{suite_id}/members", headers=h,
                              json={"scenarioIds": ["sc-s13-sq"],})
        assert r.status_code == 200, r.text
        # 成员未发布 → 422 suite_member_not_public(不再级联代发布)
        r = await client.post(f"/api/suites/{suite_id}/publish", headers=h)
        assert r.status_code == 422, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "suite_member_not_public"
        assert detail["pendingMembers"] == ["sc-s13-sq"]

    async def test_suite_deep_copy_members_point_to_public_copies(
            self, client):
        from app.core import db as db_module
        from sqlalchemy import select as sa_select

        from app.models.suite import Suite, SuiteMember

        h = await role_headers(client, "s13_sp", role="user")
        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-s13-sp"))
        r = await client.post("/api/suites", headers=h,
                              json={"name": "s13-suite2", "description": ""})
        suite_id = r.json()["suiteId"]
        await client.post(f"/api/suites/{suite_id}/members", headers=h,
                          json={"scenarioIds": ["sc-s13-sp"],})
        assert (await client.post(
            "/api/scenarios/sc-s13-sp/publish", headers=h)).status_code == 200
        r = await client.post(f"/api/suites/{suite_id}/publish", headers=h)
        assert r.status_code == 200, r.text
        copy_id = r.json()["suiteId"]
        async with db_module.SessionLocal() as db:
            copy = (await db.execute(sa_select(Suite).where(
                Suite.id == copy_id))).scalar_one()
            assert copy.project_id is not None and copy.forked_from_id == suite_id
            members = (await db.execute(sa_select(SuiteMember).where(
                SuiteMember.suite_id == copy_id))).scalars().all()
            assert [m.scenario_id for m in members] == ["sc-s13-sp-public"]
        # 原件套件下架 → 副本删除,成员场景公共副本独立保留
        r = await client.delete(f"/api/suites/{suite_id}/publish", headers=h)
        assert r.status_code == 200, r.text
        async with db_module.SessionLocal() as db:
            assert (await db.execute(sa_select(Suite).where(
                Suite.id == copy_id))).scalar_one_or_none() is None
        assert await _scenario_row("sc-s13-sp-public") is not None

    async def test_integration_publicize_requires_public_scenario(
            self, client):
        """模板公开(创建与更新)要求引用场景已在公共项目,否则 422。"""
        h = await role_headers(client, "s13_ig", role="user")
        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-s13-ig"))
        body = {"name": "探针", "scenarioId": "sc-s13-ig",
                "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
                "visibility": "public"}
        r = await client.post("/api/integration/tasks", headers=h, json=body)
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "scenario_not_public"

        # 私有创建后切公开同样 422
        body["visibility"] = "private"
        r = await client.post("/api/integration/tasks", headers=h, json=body)
        assert r.status_code == 201, r.text
        tid = r.json()["id"]
        r = await client.patch(f"/api/integration/tasks/{tid}", headers=h,
                               json={"visibility": "public"})
        assert r.status_code in (404, 422), r.text
        if r.status_code == 422:
            assert r.json()["detail"]["code"] == "scenario_not_public"


class TestPublicProjectMemberGuard:
    """B1 收口(2026-11-22):公共项目三成员端点补 public_project_protected
    守卫 —— can_run_scenario 项目分支纯查成员表,admin 给公共项目落成员
    行即可执行公共副本,击穿「公共副本对所有人不可执行」不变量。"""

    async def _public_project(self) -> int:
        """取 0040 迁移种子的公共项目(uq_projects_public_kind:全库至多
        一个公共项目,测试 schema 由迁移自动种子)。"""
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.project import Project

        async with db_module.SessionLocal() as db:
            return (await db.execute(sa_select(Project.id).where(
                Project.kind == "public"))).scalar_one()

    async def test_add_member_public_409(self, client: AsyncClient):
        h = await role_headers(client, "s11_pubadm", role="admin")
        pid = await self._public_project()
        r = await client.post(f"/api/projects/{pid}/members", headers=h,
                              json={"userId": 999999, "role": "member"})
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "project_kind_no_members"
        # 守卫先行:不存在的用户也到不了 member_invalid 校验
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.project import ProjectMember

        async with db_module.SessionLocal() as db:
            rows = (await db.execute(sa_select(ProjectMember).where(
                ProjectMember.project_id == pid))).scalars().all()
            assert rows == []

    async def test_patch_and_remove_member_public_409(
            self, client: AsyncClient):
        h = await role_headers(client, "s11_pubadm2", role="admin")
        pid = await self._public_project()
        r = await client.patch(f"/api/projects/{pid}/members/1", headers=h,
                               json={"role": "member"})
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "project_kind_no_members"


async def test_public_member_row_physically_rejected(client: AsyncClient):
    """UPC §20 收口:private/public 不落成员行由**库层触发器**钉死
    (0067 project_member_kind_guard)—— B1 窗口期的「API 补救通道」
    (remove_member 对公共放行删行)随触发器落地失去前提:残留行物理上
    无法产生,不再需要补救通道。负向:直插被拒,公共项目成员行恒空。"""
    import pytest
    from sqlalchemy import select as sa_select
    from sqlalchemy.exc import IntegrityError

    from app.core import db as db_module
    from app.models.project import Project, ProjectMember
    from app.models.user import User

    await role_headers(client, "s11_pubadm3", role="admin")
    async with db_module.SessionLocal() as db:
        pid = (await db.execute(sa_select(Project.id).where(
            Project.kind == "public"))).scalar_one()
        uid = (await db.execute(sa_select(User.id).where(
            User.username == "s11_pubadm3"))).scalar_one()
        with pytest.raises(IntegrityError):
            db.add(ProjectMember(project_id=pid, user_id=uid, role="member"))
            await db.commit()
        await db.rollback()
        rows = (await db.execute(sa_select(ProjectMember).where(
            ProjectMember.project_id == pid))).scalars().all()
        assert rows == []   # 不变量:公共项目成员行恒空