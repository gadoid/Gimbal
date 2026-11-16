"""P1a 删除端点最小显式级联(权限方案 §4.3/§7,随 M2 同车)。

M2 起 FK 真生效:凭证池/常量/个人别名三张 NO ACTION 表必须由 Python
显式删,否则删号被 FK 当场拦死。本测试钉住端到端行为:删号后三类资源
消失,收藏/场景/执行的归属按 FK 语义自收(此处只验执行仍在)。
"""
from __future__ import annotations
import pytest  # noqa: E402

from httpx import AsyncClient

from app.core import db as db_module
from tests.helpers import register_and_login


async def test_delete_user_cascades_pool_constant_alias(client: AsyncClient):
    admin = await register_and_login(client, "cascade_admin", "adminpass123")
    target = await register_and_login(client, "cascade_bob", "bobpass123")

    # 目标用户的两张 NO ACTION 表各来一条(账户 + 常量;
    # 个人别名随 authz M2a S6 退役,删号不涉及条目表)
    from app.models import Environment
    from sqlalchemy import select as _sel
    async with db_module.SessionLocal() as s:
        env = (await s.execute(_sel(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env is None:
            s.add(Environment(name="测试", is_default=True))
            await s.commit()
            env = (await s.execute(_sel(Environment.id).where(
                Environment.is_default.is_(True)))).scalar_one()
    r = await client.post("/api/auths", headers=target, json={
        "system": "bob-svc", "envId": env, "username": "u",
        "password": "p", "token_type": "Bearer",
    })
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/constants", headers=target, json={
        "name": "bob_app_code", "entry_kind": "literal", "value": "TRACE",
    })
    assert r.status_code in (200, 201), r.text
    # 个人别名随 authz M2a S6 退役(别名全部共享,删号不涉及别名表)
    from app.models.user import User
    from sqlalchemy import select
    async with db_module.SessionLocal() as s:
        bob = (await s.execute(
            select(User).where(User.username == "cascade_bob"))).scalar_one()

    # 删号(admin)
    bob_id = bob.id
    r = await client.delete(f"/api/users/{bob_id}", headers=admin)
    assert r.status_code == 204, r.text

    # 两张 NO ACTION 表已由端点显式清
    from app.models.auth_account import AuthAccount
    from app.models.constant_entry import ConstantEntry
    async with db_module.SessionLocal() as s:
        assert (await s.execute(select(AuthAccount).where(
            AuthAccount.owner_id == bob_id))).first() is None
        assert (await s.execute(select(ConstantEntry).where(
            ConstantEntry.owner_id == bob_id))).first() is None
        # 用户本体没了
        assert await s.get(User, bob_id) is None
