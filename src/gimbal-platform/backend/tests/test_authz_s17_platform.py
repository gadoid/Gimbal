"""M2a S1.7 平台模板(D8-D10):is_platform_template 判定收编 _can_manage、
platformize 入口、删用户软删模板直接删、purge 平台模板拦截闸。"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import make_draft, role_headers


async def _uid(username: str) -> int:
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


async def _mk_public_tpl(client, h_owner, sid: str, name: str) -> int:
    """建场景 → 发布(= 复制)→ 建公共模板引用副本 → 返回模板 id。"""
    from tests.inbound_fixtures import publish_scenario

    r = await client.post("/api/scenarios", headers=h_owner,
                          json=make_draft(sid))
    assert r.status_code in (200, 201), r.text
    copy_sid = await publish_scenario(sid)
    r = await client.post("/api/integration/tasks", headers=h_owner, json={
        "name": name, "scenarioId": copy_sid,
        "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
        "visibility": "public"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


class TestPlatformize:
    async def test_gates_and_idempotent(self, client: AsyncClient):
        h_own = await role_headers(client, "s17_pz", role="user")
        h_usr = await role_headers(client, "s17_pu", role="user")
        h_adm = await role_headers(client, "s17_pa", role="admin")
        tid = await _mk_public_tpl(client, h_own, "sc-s17-pz", "s17-tpl")

        # 普通用户(即使属主)→ 403;Admin+ → 200 置标记;幂等
        r = await client.post(f"/api/integration/tasks/{tid}/platformize",
                              headers=h_usr)
        assert r.status_code == 403, r.text
        r = await client.post(f"/api/integration/tasks/{tid}/platformize",
                              headers=h_adm)
        assert r.status_code == 200, r.text
        from app.models.integration_task import IntegrationTask

        tpl = await _row(IntegrationTask, id=tid)
        assert tpl.is_platform_template is True
        r = await client.post(f"/api/integration/tasks/{tid}/platformize",
                              headers=h_adm)
        assert r.status_code == 200, r.text

    async def test_private_template_422(self, client: AsyncClient):
        h_own = await role_headers(client, "s17_pv", role="user")
        h_adm = await role_headers(client, "s17_pva", role="admin")
        await client.post("/api/scenarios", headers=h_own,
                          json=make_draft("sc-s17-pv"))
        r = await client.post("/api/integration/tasks", headers=h_own, json={
            "name": "s17-priv", "scenarioId": "sc-s17-pv",
            "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
            "visibility": "private"})
        assert r.status_code == 201, r.text
        tid = r.json()["id"]
        r = await client.post(f"/api/integration/tasks/{tid}/platformize",
                              headers=h_adm)
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "scenario_not_public"


class TestPlatformTemplateManage:
    async def test_admin_manages_via_flag_not_owner(self, client):
        """Admin+ 经 is_platform_template 标记维护平台模板;**非平台**的
        公共模板(哪怕属主恰是 __platform__ 形态)不再走属主误判 ——
        D10:软删挂靠行与平台模板靠显式标记区分。"""
        from app.models.integration_task import IntegrationTask

        h_own = await role_headers(client, "s17_mm", role="user")
        h_adm = await role_headers(client, "s17_ma", role="admin")
        h_usr = await role_headers(client, "s17_mu", role="user")
        tid = await _mk_public_tpl(client, h_own, "sc-s17-mm", "s17-mtpl")
        assert (await client.post(
            f"/api/integration/tasks/{tid}/platformize",
            headers=h_adm)).status_code == 200

        # Admin+ 可改平台模板;普通用户 403
        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=h_adm,
                               json={"name": "平台改名"})
        assert r.status_code == 200, r.text
        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=h_usr,
                               json={"name": "偷改"})
        assert r.status_code == 403, r.text
        # 平台模板恒公共(转私有 409)
        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=h_adm, json={"visibility": "private"})
        assert r.status_code == 409, r.text

        # 非平台模板:属主恰为系统用户也不给 Admin+ 维护权(标记判定)
        from sqlalchemy import select as sa_sel, text as sa_text, update as _upd

        from app.core import db as db_module

        async with db_module.SessionLocal() as db:
            # 测试库走 create_all 不跑迁移(0015 才种 __platform__)→ 补种
            await db.execute(sa_text(
                "INSERT INTO users (username, display_name, password_hash, "
                "role, is_system, is_active, created_at, updated_at) "
                "SELECT '__platform__', '平台系统', 'x', 'user', true, "
                "true, now(), now() WHERE NOT EXISTS ("
                "  SELECT 1 FROM users WHERE username='__platform__')"))
            await db.commit()
            plat_id = (await db.execute(sa_text(
                "SELECT id FROM users WHERE username='__platform__'"
            ))).scalar()
            await db.execute(_upd(IntegrationTask).where(
                IntegrationTask.id == tid
            ).values(is_platform_template=False, owner_id=plat_id))
            await db.commit()
        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=h_adm, json={"name": "挂靠误判"})
        assert r.status_code == 403, f"D10:挂靠形态 ≠ 平台模板: {r.text}"


class TestDisposalSoftDeletedTemplates:
    async def test_soft_deleted_templates_deleted_not_attached(
            self, client):
        """D10:删用户时其软删模板直接删除 —— 不再兜底挂到
        __platform__(挂靠行会污染平台模板判定)。"""
        from app.models.integration_task import IntegrationTask

        h_adm = await role_headers(client, "s17_da", role="super_admin")
        h_victim = await role_headers(client, "s17_dv", role="user")
        tid = await _mk_public_tpl(client, h_victim, "sc-s17-dv", "s17-dtpl")
        # 软删(属主删除自己模板)
        r = await client.delete(f"/api/integration/tasks/{tid}",
                                headers=h_victim)
        assert r.status_code == 200, r.text

        victim_uid = await _uid("s17_dv")
        r = await client.request(
            "DELETE", f"/api/users/{victim_uid}", headers=h_adm,
            json={"disposal": "purge"})
        assert r.status_code in (200, 204), r.text

        tpl = await _row(IntegrationTask, id=tid)
        assert tpl is None, "软删模板应随用户删除,不再挂 __platform__"

    async def test_purge_blocked_by_platform_template_reference(
            self, client):
        """D8 拦截闸:purge 删除被平台模板引用的场景 → 409 列出模板。"""
        h_own = await role_headers(client, "s17_gr", role="user")
        h_adm = await role_headers(client, "s17_ga", role="super_admin")
        tid = await _mk_public_tpl(client, h_own, "sc-s17-gr", "s17-gtpl")
        assert (await client.post(
            f"/api/integration/tasks/{tid}/platformize",
            headers=h_adm)).status_code == 200

        victim_uid = await _uid("s17_gr")
        r = await client.request(
            "DELETE", f"/api/users/{victim_uid}", headers=h_adm,
            json={"disposal": "purge"})
        assert r.status_code == 409, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "platform_template_references"
        assert any(t["id"] == tid for t in detail["templates"])

