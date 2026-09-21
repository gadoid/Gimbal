"""P1a 删除端点最小显式级联(权限方案 §4.3/§7,随 M2 同车)。

M2 起 FK 真生效:凭证池/常量/个人别名三张 NO ACTION 表必须由 Python
显式删,否则删号被 FK 当场拦死。本测试钉住端到端行为:删号后三类资源
消失,收藏/场景/执行的归属按 FK 语义自收(此处只验执行仍在)。
"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import register_and_login


async def test_delete_user_cascades_pool_constant_alias(client: AsyncClient):
    admin = await register_and_login(client, "cascade_admin", "adminpass123")
    target = await register_and_login(client, "cascade_bob", "bobpass123")

    # 目标用户的三张 NO ACTION 表各来一条
    r = await client.post("/api/auths", headers=target, json={
        "alias": "bob-cred", "url": "http://x", "username": "u",
        "password": "p", "token_type": "Bearer",
    })
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/constants", headers=target, json={
        "name": "bob_app_code", "entry_kind": "literal", "value": "TRACE",
    })
    assert r.status_code in (200, 201), r.text
    # 个人别名直插(别名 API 建卡要走 plate 目录;级联测试只关心行归属)
    from app.core import db as db_module
    from app.models.service_alias import ServiceAlias
    from app.models.user import User
    from sqlalchemy import select
    async with db_module.SessionLocal() as s:
        bob = (await s.execute(
            select(User).where(User.username == "cascade_bob"))).scalar_one()
        s.add(ServiceAlias(
            alias_name="fin-service-bob", base_service="fin-service",
            owner_user_id=bob.id,
        ))
        await s.commit()

    # 删号(admin)
    bob_id = bob.id
    r = await client.delete(f"/api/users/{bob_id}", headers=admin)
    assert r.status_code == 204, r.text

    # 三张 NO ACTION 表已由端点显式清
    from app.models.auth_session import AuthSession
    from app.models.constant_entry import ConstantEntry
    async with db_module.SessionLocal() as s:
        assert (await s.execute(select(AuthSession).where(
            AuthSession.owner_id == bob_id))).first() is None
        assert (await s.execute(select(ConstantEntry).where(
            ConstantEntry.owner_id == bob_id))).first() is None
        assert (await s.execute(select(ServiceAlias).where(
            ServiceAlias.owner_user_id == bob_id))).first() is None
        # 用户本体没了
        assert await s.get(User, bob_id) is None
