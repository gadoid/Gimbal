"""authz M2b Q1:项目用户角色(``project_members.role='user'``)。

钉子(只读 + 执行):
* 读 / 复制 / 执行 / 选用项目凭证 / 订阅项目集成 —— 与成员同;
* 新建(场景 / suite / 集成模板)403 ``project_role_readonly``;改 / 删项目
  场景 403;提升进项目 403;
* 成员管理:可加为 / 改为项目用户;管理员降级为项目用户同样过「最后
  一个管理员」保护;``canWrite`` 输出三态。
表 B 全叉积在 test_authz_matrix_b(``{_P: "user"}`` 主体)。
"""
from __future__ import annotations

from tests.helpers import make_draft, register_and_login, role_headers

from .test_authz_s8_project_credentials import (
    _STEP, _mk_project, _mk_project_credential, _mk_project_tpl,
    _seed_project_scenario,
)
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401


class TestProjectUserReadOnly:
    async def test_write_surface_denied(self, client):
        h_m = await register_and_login(client, "q1_m", "pw123456")
        h_u = await register_and_login(client, "q1_u", "pw123456")
        pid = await _mk_project("q1-ro", members={"q1_m": "member",
                                                  "q1_u": "user"})
        await _seed_project_scenario(client, h_m, pid, sid="sc-q1")
        # 读:200
        assert (await client.get("/api/scenarios/sc-q1", headers=h_u)
                ).status_code == 200
        # 新建场景 / suite / 集成模板:403 project_role_readonly
        r = await client.post(f"/api/scenarios?projectId={pid}", headers=h_u,
                              json=make_draft("sc-q1-new", steps=[_STEP]))
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "project_role_readonly"
        r = await client.post("/api/suites", headers=h_u, json={
            "name": "q1-suite", "projectId": pid})
        assert r.status_code == 403, r.text
        r = await client.post("/api/integration/tasks", headers=h_u, json={
            "name": "q1-tpl", "scenarioId": "sc-q1",
            "identityMode": "personal", "triggerCron": "0 3 * * *",
            "projectId": pid})
        assert r.status_code == 403, r.text
        # 改 / 删项目场景:403
        r = await client.put("/api/scenarios/sc-q1", headers=h_u,
                             json=make_draft("sc-q1", steps=[_STEP]))
        assert r.status_code == 403, r.text
        assert (await client.delete("/api/scenarios/sc-q1", headers=h_u)
                ).status_code == 403
        # 提升进项目:403(私有场景 → 项目)
        await client.post("/api/scenarios", headers=h_u,
                          json=make_draft("sc-q1-priv", steps=[_STEP]))
        r = await client.post(f"/api/projects/{pid}/promotions/analyze",
                              headers=h_u, json={"kind": "scenario",
                                                 "sourceId": "sc-q1-priv"})
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "project_role_readonly"
        # 复制到私有区:允许(M1)
        r = await client.post("/api/scenarios/sc-q1/copy", headers=h_u,
                              json={"newScenarioId": "sc-q1-mine"})
        assert r.status_code == 201, r.text
        # 成员照旧能写
        r = await client.put("/api/scenarios/sc-q1", headers=h_m,
                             json=make_draft("sc-q1", steps=[_STEP]))
        assert r.status_code == 200, r.text

    async def test_run_with_project_credentials_and_subscribe(
            self, client, plate_mock: PlateMock, monkeypatch):
        plate_mock.behaviour = "echo"
        h_m = await register_and_login(client, "q1_rm", "pw123456")
        h_u = await register_and_login(client, "q1_ru", "pw123456")
        pid = await _mk_project("q1-run", members={"q1_rm": "member",
                                                   "q1_ru": "user"})
        tid = await _mk_project_tpl(client, h_m, pid, "sc-q1r")
        await _mk_project_credential(pid)
        cases: list[dict] = []
        _patch_launch_capture(monkeypatch, cases)
        r = await client.post("/api/runs", headers=h_u, json=_run_payload(
            scenarioId="sc-q1r", dataSetIds=[], credentialSource="project"))
        assert r.status_code == 201, r.text
        # 订阅项目集成模板(M2)
        r = await client.get(
            f"/api/integration/tasks/{tid}/subscription-summary", headers=h_u)
        assert r.status_code == 200, r.text
        r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                              headers=h_u, json={
                                  "fingerprint": r.json()["fingerprint"],
                                  "credentialSource": "project"})
        assert r.status_code in (200, 201), r.text


class TestMemberManagement:
    async def test_role_user_and_last_admin_guard(self, client):
        h_a = await role_headers(client, "q1_ga", role="user")
        h_u = await register_and_login(client, "q1_gu", "pw123456")
        pid = await _mk_project("q1-mm", members={"q1_ga": "admin"})
        from .test_authz_s8_project_credentials import _uid
        uid_u, uid_a = await _uid("q1_gu"), await _uid("q1_ga")
        r = await client.post(f"/api/projects/{pid}/members", headers=h_a,
                              json={"userId": uid_u, "role": "user"})
        assert r.status_code in (200, 201), r.text
        assert r.json()["role"] == "user"
        # canWrite:管理员 True / 项目用户 False
        assert (await client.get(f"/api/projects/{pid}", headers=h_a)
                ).json()["canWrite"] is True
        out = (await client.get(f"/api/projects/{pid}", headers=h_u)).json()
        assert out["myRole"] == "user" and out["canWrite"] is False
        # 唯一管理员降级为项目用户 → 拒绝(最后一个管理员)
        r = await client.patch(f"/api/projects/{pid}/members/{uid_a}",
                               headers=h_a, json={"role": "user"})
        assert r.status_code in (409, 422), r.text
        # 非法角色 422
        r = await client.patch(f"/api/projects/{pid}/members/{uid_u}",
                               headers=h_a, json={"role": "owner"})
        assert r.status_code == 422
