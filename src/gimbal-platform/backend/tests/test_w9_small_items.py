"""authz W9 小项(dev-plan §九):三项不一致/缺口的回归钉。

① suite 版本分布接口补读闸(:1652 —— 此前任何登录用户可读他人私有
   suite 的成员清单与版本线);
② 环境写操作补审计(W9-3;连带 :52 越属主判定收编表 A users.manage);
③ 系统公告归 Admin+(待定项 7:运维面 → ops.write;原 users.manage
   收窄过度)。
报告定义维护者制(W9-2)的用例在 test_authz_matrix_b 与
test_report_definitions。
"""
from __future__ import annotations

from datetime import datetime, timezone

from httpx import AsyncClient

from tests.helpers import role_headers


async def _mk_user_id(name: str) -> int:
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.user import User

    async with db_module.SessionLocal() as s:
        return (await s.execute(sa_select(User.id).where(
            User.username == name))).scalar_one()


# ── ① 版本分布读闸 ────────────────────────────────────────────────
async def _mk_suite_with_units(client: AsyncClient, owner_h: dict) -> int:
    """直插 suite(mode_config.units 引用带 pin 版本线的场景)+ 场景。"""
    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    from app.models.suite import Suite

    owner_id = await _mk_user_id("vd_own")
    async with db_module.SessionLocal() as s:
        # name 是生成列(payload 派生),不直插
        s.add(ComposerScenario(
            scenario_id="sc-w9-vd", owner_id=owner_id,
            payload={"definition": {
                "meta": {"scenarioId": "sc-w9-vd", "name": "VD",
                         "plate": {"fin": "1.0#1"}},
                "steps": [], "config": {}}}))
        await s.flush()
        row = Suite(name="w9-vd", description="", owner_id=owner_id,
                    mode_config={"units": {"sc-w9-vd": {"ref": "a"}}})
        s.add(row)
        await s.commit()
        await s.refresh(row)
        return row.id


class TestVersionDistributionReadGate:
    async def test_gate_matrix(self, client: AsyncClient):
        """属主 200;无权限者 404(不泄露);公共 suite 全员 200。"""
        h_owner = await role_headers(client, "vd_own")
        sid = await _mk_suite_with_units(client, h_owner)

        # 属主可读(成员清单 + 版本线)
        r = await client.get(f"/api/suites/{sid}/version-distribution",
                             headers=h_owner)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["items"] and out["items"][0]["scenarioId"] == "sc-w9-vd"
        assert out["distribution"] == {"fin": {"1.0": 1}}

        # 无关用户(无引用、私有)→ 404
        h_other = await role_headers(client, "vd_oth", role="user")
        r = await client.get(f"/api/suites/{sid}/version-distribution",
                             headers=h_other)
        assert r.status_code == 404, r.text


# ── ② 环境写审计 ─────────────────────────────────────────────────
class TestEnvironmentsAudit:
    async def _audit_rows(self, env_id: int):
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.permission import AuditLog

        async with db_module.SessionLocal() as s:
            return (await s.execute(sa_select(AuditLog).where(
                AuditLog.action == "environment.write",
                AuditLog.resource_id == str(env_id))
            )).scalars().all()

    async def test_create_update_delete_audited(self, client: AsyncClient):
        h = await role_headers(client, "env_adm", role="admin")
        r = await client.post("/api/environments", headers=h, json={
            "name": "w9-env", "description": "", "lines": {"fin": "1.0"}})
        assert r.status_code in (200, 201), r.text
        env_id = r.json()["id"]

        rows = await self._audit_rows(env_id)
        assert [row.detail.get("op") for row in rows] == ["create"]

        r = await client.put(f"/api/environments/{env_id}", headers=h,
                             json={"description": "改"})
        assert r.status_code == 200, r.text
        rows = await self._audit_rows(env_id)
        assert sorted(row.detail.get("op") for row in rows) == [
            "create", "update"]

        r = await client.delete(f"/api/environments/{env_id}", headers=h)
        assert r.status_code == 204, r.text
        rows = await self._audit_rows(env_id)
        assert sorted(row.detail.get("op") for row in rows) == [
            "create", "delete", "update"]

    async def test_write_gate_ops_write_only(self, client: AsyncClient):
        """环境是团队共享配置(0044 删 visibility 的同一裁决):写面统一
        ops.write —— 另一 admin(非属主)可改;平台 user 仍 403。
        (2026-11-11 统一:原 PUT/DELETE 收 owner∨users.manage,与
        「建/设默认 = Admin+」同对象宽窄不一,且「能建不能改」不可用。)"""
        h_owner = await role_headers(client, "env_own", role="user")
        r = await client.post("/api/environments", headers=h_owner, json={
            "name": "w9-env2", "description": "", "lines": {}})
        # 创建面 = ops.write(MemberUser):user 被 403
        assert r.status_code == 403, r.text

        h_a1 = await role_headers(client, "env_a1", role="admin")
        r = await client.post("/api/environments", headers=h_a1, json={
            "name": "w9-env3", "description": "", "lines": {}})
        env_id = r.json()["id"]
        # 另一 admin(非属主)可改 —— 共享配置不认属主
        h_a2 = await role_headers(client, "env_a2", role="admin")
        r = await client.put(f"/api/environments/{env_id}", headers=h_a2,
                             json={"description": "x"})
        assert r.status_code == 200, r.text
        h_sup = await role_headers(client, "env_sup", role="super_admin")
        r = await client.put(f"/api/environments/{env_id}", headers=h_sup,
                             json={"description": "ok"})
        assert r.status_code == 200, r.text


# ── ③ 公告归 Admin+(待定项 7)───────────────────────────────────
class TestAnnouncementOwnership:
    async def test_admin_role_can_post_super_and_user_split(
            self, client: AsyncClient):
        # admin(原 member 级,ops.write)可发 —— 原门(users.manage)下不可
        h_adm = await role_headers(client, "ann_admr", role="admin")
        r = await client.post("/api/notifications/announcements",
                              headers=h_adm,
                              json={"title": "W9 公告", "body": "b",
                                    "hours": 1})
        assert r.status_code == 201, r.text

        # user 仍不可
        h_usr = await role_headers(client, "ann_usr", role="user")
        r = await client.post("/api/notifications/announcements",
                              headers=h_usr, json={"title": "x"})
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "capability_forbidden"
        assert r.json()["detail"]["capability"] == "ops.write"
