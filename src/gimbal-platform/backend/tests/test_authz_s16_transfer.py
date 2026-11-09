"""M2a S1.6(S1-e)转移维护者:四类公共项目对象 × 门矩阵 / 受让人校验 /
写权交接 / 模板连带 / 删用户联动(公共内容默认受让人 = 执行 Admin)。"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import make_draft, role_headers


async def _uid(client: AsyncClient, h_roster: dict, username: str) -> int:
    # 直查 DB:roster 端点排除调用者本人,查自己会 StopIteration
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.user import User

    async with db_module.SessionLocal() as db:
        return (await db.execute(sa_select(User.id).where(
            User.username == username))).scalar_one()


async def _row(model, **filt):
    from sqlalchemy import select as sa_select

    from app.core import db as db_module

    async with db_module.SessionLocal() as db:
        return (await db.execute(
            sa_select(model).filter_by(**filt))).scalar_one_or_none()


class TestScenarioTransfer:
    async def _publish(self, client, h, sid):
        r = await client.post("/api/scenarios", headers=h,
                              json=make_draft(sid))
        assert r.status_code in (200, 201), r.text
        assert (await client.post(
            f"/api/scenarios/{sid}/publish", headers=h)).status_code == 200

    async def test_gates_and_handover(self, client: AsyncClient):
        h_m = await role_headers(client, "s16_m", role="user")
        h_new = await role_headers(client, "s16_new", role="user")
        h_out = await role_headers(client, "s16_out", role="user")
        h_adm = await role_headers(client, "s16_adm", role="super_admin")
        await self._publish(client, h_m, "sc-s16-t")
        new_uid = await _uid(client, h_adm, "s16_new")

        # 路人(公共读者)→ 403;受让人无效(不存在)→ 422
        r = await client.post("/api/scenarios/sc-s16-t-public/transfer",
                              headers=h_out, json={"toUserId": new_uid})
        assert r.status_code == 403, r.text
        r = await client.post("/api/scenarios/sc-s16-t-public/transfer",
                              headers=h_m, json={"toUserId": 99999})
        assert r.status_code == 422, r.text

        # 维护者本人 → 200;owner_id 交接;写权随之转移
        r = await client.post("/api/scenarios/sc-s16-t-public/transfer",
                              headers=h_m, json={"toUserId": new_uid})
        assert r.status_code == 200, r.text
        from app.models.composer_scenario import ComposerScenario

        row = await _row(ComposerScenario, scenario_id="sc-s16-t-public")
        assert row.owner_id == new_uid
        # 原维护者再转移 → 403;新维护者可;Admin+ 也可
        r = await client.post("/api/scenarios/sc-s16-t-public/transfer",
                              headers=h_m, json={"toUserId": new_uid})
        assert r.status_code in (403, 422), r.text  # 非维护者 403
        h2 = await role_headers(client, "s16_third", role="user")
        third = await _uid(client, h_adm, "s16_third")
        r = await client.post("/api/scenarios/sc-s16-t-public/transfer",
                              headers=h_adm, json={"toUserId": third})
        assert r.status_code == 200, r.text
        r = await client.post("/api/scenarios/sc-s16-t-public/transfer",
                              headers=h2, json={"toUserId": new_uid})
        assert r.status_code == 200, r.text

        # 通知与动态流(from/to)
        from sqlalchemy import select as sa_sel

        from app.core import db as db_module
        from app.models.activity_event import ActivityEvent
        from app.models.permission import Notification

        async with db_module.SessionLocal() as db:
            acts = (await db.execute(sa_sel(ActivityEvent).where(
                ActivityEvent.kind
                == "scenario.maintainer_transferred"))).scalars().all()
            assert len(acts) >= 3
            assert {"fromUserId", "toUserId"} <= set(acts[0].detail)
            notes = (await db.execute(sa_sel(Notification).where(
                Notification.type == "maintenance_transferred"))).all()
            assert len(notes) >= 4  # 每次转移新旧各一(best-effort)

    async def test_private_object_not_applicable(self, client):
        h = await role_headers(client, "s16_pv", role="user")
        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-s16-pv"))
        r = await client.post("/api/scenarios/sc-s16-pv/transfer",
                              headers=h, json={"toUserId": 1})
        assert r.status_code == 404, r.text


class TestSuiteAndReportTransfer:
    async def test_suite_transfer(self, client):
        h_m = await role_headers(client, "s16_sm", role="user")
        h_new = await role_headers(client, "s16_snew", role="user")
        h_adm = await role_headers(client, "s16_sadm", role="admin")
        await client.post("/api/scenarios", headers=h_m,
                          json=make_draft("sc-s16-su"))
        r = await client.post("/api/suites", headers=h_m,
                              json={"name": "s16-suite", "description": ""})
        suite_id = r.json()["suiteId"]
        assert (await client.post(
            "/api/scenarios/sc-s16-su/publish", headers=h_m)).status_code == 200
        r = await client.post(f"/api/suites/{suite_id}/publish", headers=h_m)
        assert r.status_code == 200, r.text
        copy_id = r.json()["suiteId"]
        new_uid = await _uid(client, h_adm, "s16_snew")

        r = await client.post(f"/api/suites/{copy_id}/transfer",
                              headers=h_m, json={"toUserId": new_uid})
        assert r.status_code == 200, r.text
        from app.models.suite import Suite

        row = await _row(Suite, id=copy_id)
        assert row.owner_id == new_uid

    async def test_report_definition_transfer(self, client):
        from app.models.report_definition import ReportDefinitionRow

        h_m = await role_headers(client, "s16_rm", role="user")
        h_new = await role_headers(client, "s16_rnew", role="user")
        h_adm = await role_headers(client, "s16_radm", role="admin")
        await role_headers(client, "s16_rnew2", role="user")
        new_uid = await _uid(client, h_adm, "s16_rnew")
        # 建公共定义(建即公开快捷方式,入公共项目)
        r = await client.post("/api/report-definitions", headers=h_m, json={
            "name": "s16-rd", "description": "",
            "selection": {}, "projection": {}, "public": True})
        assert r.status_code in (200, 201), r.text
        did = r.json()["id"]

        r = await client.post(f"/api/report-definitions/{did}/transfer",
                              headers=h_m, json={"toUserId": new_uid})
        assert r.status_code == 200, r.text
        row = await _row(ReportDefinitionRow, id=did)
        assert row.owner_id == new_uid


class TestIntegrationTemplateTransfer:
    async def test_transfer_unbinds_token_and_clears_own_instances(
            self, client):
        from app.models.integration_task import IntegrationTask

        h_m = await role_headers(client, "s16_im", role="user")
        h_new = await role_headers(client, "s16_inew", role="user")
        h_sub = await role_headers(client, "s16_isub", role="user")
        h_adm = await role_headers(client, "s16_iadm", role="admin")
        # 场景发布 → 公共模板引用副本
        await client.post("/api/scenarios", headers=h_m,
                          json=make_draft("sc-s16-ig"))
        from tests.inbound_fixtures import publish_scenario

        publish_sid = await publish_scenario("sc-s16-ig")
        r = await client.post("/api/integration/tasks", headers=h_m, json={
            "name": "s16-tpl", "scenarioId": publish_sid,
            "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
            "visibility": "public"})
        assert r.status_code == 201, r.text
        tid = r.json()["id"]
        # 订阅者建实例(fingerprint 取自摘要,与显式订阅入口同款)
        fp = (await client.get(
            f"/api/integration/tasks/{tid}/subscription-summary",
            headers=h_sub)).json()["fingerprint"]
        r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                              headers=h_sub, json={"fingerprint": fp})
        assert r.status_code == 200, r.text

        new_uid = await _uid(client, h_adm, "s16_inew")
        tpl = await _row(IntegrationTask, id=tid)
        r = await client.post(f"/api/integration/tasks/{tid}/transfer",
                              headers=h_m, json={"toUserId": new_uid})
        assert r.status_code == 200, r.text

        tpl = await _row(IntegrationTask, id=tid)
        assert tpl.owner_id == new_uid
        assert tpl.token_id is None, "注册令牌应解绑(回调停发)"
        # 订阅实例保留;原维护者自有实例(创建即订阅)被清
        from sqlalchemy import select as sa_sel

        from app.core import db as db_module

        async with db_module.SessionLocal() as db:
            insts = (await db.execute(sa_sel(
                IntegrationTask.holder_id).where(
                IntegrationTask.template_id == tid))).scalars().all()
        assert insts == [await _uid(client, h_adm, "s16_isub")], insts


class TestDisposalDefaultPublicTransferee:
    async def test_public_content_defaults_to_executing_admin(
            self, client):
        from app.models.composer_scenario import ComposerScenario
        from app.models.suite import Suite

        h_adm = await role_headers(client, "s16_dadm", role="super_admin")
        h_victim = await role_headers(client, "s16_dv", role="user")
        h_keeper = await role_headers(client, "s16_dk", role="user")
        adm_uid = await _uid(client, h_adm, "s16_dadm")
        keeper_uid = await _uid(client, h_adm, "s16_dk")
        victim_uid = await _uid(client, h_adm, "s16_dv")

        # 公共副本 + 私有原件 + 私有 suite
        await client.post("/api/scenarios", headers=h_victim,
                          json=make_draft("sc-s16-dp"))
        await client.post("/api/scenarios", headers=h_victim,
                          json=make_draft("sc-s16-dv"))
        assert (await client.post(
            "/api/scenarios/sc-s16-dp/publish",
            headers=h_victim)).status_code == 200
        r = await client.post("/api/suites", headers=h_victim,
                              json={"name": "s16-dsuite", "description": ""})
        assert r.status_code == 201

        r = await client.request(
            "DELETE", f"/api/users/{victim_uid}", headers=h_adm,
            json={"disposal": "transfer", "transfer_to": keeper_uid})
        assert r.status_code in (200, 204), r.text

        pub = await _row(ComposerScenario, scenario_id="sc-s16-dp-public")
        prv = await _row(ComposerScenario, scenario_id="sc-s16-dv")
        assert pub.owner_id == adm_uid, "公共内容默认转给执行删除的 Admin"
        assert prv.owner_id == keeper_uid

    async def test_public_transfer_to_override(self, client):
        from app.models.composer_scenario import ComposerScenario

        h_adm = await role_headers(client, "s16_oadm", role="super_admin")
        h_victim = await role_headers(client, "s16_ov", role="user")
        h_pub_to = await role_headers(client, "s16_op", role="user")
        h_keeper = await role_headers(client, "s16_ok", role="user")
        adm_uid = await _uid(client, h_adm, "s16_oadm")
        pub_uid = await _uid(client, h_adm, "s16_op")
        keeper_uid = await _uid(client, h_adm, "s16_ok")
        victim_uid = await _uid(client, h_adm, "s16_ov")

        await client.post("/api/scenarios", headers=h_victim,
                          json=make_draft("sc-s16-op"))
        assert (await client.post(
            "/api/scenarios/sc-s16-op/publish",
            headers=h_victim)).status_code == 200
        r = await client.request(
            "DELETE", f"/api/users/{victim_uid}", headers=h_adm,
            json={"disposal": "transfer", "transfer_to": keeper_uid,
                  "public_transfer_to": pub_uid})
        assert r.status_code in (200, 204), r.text
        pub = await _row(ComposerScenario, scenario_id="sc-s16-op-public")
        assert pub.owner_id == pub_uid
