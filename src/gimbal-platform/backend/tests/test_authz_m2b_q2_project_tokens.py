"""authz M2b Q2:项目令牌(``kind='project'``)。

钉子:
* 管理面 ``/projects/{pid}/tokens``:仅项目管理员(r5-2.2 同口径,
  Admin+ 非成员不旁路);成员 403 / 非成员 404 / 公共项目 409;
  负责人须是项目管理员;个人令牌面看不到项目令牌;
* 调用:区锁(私有 / 他项目 404)+ 恒用项目凭证 + 范围按项目池;执行
  ``owner_id`` = 负责人、``project_id`` / ``token_id`` 落库;
* 负责人失格 → 401 ``token_holder_invalid``;换绑:本人立即 / 他人待确认
  (确认前按原负责人状态)/ 拒绝;项目删除吊销;
* 集成注册(M5):模板归项目、注册方实例项目源锁定;负责人失格 → 注册
  方实例 ``token_holder_invalid`` 暂停,换绑确认后模板 / 实例迁移并复活。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models.auth_session import AuthSession

from .helpers import make_draft, register_and_login, role_headers
from .test_authz_s8_project_credentials import (
    _STEP, _mk_project, _mk_project_credential, _seed_project_scenario, _uid,
)
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401


def _bearer(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


async def _issue(client, h, pid: int, *, auth_ids: list[int],
                 holder_id: int | None = None) -> tuple[int, str]:
    body = {"name": "ci", "scope": {"aliases": ["s8-alias"],
                                    "authIds": auth_ids}}
    if holder_id is not None:
        body["holderId"] = holder_id
    r = await client.post(f"/api/projects/{pid}/tokens", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"], r.json()["token"]


async def _set_role(pid: int, username: str, role: str | None) -> None:
    from app.models.project import ProjectMember
    uid = await _uid(username)
    async with db_module.SessionLocal() as db:
        m = (await db.execute(sa.select(ProjectMember).where(
            ProjectMember.project_id == pid,
            ProjectMember.user_id == uid))).scalar_one_or_none()
        if role is None:
            if m is not None:
                await db.delete(m)
        elif m is None:
            db.add(ProjectMember(project_id=pid, user_id=uid, role=role))
        else:
            m.role = role
        await db.commit()


class TestManagement:
    async def test_gates_and_personal_face_hidden(self, client):
        h_a = await register_and_login(client, "q2_ga", "pw123456")
        h_m = await register_and_login(client, "q2_gm", "pw123456")
        h_x = await register_and_login(client, "q2_gx", "pw123456")
        pid = await _mk_project("q2-g", members={"q2_ga": "admin",
                                                 "q2_gm": "member"})
        base = f"/api/projects/{pid}/tokens"
        body = {"name": "t1"}
        assert (await client.post(base, headers=h_m, json=body)
                ).status_code == 403
        assert (await client.post(base, headers=h_x, json=body)
                ).status_code == 404
        # 负责人须是项目管理员
        r = await client.post(base, headers=h_a, json={
            "name": "t1", "holderId": await _uid("q2_gm")})
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "holder_not_project_admin"
        r = await client.post(base, headers=h_a, json=body)
        assert r.status_code == 201, r.text
        tid = r.json()["id"]
        assert r.json()["token"].startswith("gtk_")
        out = (await client.get(base, headers=h_a)).json()
        assert out["items"][0]["holderId"] == await _uid("q2_ga")
        assert out["items"][0]["holderValid"] is True
        assert out["items"][0]["kind"] == "project"
        # 个人令牌面:列表不出现、按 id 404
        mine = (await client.get("/api/access-tokens", headers=h_a)).json()
        assert all(it["id"] != tid for it in mine["items"])
        assert (await client.get(f"/api/access-tokens/{tid}", headers=h_a)
                ).status_code == 404
        # Admin+ 非成员不旁路(2026-11-11 与 S8 凭证同口径收口:
        # 令牌是项目的,不是平台的;404 不泄露存在性)
        h_ops = await role_headers(client, "q2_ops", role="admin")
        assert (await client.get(base, headers=h_ops)).status_code == 404
        # 公共项目 409
        from .test_authz_s8_project_credentials import _public_project_id
        ppid = await _public_project_id()
        r = await client.post(f"/api/projects/{ppid}/tokens", headers=h_ops,
                              json=body)
        assert r.status_code == 409
        # 审计 project.token.write
        from app.models.permission import AuditLog
        async with db_module.SessionLocal() as db:
            acts = (await db.execute(sa.select(AuditLog.action).where(
                AuditLog.resource_type == "project",
                AuditLog.resource_id == str(pid)))).scalars().all()
        assert "project.token.write" in acts
        # 项目删除 → 令牌吊销
        h_del = await role_headers(client, "q2_del", role="admin")
        pid2 = await _mk_project("q2-del", members={"q2_del": "admin"})
        r = await client.post(f"/api/projects/{pid2}/tokens", headers=h_del,
                              json={"name": "d"})
        tid2 = r.json()["id"]
        assert (await client.delete(f"/api/projects/{pid2}", headers=h_del)
                ).status_code == 204
        from app.models.access_token import AccessToken
        async with db_module.SessionLocal() as db:
            assert (await db.get(AccessToken, tid2)).revoked_at is not None


class TestCalls:
    async def test_zone_lock_project_pool_and_record(
            self, client, plate_mock: PlateMock, monkeypatch):
        plate_mock.behaviour = "echo"
        h_a = await register_and_login(client, "q2_ca", "pw123456")
        pid = await _mk_project("q2-call", members={"q2_ca": "admin"})
        other = await _mk_project("q2-other", members={"q2_ca": "admin"})
        await _seed_project_scenario(client, h_a, pid, sid="sc-q2")
        await _seed_project_scenario(client, h_a, other, sid="sc-q2-other")
        await client.post("/api/scenarios", headers=h_a,
                          json=make_draft("sc-q2-priv", steps=[_STEP]))
        # 负责人个人池也有 qa1(验证不被取用)
        async with db_module.SessionLocal() as s:
            s.add(AuthSession(
                owner_id=await _uid("q2_ca"), alias="qa1", slot="qa1",
                system="fin", url="http://personal-auth",
                username_enc=fernet_encrypt("me"),
                password_enc=fernet_encrypt("me"),
                account_fields={"orgNo": "ME"}, is_default=True))
            await s.commit()
        cid = await _mk_project_credential(pid)
        tid, plain = await _issue(client, h_a, pid, auth_ids=[cid])
        hb = _bearer(plain)
        cases: list[dict] = []
        _patch_launch_capture(monkeypatch, cases)
        # 区锁:私有 / 他项目 404
        for sid in ("sc-q2-priv", "sc-q2-other"):
            r = await client.post("/api/runs", headers=hb,
                                  json={"scenarioId": sid})
            assert r.status_code == 404, (sid, r.text)
        # 预览同锁 + 恒项目源
        r = await client.post("/api/runs/preview", headers=hb,
                              json={"scenarioId": "sc-q2"})
        assert r.status_code == 200, r.text
        assert r.json()["auths"]["qa1"]["source"] == "project"
        # 本项目:200,项目凭证注入
        r = await client.post("/api/runs", headers=hb,
                              json={"scenarioId": "sc-q2"})
        assert r.status_code == 201, r.text
        ex_id = r.json()["executionId"]
        from .helpers import wait_until
        await wait_until(lambda: len(cases) >= 1)
        assert cases[0]["config"]["users"]["qa1"]["url"] == "http://proj-auth"
        from app.models.execution import Execution
        async with db_module.SessionLocal() as db:
            ex = await db.get(Execution, ex_id)
        assert ex.owner_id == await _uid("q2_ca")
        assert ex.token_id == tid and ex.project_id == pid
        assert ex.config_json["credentialSource"] == "project"
        assert ex.config_json["token"]["projectId"] == pid
        # 请求体带 credentialSource → 422(配方禁令不变)
        r = await client.post("/api/runs", headers=hb, json={
            "scenarioId": "sc-q2", "credentialSource": "personal"})
        assert r.status_code == 422
        # 范围外:范围不含项目凭证 → 403 resource_not_allowed
        tid2, plain2 = await _issue(client, h_a, pid, auth_ids=[])
        r = await client.post("/api/runs", headers=_bearer(plain2),
                              json={"scenarioId": "sc-q2"})
        assert r.status_code == 403, r.text
        # adhoc 仍限个人令牌
        r = await client.post("/api/runs", headers=hb, json={
            "steps": [{"service": "s8-alias", "endpoint": "GET /x"}]})
        assert r.status_code == 403

    async def test_holder_invalid_and_rebind(self, client, plate_mock):
        plate_mock.behaviour = "echo"
        h_a = await register_and_login(client, "q2_ha", "pw123456")
        h_b = await register_and_login(client, "q2_hb", "pw123456")
        pid = await _mk_project("q2-hold", members={"q2_ha": "admin",
                                                    "q2_hb": "admin"})
        await _seed_project_scenario(client, h_a, pid, sid="sc-q2h")
        cid = await _mk_project_credential(pid)
        tid, plain = await _issue(client, h_a, pid, auth_ids=[cid])
        hb = _bearer(plain)
        base = f"/api/projects/{pid}/tokens/{tid}"
        ok = await client.post("/api/runs/preview", headers=hb,
                               json={"scenarioId": "sc-q2h"})
        assert ok.status_code == 200
        # 换绑给乙:待确认;确认前仍按甲(有效)
        r = await client.put(f"{base}/holder", headers=h_a,
                             json={"userId": await _uid("q2_hb")})
        assert r.status_code == 200 and r.json()["pending"] is True
        assert (await client.post("/api/runs/preview", headers=hb, json={
            "scenarioId": "sc-q2h"})).status_code == 200
        # 拒绝 → 清 pending
        r = await client.post(f"{base}/holder/decline", headers=h_b)
        assert r.status_code == 200 and r.json()["holderPendingId"] is None
        # 甲降级 → 401 token_holder_invalid
        await _set_role(pid, "q2_ha", "member")
        r = await client.post("/api/runs/preview", headers=hb,
                              json={"scenarioId": "sc-q2h"})
        assert r.status_code == 401
        assert r.json()["detail"]["code"] == "token_holder_invalid"
        # 乙自己接任:立即生效
        r = await client.put(f"{base}/holder", headers=h_b,
                             json={"userId": await _uid("q2_hb")})
        assert r.status_code == 200 and r.json()["pending"] is False
        assert (await client.post("/api/runs/preview", headers=hb, json={
            "scenarioId": "sc-q2h"})).status_code == 200
        # 非待确认人 accept → 404
        assert (await client.post(f"{base}/holder/accept", headers=h_a)
                ).status_code == 404
        # 负责人改密不影响项目令牌
        r = await client.post("/api/auth/change-password", headers=h_b, json={
            "old_password": "pw123456", "new_password": "Pw654321!x"})
        assert r.status_code == 200, r.text
        assert (await client.post("/api/runs/preview", headers=hb, json={
            "scenarioId": "sc-q2h"})).status_code == 200


class TestIntegrationRegistration:
    async def test_register_lock_pause_and_rebind_migrate(
            self, client, plate_mock):
        plate_mock.behaviour = "echo"
        h_a = await register_and_login(client, "q2_ia", "pw123456")
        h_b = await register_and_login(client, "q2_ib", "pw123456")
        pid = await _mk_project("q2-int", members={"q2_ia": "admin",
                                                   "q2_ib": "admin"})
        await _seed_project_scenario(client, h_a, pid, sid="sc-q2i")
        await client.post("/api/scenarios", headers=h_a,
                          json=make_draft("sc-q2i-priv", steps=[_STEP]))
        cid = await _mk_project_credential(pid)
        tid, plain = await _issue(client, h_a, pid, auth_ids=[cid])
        hb = _bearer(plain)
        # 私有场景注册 → 404
        r = await client.post("/api/integration/tasks", headers=hb, json={
            "name": "x", "scenarioId": "sc-q2i-priv",
            "triggerCron": "0 3 * * *"})
        assert r.status_code == 404, r.text
        r = await client.post("/api/integration/tasks", headers=hb, json={
            "name": "q2-tpl", "scenarioId": "sc-q2i",
            "triggerCron": "0 3 * * *"})
        assert r.status_code == 201, r.text
        tpl_id = r.json()["id"]
        from app.models.integration_task import IntegrationTask
        uid_a, uid_b = await _uid("q2_ia"), await _uid("q2_ib")
        async with db_module.SessionLocal() as db:
            tpl = await db.get(IntegrationTask, tpl_id)
            assert tpl.project_id == pid and tpl.owner_id == uid_a
            assert tpl.token_id == tid
            inst = (await db.execute(sa.select(IntegrationTask).where(
                IntegrationTask.template_id == tpl_id))).scalar_one()
            assert inst.holder_id == uid_a
            assert inst.credential_source == "project"
            inst_id = inst.id
        # 注册方实例切个人来源 → 409 credential_source_locked
        fp = (await client.get(
            f"/api/integration/tasks/{tpl_id}/subscription-summary",
            headers=h_a)).json()["fingerprint"]
        r = await client.post(f"/api/integration/tasks/{tpl_id}/subscribe",
                              headers=h_a, json={
                                  "fingerprint": fp,
                                  "credentialSource": "personal"})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "credential_source_locked"
        # 负责人(甲)移出项目 → 运行前复核暂停 token_holder_invalid
        await _set_role(pid, "q2_ia", None)
        from app.services import integration_runner as ir
        await ir.run_instance(inst_id)
        async with db_module.SessionLocal() as db:
            inst = await db.get(IntegrationTask, inst_id)
            assert inst.state == "paused"
            assert inst.paused_reason == "token_holder_invalid"
        # 乙接任(本人立即生效)→ 模板 / 实例迁到乙 + 复活
        r = await client.put(f"/api/projects/{pid}/tokens/{tid}/holder",
                             headers=h_b, json={"userId": uid_b})
        assert r.status_code == 200, r.text
        async with db_module.SessionLocal() as db:
            tpl = await db.get(IntegrationTask, tpl_id)
            inst = await db.get(IntegrationTask, inst_id)
        assert tpl.owner_id == uid_b
        assert inst.holder_id == uid_b and inst.owner_id == uid_b
        assert inst.credential_source == "project"
        assert inst.state == "idle"
