"""入站调用方的生命周期补全(收尾评审 2026-11-02 G1 / G2)。

* G1 集成任务:入站凭证可查 / 删 / 触发**自己别名注册的**任务 ——
  列表只回本别名;他人别名的任务一律 404(不泄露);触发时身份须与
  注册一致(平台模式任务不带 grant、个人模式任务带同一签发人的 grant,
  错配 422 identity_mode_mismatch / 403 grant_issuer_mismatch,与 PATCH
  重绑同码);JWT 面语义不变。
* G2 执行取消:入站凭证可取消 caller_alias_name 等于自己别名的执行
  (与只读查询同规则);他人别名 404;终态 409;JWT 仍只限 owner 本人。
* G4 入站审计:经别名发起的执行 / 取消(inbound.run)、任务注册 / 修改 /
  删除 / 触发(inbound.task.write)、换绑(inbound.grant_rebind)各落一条,
  actor = grant 用户或平台系统用户,resource = 调用方别名,detail 带
  identity_mode / grant_id;JWT 面不记。
* G3 别名页排查面:GET /api/executions?caller_alias= 由别名属主 / admin 列出
  经由该别名的执行(平台模式执行不进「我的执行」);陌生人 / 不存在 404;
  入站凭证忽略该参数。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Execution
from app.models.integration_task import IntegrationTask
from app.models.permission import AuditLog
from app.models.service_alias import ServiceAlias
from app.services import integration_runner as ir

from .helpers import make_draft as _draft, wait_until as _wait
from .inbound_fixtures import (
    mk_execution,
    publish_scenario as _publish,
    seed_alias as _seed_alias, seed_platform_user as _seed_platform_user,
)
from .test_inbound_identity import (
    GET_STEP, _gic, _mk_credential, _mk_grant, _register, _user_id,
)
from .test_inbound_recipe_scope import _capture_fanout

ALIAS_A, ALIAS_B = "agent-sys", "agent-b"


async def _two_aliases() -> tuple[str, str]:
    """两个入站别名各一枚凭证:(token_a, token_b)。"""
    await _seed_platform_user()
    await _seed_alias(ALIAS_A)
    await _seed_alias(ALIAS_B)
    return await _mk_credential(ALIAS_A), await _mk_credential(ALIAS_B)


async def _public_scenario(client, h, scenario_id: str) -> None:
    await client.post("/api/scenarios", headers=h, json=_draft(
        scenario_id, steps=[GET_STEP]))
    await _publish(scenario_id)   # 平台模式范围闸:公共场景


async def _register_platform(client, token: str, scenario_id: str,
                             name: str) -> int:
    r = await client.post("/api/integration/tasks", headers=_gic(token), json={
        "name": name, "scenarioId": scenario_id, "identityMode": "platform"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _stub_run(monkeypatch, sink: list[int]) -> None:
    async def _fake(inst_id: int, *, lease=None):
        sink.append(inst_id)
        return {"status": "done"}
    monkeypatch.setattr(ir, "run_instance", _fake)


# ── G1 ────────────────────────────────────────────────────────────


class TestInboundTaskLifecycle:
    async def test_list_and_get_only_own_alias(self, client):
        tok_a, tok_b = await _two_aliases()
        h = await _register(client, "lc_u1")
        await _public_scenario(client, h, "sc-lc1")
        tid_a = await _register_platform(client, tok_a, "sc-lc1", "task-a")
        tid_b = await _register_platform(client, tok_b, "sc-lc1", "task-b")

        r = await client.get("/api/integration/tasks", headers=_gic(tok_a))
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert [t["id"] for t in items] == [tid_a]
        assert items[0]["callerAliasName"] == ALIAS_A   # 注册方看得到台账
        assert items[0]["canManage"] is True

        r = await client.get(f"/api/integration/tasks/{tid_a}", headers=_gic(tok_a))
        assert r.status_code == 200, r.text
        assert r.json()["id"] == tid_a
        r = await client.get(f"/api/integration/tasks/{tid_b}", headers=_gic(tok_a))
        assert r.status_code == 404
        # JWT 面不变:公共任务对任何用户可见
        r = await client.get(f"/api/integration/tasks/{tid_b}", headers=h)
        assert r.status_code == 200

    async def test_delete_own_only_and_gone_after(self, client):
        tok_a, tok_b = await _two_aliases()
        h = await _register(client, "lc_u2")
        await _public_scenario(client, h, "sc-lc2")
        tid_a = await _register_platform(client, tok_a, "sc-lc2", "task-a")

        r = await client.delete(f"/api/integration/tasks/{tid_a}", headers=_gic(tok_b))
        assert r.status_code == 404
        r = await client.delete(f"/api/integration/tasks/{tid_a}", headers=_gic(tok_a))
        assert r.status_code == 200, r.text
        assert r.json() == {"removed": True}
        async with db_module.SessionLocal() as s:
            assert (await s.get(IntegrationTask, tid_a)).removed_at is not None
        # 软删后对注册方也不再可见 / 可触发
        r = await client.get(f"/api/integration/tasks/{tid_a}", headers=_gic(tok_a))
        assert r.status_code == 404
        r = await client.get("/api/integration/tasks", headers=_gic(tok_a))
        assert r.json()["items"] == []
        r = await client.post(f"/api/integration/tasks/{tid_a}/run", headers=_gic(tok_a))
        assert r.status_code == 404

    async def test_run_platform_task(self, client, monkeypatch):
        tok_a, tok_b = await _two_aliases()
        h = await _register(client, "lc_u3")
        uid = await _user_id("lc_u3")
        await _public_scenario(client, h, "sc-lc3")
        tid_a = await _register_platform(client, tok_a, "sc-lc3", "task-a")
        ran: list[int] = []
        _stub_run(monkeypatch, ran)

        r = await client.post(f"/api/integration/tasks/{tid_a}/run", headers=_gic(tok_b))
        assert r.status_code == 404
        assert ran == []
        # 平台模式任务带 grant(= 个人身份)→ 422,与注册闸同码
        grant = await _mk_grant(ALIAS_A, uid)
        r = await client.post(f"/api/integration/tasks/{tid_a}/run",
                              headers=_gic(tok_a, grant))
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "identity_mode_mismatch"
        assert ran == []
        r = await client.post(f"/api/integration/tasks/{tid_a}/run", headers=_gic(tok_a))
        assert r.status_code == 200, r.text
        assert r.json()["result"] == {"status": "done"}
        async with db_module.SessionLocal() as s:
            inst_id = (await s.execute(sa.select(IntegrationTask.id).where(
                IntegrationTask.template_id == tid_a))).scalar_one()
        assert ran == [inst_id]
        # 平台模式冷却仍生效(60s 内再触发 409)
        r = await client.post(f"/api/integration/tasks/{tid_a}/run", headers=_gic(tok_a))
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] in ("cooldown", "running")

    async def test_run_personal_task_requires_same_issuer_grant(
            self, client, monkeypatch):
        tok_a, _ = await _two_aliases()
        h = await _register(client, "lc_u4")
        uid = await _user_id("lc_u4")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-lc4", steps=[GET_STEP]))
        grant = await _mk_grant(ALIAS_A, uid)
        r = await client.post("/api/integration/tasks", headers=_gic(tok_a, grant),
                              json={"name": "task-p", "scenarioId": "sc-lc4",
                                    "identityMode": "personal"})
        assert r.status_code == 201, r.text
        tid = r.json()["id"]
        ran: list[int] = []
        _stub_run(monkeypatch, ran)

        # 不带 grant(平台身份)→ 422
        r = await client.post(f"/api/integration/tasks/{tid}/run", headers=_gic(tok_a))
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "identity_mode_mismatch"
        # 同别名、他人签发的 grant → 403
        await _register(client, "lc_u4b")
        other = await _mk_grant(ALIAS_A, await _user_id("lc_u4b"))
        r = await client.post(f"/api/integration/tasks/{tid}/run",
                              headers=_gic(tok_a, other))
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "grant_issuer_mismatch"
        assert ran == []
        # 同一签发人的 grant → 触发自己的实例(无冷却)
        r = await client.post(f"/api/integration/tasks/{tid}/run",
                              headers=_gic(tok_a, grant))
        assert r.status_code == 200, r.text
        assert len(ran) == 1

    async def test_jwt_delete_semantics_unchanged(self, client):
        tok_a, _ = await _two_aliases()
        h = await _register(client, "lc_u5")
        await _public_scenario(client, h, "sc-lc5")
        tid_a = await _register_platform(client, tok_a, "sc-lc5", "task-a")
        # 平台模式任务 owner = 系统用户:普通成员 403(不是 404),admin 可删
        other = await _register(client, "lc_u5b")
        r = await client.delete(f"/api/integration/tasks/{tid_a}", headers=other)
        assert r.status_code == 403


# ── G2 ────────────────────────────────────────────────────────────


class TestInboundCancel:
    async def test_inbound_cancels_own_alias_execution_only(self, client):
        tok_a, _ = await _two_aliases()
        ex_a = await mk_execution(caller=ALIAS_A, status="running")
        ex_b = await mk_execution(caller=ALIAS_B, status="queued")

        r = await client.post(f"/api/executions/{ex_b}/cancel", headers=_gic(tok_a))
        assert r.status_code == 404
        r = await client.post(f"/api/executions/{ex_a}/cancel", headers=_gic(tok_a))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "canceled"
        async with db_module.SessionLocal() as s:
            assert (await s.get(Execution, ex_a)).status == "canceled"
            assert (await s.get(Execution, ex_b)).status == "queued"
        # 终态再取消 409(与 JWT 面同口径)
        r = await client.post(f"/api/executions/{ex_a}/cancel", headers=_gic(tok_a))
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "not_cancelable"

    async def test_jwt_cancel_still_owner_only(self, client):
        await _two_aliases()
        ex_a = await mk_execution(caller=ALIAS_A, status="running")
        # 平台模式执行 owner = 系统用户;别名属主/普通成员经 JWT 取消 → 404
        h = await _register(client, "lc_u6")
        r = await client.post(f"/api/executions/{ex_a}/cancel", headers=h)
        assert r.status_code == 404


# ── G4 ────────────────────────────────────────────────────────────


async def _audit(action: str) -> list[AuditLog]:
    async with db_module.SessionLocal() as s:
        return list((await s.execute(sa.select(AuditLog).where(
            AuditLog.action == action).order_by(AuditLog.id))).scalars().all())


class TestInboundAudit:
    async def test_task_lifecycle_and_rebind_audited(self, client, monkeypatch):
        tok_a, _ = await _two_aliases()
        h = await _register(client, "au_u1")
        uid = await _user_id("au_u1")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-au1", steps=[GET_STEP]))
        grant = await _mk_grant(ALIAS_A, uid)
        r = await client.post("/api/integration/tasks", headers=_gic(tok_a, grant),
                              json={"name": "task-au", "scenarioId": "sc-au1",
                                    "identityMode": "personal"})
        assert r.status_code == 201, r.text
        tid = r.json()["id"]
        _stub_run(monkeypatch, [])
        assert (await client.post(f"/api/integration/tasks/{tid}/run",
                                  headers=_gic(tok_a, grant))).status_code == 200
        grant2 = await _mk_grant(ALIAS_A, uid)
        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=_gic(tok_a, grant2), json={"name": "task-au2"})
        assert r.status_code == 200, r.text
        assert (await client.delete(f"/api/integration/tasks/{tid}",
                                    headers=_gic(tok_a))).status_code == 200
        rows = await _audit("inbound.task.write")
        assert [r.detail["fn"] for r in rows] == ["create", "run", "patch", "delete"]
        assert {r.resource_type for r in rows} == {"alias"}
        assert {r.resource_id for r in rows} == {ALIAS_A}
        assert rows[0].actor_id == uid                      # 个人模式 actor = grant 用户
        assert rows[0].detail["identity_mode"] == "personal"
        assert rows[0].detail["grant_id"] is not None
        assert rows[0].detail["task"] == tid
        assert rows[2].detail["changed"] == ["name"]
        assert rows[3].detail["identity_mode"] == "platform"  # 删除时未带 grant
        rebind = await _audit("inbound.grant_rebind")
        assert len(rebind) == 1
        assert rebind[0].detail["task"] == tid
        assert rebind[0].detail["grant_from"] == rows[0].detail["grant_id"]
        assert rebind[0].detail["grant_id"] != rebind[0].detail["grant_from"]
        assert rebind[0].detail["resumed"] is False
        # 同 grant 再 PATCH:只记 task.write,不再记换绑
        async with db_module.SessionLocal() as s:
            (await s.get(IntegrationTask, tid)).removed_at = None
            await s.commit()
        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=_gic(tok_a, grant2), json={})
        assert r.status_code == 200, r.text
        assert len(await _audit("inbound.grant_rebind")) == 1
        assert len(await _audit("inbound.task.write")) == 5

    async def test_run_and_cancel_audited_jwt_not(self, client, monkeypatch):
        tok_a, _ = await _two_aliases()
        h = await _register(client, "au_u2")
        await _public_scenario(client, h, "sc-au2")
        cap = await _capture_fanout(monkeypatch)
        r = await client.post("/api/runs", headers=_gic(tok_a),
                              json={"scenarioId": "sc-au2", "clientRef": "cr-1"})
        assert r.status_code == 201, r.text
        ex_id = r.json()["executionId"]
        # JWT 发起不记
        r = await client.post("/api/runs", headers=h, json={"scenarioId": "sc-au2"})
        assert r.status_code == 201, r.text
        await _wait(lambda: len(cap) == 2)
        ex_c = await mk_execution(caller=ALIAS_A, status="running")
        assert (await client.post(f"/api/executions/{ex_c}/cancel",
                                  headers=_gic(tok_a))).status_code == 200
        rows = await _audit("inbound.run")
        assert [(r.detail["fn"], r.detail["execution"]) for r in rows] == [
            ("scenario", ex_id), ("cancel", ex_c)]
        assert rows[0].detail["scenario_id"] == "sc-au2"
        assert rows[0].detail["client_ref"] == "cr-1"
        assert rows[0].detail["identity_mode"] == "platform"
        assert rows[0].actor_name == "平台系统"
        assert rows[0].resource_id == ALIAS_A


# ── G3 ────────────────────────────────────────────────────────────


class TestAliasExecutionsList:
    async def test_alias_owner_and_admin_list_by_caller_alias(self, client):
        tok_a, _ = await _two_aliases()
        ex_a = await mk_execution(caller=ALIAS_A, status="done")
        await mk_execution(caller=ALIAS_B, status="done")
        h_admin = await _register(client, "al_admin")        # 首个真人 = admin
        h_owner = await _register(client, "al_owner")        # 之后注册 = 普通用户
        async with db_module.SessionLocal() as s:
            (await s.get(ServiceAlias, ALIAS_A)).owner_user_id = await _user_id("al_owner")
            await s.commit()
        r = await client.get("/api/executions", headers=h_owner,
                             params={"caller_alias": ALIAS_A})
        assert r.status_code == 200, r.text
        assert [it["id"] for it in r.json()["items"]] == [ex_a]
        # 不是属主的别名 / 不存在的别名 → 404
        r = await client.get("/api/executions", headers=h_owner,
                             params={"caller_alias": ALIAS_B})
        assert r.status_code == 404
        r = await client.get("/api/executions", headers=h_owner,
                             params={"caller_alias": "nope"})
        assert r.status_code == 404
        # 不带参数仍是「我的执行」(平台模式执行不进来)
        r = await client.get("/api/executions", headers=h_owner)
        assert r.json()["total"] == 0
        # 入站凭证忽略 caller_alias(恒按本别名)
        r = await client.get("/api/executions", headers=_gic(tok_a),
                             params={"caller_alias": ALIAS_B})
        assert r.status_code == 200
        assert [it["id"] for it in r.json()["items"]] == [ex_a]
        # admin 任意别名
        r = await client.get("/api/executions", headers=h_admin,
                             params={"caller_alias": ALIAS_B})
        assert r.status_code == 200 and r.json()["total"] == 1
