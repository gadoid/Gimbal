"""M1 + M2 修复(修复方案 2026-11-01 §1/§2):入站配方收归服务端、
平台模式调用方隔离 —— 开放入站凭证之前的硬门槛。

M1:入站调用只能**选择**服务端配方,不能携带(地址链第①层「显式绑定
url 优先」可被用来改写被测地址并带走注入凭证);
M2:平台模式只能执行公共场景或别名属主自己的场景;任务管理权按调用方
别名判定;每次运行前重查。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Execution
from app.models.integration_task import IntegrationTask
from app.models.webhook_delivery import WebhookDelivery
from app.services import integration_runner as ir
from app.services import run_dispatcher as rd
from app.services.run_dispatcher import STATUS_DONE

from .helpers import make_draft as _draft, wait_until as _wait
from .inbound_fixtures import (
    publish_scenario as _publish,
    seed_alias as _seed_alias, seed_platform_user as _seed_platform_user,
)
from .test_inbound_identity import (
    GET_STEP, _gic, _mk_credential, _own_alias, _promote, _register,
)

# ── M1:入站配方收归服务端 ────────────────────────────────────────


async def _seed_scheme(scenario_id: str, payload: dict, *,
                       name: str = "入站方案") -> str:
    from app.services import scheme_store
    async with db_module.SessionLocal() as s:
        row = await scheme_store.create_scheme(
            s, scenario_id, name=name, payload=payload)
    return row["schemeId"]


async def _capture_fanout(monkeypatch) -> "list[dict]":
    """把 _fanout 打桩:捕获 dispatch 入队后 worker 解包后的实参。"""
    cap: list[dict] = []

    async def _fake_fanout(*, db_factory, execution_id, **kw):
        cap.append({"execution_id": execution_id, **kw})
        await rd.transition_with_retry(db_factory, execution_id, STATUS_DONE)

    monkeypatch.setattr(rd, "_fanout", _fake_fanout)
    return cap


class TestM1InboundRecipe:
    async def test_forbidden_fields_422(self, client):
        await _seed_platform_user()
        await _seed_alias()
        token = await _mk_credential()
        h = await _register(client, "m1_owner")
        await _own_alias("agent-sys", "m1_owner")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-m1", steps=[GET_STEP]))
        cases = [
            ({"serviceBindings": {"svc": {"url": "https://attacker.example"}}},
             "serviceBindings"),
            ({"dataSetIds": ["ds-1"]}, "dataSetIds"),
            ({"dataSetSelection": [{"datasetId": "ds-1"}]},
             "dataSetSelection"),
            ({"injectionEntryIds": ["inj-1"]}, "injectionEntryIds"),
            ({"graph": {"units": [
                {"ref": "u1", "scenarioId": "sc-m1"}]}}, "graph"),
            # 内层键 snake_case(RunOptions extra=forbid,与生成物同形)
            ({"runOptions": {"n_runs": 2}}, "runOptions.nRuns"),
            ({"runOptions": {"parallel": 3}}, "runOptions.parallel"),
            ({"runOptions": {"step_from": 0}}, "runOptions.stepFrom"),
            ({"runOptions": {"subscribe": [{"sink": "stdout"}]}},
             "runOptions.subscribe"),
            ({"runOptions": {"debug": {"breakpoints": []}}},
             "runOptions.debug"),
        ]
        for extra, field in cases:
            r = await client.post("/api/runs", headers=_gic(token), json={
                "scenarioId": "sc-m1", **extra})
            assert r.status_code == 422, (field, r.text)
            detail = r.json()["detail"]
            assert detail["code"] == "inbound_field_not_allowed"
            assert field in detail["fields"], (field, detail)

    async def test_step_to_allowed_and_default_scheme_applied(
            self, client, monkeypatch):
        """stepTo 放行;未给 schemeId → 默认方案的绑定/数据集下发到
        fan-out(调用方无法携带配方,只能选)。"""
        await _seed_platform_user()
        await _seed_alias()
        token = await _mk_credential()
        h = await _register(client, "m1_owner2")
        await _own_alias("agent-sys", "m1_owner2")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-m1b", steps=[GET_STEP, GET_STEP]))
        # 建默认方案:绑定 + 注入条目(数据集留空,不落库外键)
        from app.services import scheme_store
        async with db_module.SessionLocal() as s:
            await scheme_store.ensure_default_scheme(s, "sc-m1b")
            row = (await s.execute(sa.select(scheme_store.ComposerRunScheme)
                                   .where(
                                       scheme_store.ComposerRunScheme
                                       .scenario_id == "sc-m1b",
                                       scheme_store.ComposerRunScheme
                                       .is_default.is_(True)))).scalar_one()
            row.payload = {
                "dataSetSelection": [],
                "injectionEntryIds": [],
                "serviceBindings": {"svc": {"authAlias": "qa-cred"}},
                "options": {"step_from": None, "step_to": None,
                            "n_runs": 1, "parallel": 1},
            }
            await s.commit()
            scheme_id = row.scheme_id
        cap = await _capture_fanout(monkeypatch)
        r = await client.post("/api/runs", headers=_gic(token), json={
            "scenarioId": "sc-m1b", "runOptions": {"step_to": 1}})
        assert r.status_code == 201, r.text
        await _wait(lambda: len(cap) == 1)
        got = cap[0]
        assert got["service_bindings"]["svc"].auth_alias == "qa-cred"
        assert got["halt_at"] == 1
        # 溯源:schemeId 落方案真值
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, r.json()["executionId"])
            assert ex.config_json["schemeId"] == scheme_id

    async def test_explicit_scheme_of_other_scenario_422(self, client):
        await _seed_platform_user()
        await _seed_alias()
        token = await _mk_credential()
        h = await _register(client, "m1_owner3")
        await _own_alias("agent-sys", "m1_owner3")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-m1c", steps=[GET_STEP]))
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-m1d", steps=[GET_STEP]))
        other = await _seed_scheme("sc-m1d", {}, name="别人的方案")
        r = await client.post("/api/runs", headers=_gic(token), json={
            "scenarioId": "sc-m1c", "schemeId": other})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "scheme_not_owned"

    async def test_jwt_path_keeps_carrying_recipe(self, client, monkeypatch):
        """JWT 调用行为不变:仍可携带 serviceBindings。"""
        await _seed_platform_user()
        h = await _register(client, "m1_jwt")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-m1e", steps=[GET_STEP]))
        cap = await _capture_fanout(monkeypatch)
        r = await client.post("/api/runs", headers=h, json={
            "scenarioId": "sc-m1e",
            "serviceBindings": {"svc": {"authAlias": "jwt-cred"}}})
        assert r.status_code == 201, r.text
        await _wait(lambda: len(cap) == 1)
        assert cap[0]["service_bindings"]["svc"].auth_alias == "jwt-cred"


# ── M2:平台模式隔离 ──────────────────────────────────────────────


class TestM2PlatformScope:
    async def test_run_scope_matrix(self, client):
        await _seed_platform_user()
        await _seed_alias("agent-sys")
        h = await _register(client, "m2_owner")
        # 公共场景(属主可为他人的公共场景)
        h_other = await _register(client, "m2_other")
        await client.post("/api/scenarios", headers=h_other, json=_draft(
            "sc-m2-pub", steps=[GET_STEP]))
        await _publish("sc-m2-pub")
        # 别名属主自己的私有场景
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-m2-own", steps=[GET_STEP]))
        # 他人私有场景
        await client.post("/api/scenarios", headers=h_other, json=_draft(
            "sc-m2-priv", steps=[GET_STEP]))
        await _own_alias("agent-sys", "m2_owner")
        token = await _mk_credential()
        # 公共 → 通过(打桩 fanout 避免真跑)
        async def _readonly_ok(payload):
            return True, []

        import app.services.integration_runner as _ir
        orig_fn = _ir.is_scenario_read_only
        _ir.is_scenario_read_only = _readonly_ok
        try:
            import app.services.run_dispatcher as _rd

            async def _fake(db_factory, execution_id, **kw):
                await _rd.transition_with_retry(
                    db_factory, execution_id, STATUS_DONE)

            orig_fan = _rd._fanout
            _rd._fanout = _fake
            try:
                r = await client.post("/api/runs", headers=_gic(token), json={
                    "scenarioId": "sc-m2-pub"})
                assert r.status_code == 201, r.text
                # 属主私有 → 通过
                r = await client.post("/api/runs", headers=_gic(token), json={
                    "scenarioId": "sc-m2-own"})
                assert r.status_code == 201, r.text
                # 他人私有 → 403
                r = await client.post("/api/runs", headers=_gic(token), json={
                    "scenarioId": "sc-m2-priv"})
                assert r.status_code == 403, r.text
                assert r.json()["detail"]["code"] == "platform_scope_denied"
            finally:
                _rd._fanout = orig_fan
        finally:
            _ir.is_scenario_read_only = orig_fn

    async def test_team_shared_alias_private_denied(self, client):
        await _seed_platform_user()
        await _seed_alias("agent-team")     # owner_user_id 空
        h = await _register(client, "m2_owner2")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-m2-team", steps=[GET_STEP]))
        token = await _mk_credential("agent-team")
        r = await client.post("/api/runs", headers=_gic(token), json={
            "scenarioId": "sc-m2-team"})
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "platform_scope_denied"

    async def test_register_task_scope_matrix(self, client):
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "m2_reg")
        h_other = await _register(client, "m2_reg_other")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-m2-ro", steps=[GET_STEP]))
        await client.post("/api/scenarios", headers=h_other, json=_draft(
            "sc-m2-rp", steps=[GET_STEP]))
        token = await _mk_credential()
        # 他人私有 → 403 platform_scope_denied
        r = await client.post("/api/integration/tasks", headers=_gic(token),
                              json={"name": "x", "scenarioId": "sc-m2-rp",
                                    "identityMode": "platform"})
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "platform_scope_denied"
        # 别名属主自己的 → 201
        await _own_alias("agent-sys", "m2_reg")
        r = await client.post("/api/integration/tasks", headers=_gic(token),
                              json={"name": "ok", "scenarioId": "sc-m2-ro",
                                    "identityMode": "platform"})
        assert r.status_code == 201, r.text

    async def test_run_instance_scope_recheck_pauses(self, client):
        """运行前重查:场景转私有后入站注册的平台任务 → 暂停
        scope_denied 并写 integration.paused 投递行。"""
        await _seed_platform_user()
        await _seed_alias()
        await _register(client, "m2_run")
        h_other = await _register(client, "m2_run_other")
        await client.post("/api/scenarios", headers=h_other, json=_draft(
            "sc-m2-scope", steps=[GET_STEP]))
        await _publish("sc-m2-scope")
        token = await _mk_credential()
        r = await client.post("/api/integration/tasks", headers=_gic(token),
                              json={"name": "s", "scenarioId": "sc-m2-scope",
                                    "identityMode": "platform"})
        assert r.status_code == 201, r.text
        tid = r.json()["id"]
        # 场景转私有 → 范围失效
        async with db_module.SessionLocal() as s:
            from app.models.composer_scenario import ComposerScenario
            scen = (await s.execute(sa.select(ComposerScenario).where(
                ComposerScenario.scenario_id == "sc-m2-scope"))).scalar_one()
            scen.visibility = "private"
            inst = (await s.execute(sa.select(IntegrationTask).where(
                IntegrationTask.template_id == tid))).scalars().one()
            inst.state = "running"
            inst.running_since = datetime.now(timezone.utc)
            await s.commit()
            iid = inst.id
        await ir.run_instance(iid, lease=None)
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, iid)
            assert inst.state == "paused"
            assert inst.paused_reason == "scope_denied"
            assert inst.run_status == "auth"
            rows = (await s.execute(sa.select(WebhookDelivery).where(
                WebhookDelivery.instance_id == iid))).scalars().all()
            assert len(rows) == 1
            body = json.loads(rows[0].body)
            assert body["event"] == "integration.paused"
            assert body["reason"] == "scope_denied"

    async def test_jwt_platform_task_unaffected(self, client):
        """JWT 建的平台任务(caller 为空)不受 M2 运行前重查影响。"""
        await _seed_platform_user()
        h = await _register(client, "m2_jwt")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-m2-jwt", steps=[GET_STEP]))
        r = await client.post("/api/integration/tasks", headers=h, json={
            "name": "j", "scenarioId": "sc-m2-jwt",
            "identityMode": "platform"})
        assert r.status_code == 201, r.text
        async with db_module.SessionLocal() as s:
            tpl = (await s.execute(sa.select(IntegrationTask).where(
                IntegrationTask.template_id.is_(None),
                IntegrationTask.name == "j"))).scalar_one()
            assert tpl.caller_alias_name is None

    async def test_patch_task_alias_gate(self, client):
        """别名 B 修改别名 A 的任务 → 404;A 改自己的 → 200;
        admin JWT 改 → 200。"""
        await _seed_platform_user()
        await _seed_alias("agent-a")
        await _seed_alias("agent-b")
        h = await _register(client, "m2_patch")
        await _own_alias("agent-a", "m2_patch")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-m2-patch", steps=[GET_STEP]))
        ta = await _mk_credential("agent-a")
        tb = await _mk_credential("agent-b")
        r = await client.post("/api/integration/tasks", headers=_gic(ta),
                              json={"name": "pa", "scenarioId": "sc-m2-patch",
                                    "identityMode": "platform"})
        assert r.status_code == 201, r.text
        tid = r.json()["id"]
        # 别名 B PATCH → 404(不泄露存在性)
        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=_gic(tb), json={"name": "hijack"})
        assert r.status_code == 404, r.text
        # 别名 A PATCH 自己的 → 200
        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=_gic(ta), json={"name": "ok-a"})
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "ok-a"
        # admin JWT → 200(维持既有管理权)
        await _promote("m2_patch")
        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=h, json={"name": "by-admin"})
        assert r.status_code == 200, r.text
