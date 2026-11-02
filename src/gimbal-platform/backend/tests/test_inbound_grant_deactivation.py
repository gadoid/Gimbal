"""S1 修复(修复方案 2026-11-01 §3):停用用户即撤销其名下 grant。

停用后认证分流不再以其身份执行(此前 grant 未撤、定时任务继续跑);
认证时另查签发人活跃度作兜底(`grant_user_inactive`)。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import User
from app.models.inbound_identity import InboundGrant
from app.models.permission import AuditLog

from .inbound_fixtures import (
    seed_alias as _seed_alias, seed_platform_user as _seed_platform_user,
)
from .test_inbound_identity import (
    _gic, _mk_credential, _mk_grant, _promote, _register, _set_role,
    _user_id,
)


class TestS1Deactivation:
    async def test_deactivate_revokes_grants_and_audits(self, client):
        await _seed_platform_user()
        await _seed_alias()
        h_admin = await _register(client, "s1_admin")
        await _promote("s1_admin")
        h_user = await _register(client, "s1_user")
        await _set_role("s1_user", "member")     # 签发 grant 须 member+
        uid = await _user_id("s1_user")
        r = await client.post("/api/service-aliases/agent-sys/grants",
                              headers=h_user, json={})
        assert r.status_code == 201
        gid = r.json()["id"]
        grant_token = r.json()["token"]     # 明文只此一次,留着验证撤销后 403
        # 停用
        r = await client.patch(f"/api/users/{uid}", headers=h_admin,
                               json={"is_active": False})
        assert r.status_code == 200, r.text
        async with db_module.SessionLocal() as s:
            g = await s.get(InboundGrant, gid)
            assert g.revoked_at is not None
            n = (await s.execute(sa.select(sa.func.count()).where(
                AuditLog.action
                == "inbound.grant_revoked_by_deactivation"))).scalar_one()
            assert n == 1
        # 认证分流:被撤销的 grant 令牌 → 403
        token = await _mk_credential()
        r = await client.get("/api/executions",
                             headers=_gic(token, grant_token))
        assert r.status_code == 403
        assert "grant_invalid" in r.text
        # 重新启用**不**恢复 grant
        r = await client.patch(f"/api/users/{uid}", headers=h_admin,
                               json={"is_active": True})
        assert r.status_code == 200
        async with db_module.SessionLocal() as s:
            g = await s.get(InboundGrant, gid)
            assert g.revoked_at is not None

    async def test_inactive_issuer_blocks_grant(self, client):
        """纵深防御:grant 未撤销但签发人停用 → 认证 403。"""
        await _seed_platform_user()
        await _seed_alias()
        await _register(client, "s1_issuer")
        uid = await _user_id("s1_issuer")
        grant = await _mk_grant("agent-sys", uid)
        token = await _mk_credential()
        async with db_module.SessionLocal() as s:
            u = await s.get(User, uid)
            u.is_active = False
            await s.commit()
        r = await client.get("/api/executions", headers=_gic(token, grant))
        assert r.status_code == 403
        assert "grant_user_inactive" in r.text
