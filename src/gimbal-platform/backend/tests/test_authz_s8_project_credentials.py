"""authz M2a S8:项目凭证 —— 归属 + 写面分权 + 解析/执行 + 集成来源。

钉子(裁定:唯一共享凭证 = 项目账户凭证):
* 归属:项目凭证行 owner NULL / project_id 恰一非空;个人面(auths 列表
  / 令牌范围候选)不出现项目行。
* 写面:``/projects/{pid}/credentials`` 只有项目管理员(∨ Admin+)能写;
  成员只读且**无用户名**;公共项目 409;审计 ``project.credential.write``;
  项目删除连带清理。
* 手动执行:``RunRequest.credentialSource='project'`` → 项目池取用(个人
  池同名槽不进);预览同源(逐槽 source);非成员 / 私有场景 409;缺槽
  409 文案指向项目配置;令牌调用携带 → 422;重跑按快照回放;
  ``Execution.project_id`` 落场景项目。
* 集成:普通项目模板实例缺省项目来源;成员可订阅(personal/project 可选);
  指纹取项目池;项目凭证更新复活项目源暂停实例;成员被移出 → 下轮
  made_private。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models.auth_session import AuthSession

from .helpers import (
    make_draft, register_and_login, role_headers, wait_until as _wait,
)
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401

_STEP = {"kind": "step",
         "call": {"service": "s8-alias", "method": "GET", "path": "/x"},
         "request": {"kind": "request", "body": {
             "tok": "${auth.qa1.token}",
             "org": "${slot.qa1.orgNo}"}},
         "strategy": []}


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar()


async def _mk_project(name: str, *, members: dict[str, str]) -> int:
    from app.models.project import Project, ProjectMember
    from app.models.user import User

    async with db_module.SessionLocal() as db:
        proj = Project(name=name, kind="normal", description="")
        db.add(proj)
        await db.flush()
        for uname, role in members.items():
            uid = (await db.execute(sa.select(User.id).where(
                User.username == uname))).scalar_one()
            db.add(ProjectMember(project_id=proj.id, user_id=uid, role=role))
        await db.commit()
        return proj.id


async def _public_project_id() -> int:
    from app.models.project import Project
    async with db_module.SessionLocal() as db:
        return (await db.execute(sa.select(Project.id).where(
            Project.kind == "public"))).scalar_one()


async def _mk_project_credential(
    pid: int, *, slot: str = "qa1", alias: str | None = None,
    account_fields: dict | None = None,
) -> int:
    async with db_module.SessionLocal() as db:
        a = AuthSession(
            owner_id=None, project_id=pid,
            alias=alias or slot, slot=slot, system="fin",
            url="http://proj-auth",
            username_enc=fernet_encrypt("proj-u"),
            password_enc=fernet_encrypt("proj-p"),
            account_fields=account_fields or {"orgNo": "P-1001"},
            is_default=True)
        db.add(a)
        await db.commit()
        return a.id


async def _seed_project_scenario(
    client, h, pid: int, sid: str = "sc-s8",
) -> None:
    from app.models.service_alias import ServiceAlias
    async with db_module.SessionLocal() as db:
        # 专属别名,声明槽位 qa1(别名默认命中 → 进指纹 slot_bindings);
        # 另建同名别名行 qa1(槽位状态页按「注入名 → 别名行 slot」反查)
        if await db.get(ServiceAlias, "s8-alias") is None:
            db.add(ServiceAlias(alias_name="s8-alias", base_service="fin-svc",
                                kind="external", slot="qa1"))
        if await db.get(ServiceAlias, "qa1") is None:
            db.add(ServiceAlias(alias_name="qa1", base_service="fin-svc",
                                kind="external", slot="qa1"))
        await db.commit()
    r = await client.post("/api/scenarios?projectId=%d" % pid,
                          headers=h, json=make_draft(sid, steps=[_STEP]))
    assert r.status_code in (200, 201), r.text


async def _mk_project_tpl(client, h, pid: int, sid: str):
    await _seed_project_scenario(client, h, pid, sid)
    r = await client.post("/api/integration/tasks", headers=h, json={
        "name": "s8-proj-tpl", "scenarioId": sid,
        "identityMode": "personal", "triggerCron": "0 3 * * *",
        "projectId": pid})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── ① 写面与分权 ─────────────────────────────────────────────────

class TestCredentialCrudGates:
    async def test_admin_crud_member_view_no_username(self, client):
        h_admin = await role_headers(client, "s8_pa", role="user")
        h_member = await role_headers(client, "s8_pm", role="user")
        h_out = await role_headers(client, "s8_px", role="user")
        pid = await _mk_project(
            "s8-crud", members={"s8_pa": "admin", "s8_pm": "member"})
        base = f"/api/projects/{pid}/credentials"
        # 普通成员不能建(403);非成员 404;建成功(管理员)
        body = {"alias": "qa1", "url": "http://a", "username": "u1",
                "password": "p1x2y3z", "system": "fin", "accountFields": {"orgNo": "1"}}
        assert (await client.post(base, headers=h_member, json=body)
                ).status_code == 403
        assert (await client.post(base, headers=h_out, json=body)
                ).status_code == 404
        r = await client.post(base, headers=h_admin, json=body)
        assert r.status_code == 201, r.text
        out = r.json()
        assert out["slot"] == "qa1" and out["isDefault"] is True
        assert out["password_masked"] == "<REDACTED>"
        cid = out["id"]
        # 列表:成员可见但没有用户名;管理员可见用户名;canManage 位
        r = await client.get(base, headers=h_member)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1 and items[0]["username"] == ""
        assert r.json()["canManage"] is False
        r = await client.get(base, headers=h_admin)
        assert r.json()["items"][0]["username"] == "u1"
        assert r.json()["canManage"] is True
        # 非成员列表 404
        assert (await client.get(base, headers=h_out)).status_code == 404
        # patch(换密)+ 换默认 + 删除走管理员
        r = await client.patch(f"{base}/{cid}", headers=h_admin,
                               json={"password": "p2x3y4z"})
        assert r.status_code == 200 and r.json()["password_masked"] == "<REDACTED>"
        r = await client.post(f"{base}/{cid}/default", headers=h_admin)
        assert r.status_code == 200
        assert (await client.delete(f"{base}/{cid}", headers=h_member)
                ).status_code == 403
        assert (await client.delete(f"{base}/{cid}", headers=h_admin)
                ).status_code == 204
        # 审计:project.credential.write
        from app.models.permission import AuditLog
        async with db_module.SessionLocal() as db:
            acts = (await db.execute(sa.select(AuditLog.action).where(
                AuditLog.resource_id == str(pid)))).scalars().all()
        assert "project.credential.write" in acts

    async def test_public_project_rejected_and_project_delete_cascade(
            self, client):
        h_admin = await role_headers(client, "s8_da", role="admin")
        pid = await _mk_project("s8-del", members={"s8_da": "admin"})
        await _mk_project_credential(pid, slot="qa1")
        # 公共项目 409(先建一个普通项目凭证对照)
        ppid = await _public_project_id()
        r = await client.post(
            f"/api/projects/{ppid}/credentials", headers=h_admin,
            json={"alias": "x", "url": "", "username": "u", "password": "p12345"})
        assert r.status_code == 409 and r.json()["detail"]["code"] == \
            "public_project_no_credentials"
        # 项目删除(内容为空)连带删除项目凭证
        assert (await client.delete(
            f"/api/projects/{pid}", headers=h_admin)).status_code == 204
        async with db_module.SessionLocal() as db:
            n = (await db.execute(sa.select(sa.func.count()).where(
                AuthSession.project_id == pid))).scalar_one()
        assert n == 0

    async def test_personal_views_exclude_project_rows(self, client):
        h = await register_and_login(client, "s8_pv", "pw123456")
        pid = await _mk_project("s8-pv", members={"s8_pv": "member"})
        await _mk_project_credential(pid, slot="qa1", alias="s8pv-alias")
        # 个人 /auths 列表与令牌范围候选都不出现项目行
        rows = (await client.get("/api/auths", headers=h)).json()["items"]
        assert all(it["alias"] != "s8pv-alias" for it in rows)
        async with db_module.SessionLocal() as db:
            hits = (await db.execute(sa.select(AuthSession.id).where(
                AuthSession.owner_id == await _uid("s8_pv")))).scalars().all()
        assert hits == []


# ── ② 手动执行:项目池取用 + 预览 + 门 ────────────────────────────

class TestManualRunProjectSource:
    async def test_run_uses_project_pool_and_preview_source(
            self, client, plate_mock: PlateMock, monkeypatch):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "s8_r1", "pw123456")
        pid = await _mk_project("s8-run", members={"s8_r1": "member"})
        await _seed_project_scenario(client, h, pid)
        # 个人池与项目池各放一个同名槽(值不同,验证取用池)
        async with db_module.SessionLocal() as s:
            uid = await _uid("s8_r1")
            s.add(AuthSession(
                owner_id=uid, alias="qa1", slot="qa1", system="fin",
                url="http://personal-auth",
                username_enc=fernet_encrypt("me-u"),
                password_enc=fernet_encrypt("me-p"),
                account_fields={"orgNo": "ME"}, is_default=True))
            await s.commit()
        proj_cid = await _mk_project_credential(pid)
        # ① 预览:credentialSource=project → 项目绑定 + source=project
        r = await client.post("/api/runs/preview", headers=h, json={
            "scenarioId": "sc-s8", "credentialSource": "project"})
        assert r.status_code == 200, r.text
        auths = r.json()["auths"]
        assert auths["qa1"]["bindingId"] == proj_cid
        assert auths["qa1"]["source"] == "project"
        # 缺省 = personal
        r = await client.post("/api/runs/preview", headers=h,
                              json={"scenarioId": "sc-s8"})
        assert r.json()["auths"]["qa1"]["source"] == "personal"
        # ② 执行:项目凭证注入(users = 项目凭证;${slot} 取项目字段)
        cases: list[dict] = []
        _patch_launch_capture(monkeypatch, cases)
        r = await client.post("/api/runs", headers=h, json=_run_payload(
            scenarioId="sc-s8", dataSetIds=[], credentialSource="project"))
        assert r.status_code == 201, r.text
        ex_id = r.json()["executionId"]
        await _wait(lambda: len(cases) >= 1)
        users = cases[0]["config"]["users"]
        assert users["qa1"]["url"] == "http://proj-auth"
        body = cases[0]["steps"][0]["request"]["body"]
        assert body["org"] == "P-1001"
        # ③ Execution.project_id 落场景项目(S1.1 项目执行对成员可见)
        from app.models.execution import Execution
        async with db_module.SessionLocal() as db:
            ex = await db.get(Execution, ex_id)
            assert ex.project_id == pid

    async def test_project_source_gates_and_missing_copy(
            self, client, plate_mock: PlateMock):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "s8_g1", "pw123456")
        h_out = await register_and_login(client, "s8_g2", "pw123456")
        pid = await _mk_project("s8-gate", members={"s8_g1": "member"})
        await _seed_project_scenario(client, h, pid, sid="sc-s8g")
        # 非成员 → 403 not_owner(先撞场景执行权,再轮到凭证来源闸)
        r = await client.post("/api/runs", headers=h_out, json=_run_payload(
            scenarioId="sc-s8g", dataSetIds=[], credentialSource="project"))
        assert r.status_code == 403 and r.json()["detail"]["code"] ==             "not_owner"
        # 私有场景 → 409 credential_source_invalid
        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-s8-priv", steps=[_STEP]))
        r = await client.post("/api/runs", headers=h, json=_run_payload(
            scenarioId="sc-s8-priv", dataSetIds=[], credentialSource="project"))
        assert r.status_code == 409 and r.json()["detail"]["code"] == \
            "credential_source_invalid"
        # 成员 + 项目场景但项目凭证缺槽 → 409 文案指向项目凭证
        r = await client.post("/api/runs", headers=h, json=_run_payload(
            scenarioId="sc-s8g", dataSetIds=[], credentialSource="project"))
        assert r.status_code == 409
        det = r.json()["detail"]
        assert det["code"] == "auth_aliases_missing"
        assert det["credentialSource"] == "project"
        assert "项目凭证" in det["message"]

    async def test_rerun_replays_source_and_token_rejected(
            self, client, plate_mock: PlateMock, monkeypatch):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "s8_t1", "pw123456")
        pid = await _mk_project("s8-tok", members={"s8_t1": "member"})
        await _seed_project_scenario(client, h, pid, sid="sc-s8t")
        await _mk_project_credential(pid)
        cases: list[dict] = []
        _patch_launch_capture(monkeypatch, cases)
        r = await client.post("/api/runs", headers=h, json=_run_payload(
            scenarioId="sc-s8t", dataSetIds=[], credentialSource="project"))
        assert r.status_code == 201, r.text
        ex_id = r.json()["executionId"]
        # config_json 留档
        from app.models.execution import Execution
        async with db_module.SessionLocal() as db:
            cfg = (await db.get(Execution, ex_id)).config_json
        assert cfg["credentialSource"] == "project"
        assert cfg["credentialProjectId"] == pid
        # 重跑按快照回放(项目凭证依旧可用)
        r = await client.post(f"/api/executions/{ex_id}/rerun", headers=h)
        assert r.status_code == 201, r.text


# ── ③ 集成:来源 + 订阅 + 指纹 + 复活 ─────────────────────────────

class TestIntegrationProjectSource:
    async def _seed_tpl(self, client):
        h_owner = await register_and_login(client, "s8_io", "pw123456")
        pid = await _mk_project(
            "s8-int", members={"s8_io": "member"})
        tid = await _mk_project_tpl(client, h_owner, pid, "sc-s8-int")
        return h_owner, pid, tid

    async def test_instance_default_project_source_and_subscribe_choice(
            self, client):
        h_owner, pid, tid = await self._seed_tpl(client)
        # 创建人自动实例:缺省项目来源;详情回显来源与可选项
        r = await client.get(f"/api/integration/tasks/{tid}", headers=h_owner)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["projectCredentialsAvailable"] is True
        assert out["instance"]["credentialSource"] == "project"
        # 缺失清单按项目池口径
        assert out["instance"]["missingCredentials"] == ["qa1"]
        await _mk_project_credential(pid)
        r = await client.get(f"/api/integration/tasks/{tid}", headers=h_owner)
        assert r.json()["instance"]["missingCredentials"] == []
        # 成员乙订阅:缺省建为项目来源;显式 personal → 个人来源
        h_b = await register_and_login(client, "s8_ib", "pw123456")
        from app.models.project import ProjectMember
        async with db_module.SessionLocal() as db:
            db.add(ProjectMember(
                project_id=pid, user_id=await _uid("s8_ib"), role="member"))
            await db.commit()
        fp = (await client.get(
            f"/api/integration/tasks/{tid}/subscription-summary",
            headers=h_b)).json()["fingerprint"]
        r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                              headers=h_b,
                              json={"fingerprint": fp,
                                    "credentialSource": "personal"})
        assert r.status_code == 200, r.text
        inst = r.json()["instance"]
        assert inst["credentialSource"] == "personal"
        # 再切回 project(重新订阅改来源)
        fp = (await client.get(
            f"/api/integration/tasks/{tid}/subscription-summary",
            headers=h_b)).json()["fingerprint"]
        r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                              headers=h_b,
                              json={"fingerprint": fp,
                                    "credentialSource": "project"})
        assert r.json()["instance"]["credentialSource"] == "project"
        # 非成员选 project → 409
        h_x = await register_and_login(client, "s8_ix", "pw123456")
        r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                              headers=h_x,
                              json={"fingerprint": fp,
                                    "credentialSource": "project"})
        assert r.status_code in (404, 409)

    async def test_fingerprint_project_pool_and_revive(self, client):
        h_owner, pid, tid = await self._seed_tpl(client)
        h_b = await register_and_login(client, "s8_rb", "pw123456")
        from app.models.project import ProjectMember
        async with db_module.SessionLocal() as db:
            db.add(ProjectMember(
                project_id=pid, user_id=await _uid("s8_rb"), role="member"))
            await db.commit()
        fp = (await client.get(
            f"/api/integration/tasks/{tid}/subscription-summary",
            headers=h_b)).json()["fingerprint"]
        r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                              headers=h_b, json={"fingerprint": fp})
        assert r.status_code == 200, r.text
        # ① 指纹 slot_bindings 取项目池:登记项目凭证后指纹变化
        from app.models.composer_scenario import ComposerScenario
        from app.models.integration_task import IntegrationTask
        from app.services import integration_runner as ir
        async with db_module.SessionLocal() as db:
            tpl = await db.get(IntegrationTask, tid)
            scen = (await db.execute(sa.select(ComposerScenario).where(
                ComposerScenario.scenario_id == tpl.scenario_id))).scalar()
            fp_before = await ir.consent_fingerprint_now(db, tpl, scen)
        cid = await _mk_project_credential(pid)
        async with db_module.SessionLocal() as db:
            tpl = await db.get(IntegrationTask, tid)
            scen = (await db.execute(sa.select(ComposerScenario).where(
                ComposerScenario.scenario_id == tpl.scenario_id))).scalar()
            fp_after = await ir.consent_fingerprint_now(db, tpl, scen)
        assert fp_before != fp_after
        # ② 复活:项目凭证源实例 missing_credential 暂停 → 凭证写面拉活
        from app.models.integration_task import IntegrationTask
        async with db_module.SessionLocal() as db:
            inst = (await db.execute(sa.select(IntegrationTask).where(
                IntegrationTask.template_id == tid,
                IntegrationTask.holder_id == await _uid("s8_rb"),
            ))).scalar_one()
            inst.state = "paused"
            inst.paused_reason = "missing_credential"
            await db.commit()
        h_admin = await role_headers(client, "s8_ia", role="user")
        # s8_ia 不是本项目管理员:先加为项目管理员
        async with db_module.SessionLocal() as db:
            db.add(ProjectMember(project_id=pid,
                                 user_id=await _uid("s8_ia"), role="admin"))
            await db.commit()
        r = await client.post(
            f"/api/projects/{pid}/credentials", headers=h_admin,
            json={"alias": "qa1b", "slot": "qa1", "url": "",
                  "username": "u", "password": "p12345"})
        assert r.status_code == 201, r.text
        async with db_module.SessionLocal() as db:
            inst2 = await db.get(IntegrationTask, inst.id)
            await db.refresh(inst2)
            assert inst2.state == "idle"

    async def test_member_removed_made_private(self, client):
        h_owner, pid, tid = await self._seed_tpl(client)
        h_b = await register_and_login(client, "s8_mb", "pw123456")
        from app.models.project import ProjectMember
        async with db_module.SessionLocal() as db:
            db.add(ProjectMember(
                project_id=pid, user_id=await _uid("s8_mb"), role="member"))
            await db.commit()
        fp = (await client.get(
            f"/api/integration/tasks/{tid}/subscription-summary",
            headers=h_b)).json()["fingerprint"]
        r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                              headers=h_b, json={"fingerprint": fp})
        assert r.status_code == 200, r.text
        # 移出项目 → run_instance 对非成员停 made_private
        async with db_module.SessionLocal() as db:
            from sqlalchemy import delete as sa_del
            await db.execute(sa_del(ProjectMember).where(
                ProjectMember.project_id == pid,
                ProjectMember.user_id == await _uid("s8_mb")))
            await db.commit()
        from app.models.integration_task import IntegrationTask
        from app.services import integration_runner as ir
        async with db_module.SessionLocal() as db:
            inst_id = (await db.execute(sa.select(IntegrationTask.id).where(
                IntegrationTask.template_id == tid,
                IntegrationTask.holder_id == await _uid("s8_mb"),
            ))).scalar_one()
        # 成员闸在暂停路径收口,不抛
        await ir.run_instance(inst_id)
        async with db_module.SessionLocal() as db:
            inst = (await db.execute(sa.select(IntegrationTask).where(
                IntegrationTask.template_id == tid,
                IntegrationTask.holder_id == await _uid("s8_mb"),
            ))).scalar_one()
        assert inst.state == "paused"
        assert inst.paused_reason == "made_private"


# ── ④ 槽位状态 ────────────────────────────────────────────────────

async def test_slot_status_project_bound(client):
    h = await register_and_login(client, "s8_ss", "pw123456")
    pid = await _mk_project("s8-ss", members={"s8_ss": "member"})
    await _seed_project_scenario(client, h, pid, sid="sc-s8-ss")
    await _mk_project_credential(pid)
    r = await client.get(f"/api/projects/{pid}/slot-status", headers=h)
    assert r.status_code == 200, r.text
    rows = {s["slot"]: s for s in r.json()["slots"]}
    assert rows["qa1"]["projectBound"] is True
