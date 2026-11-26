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
        "password": "pass1234", "token_type": "Bearer",  # ≥6 位:TOK-08a 掩码闸
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


async def test_publicize_notification_failure_keeps_disposal(
        client: AsyncClient, monkeypatch):
    """复核收口(2026-11-22):publicize 公示通知失败**不得** rollback
    吞掉此前处置写入 —— 旧码 rollback 后循环继续 + 末尾照常 commit =
    半处置状态落库。修后:通知失败按增强语义吞掉继续,模板删除照常
    落库(204);若真为 DB 级错误则事务中止、整端点失败(连贯)。"""
    from sqlalchemy import select as _sel

    from app.core import db as db_module
    from app.models.integration_task import IntegrationTask
    from app.models.user import User

    admin = await register_and_login(client, "pub_admin2", "adminpass123")
    target = await register_and_login(client, "pub_bob2", "bobpass123")
    holder = await register_and_login(client, "pub_holder", "holdpass123")

    async with db_module.SessionLocal() as s:
        tid = (await s.execute(_sel(User.id).where(
            User.username == "pub_bob2"))).scalar_one()
        hid = (await s.execute(_sel(User.id).where(
            User.username == "pub_holder"))).scalar_one()
        from tests.helpers import default_space_id

        tpl = IntegrationTask(name="pub-tpl-1", owner_id=tid,
                              project_id=await default_space_id(s, tid),
                              card_template="status")
        s.add(tpl)
        await s.flush()
        s.add(IntegrationTask(name="inst-1", owner_id=hid,
                              template_id=tpl.id, holder_id=hid,
                              card_template="status"))
        await s.commit()
        tpl_id = tpl.id

    async def _boom(*a, **kw):
        raise RuntimeError("notification backend down")

    monkeypatch.setattr(
        "app.services.notifications.create_notification", _boom)

    r = await client.request("DELETE", f"/api/users/{tid}", headers=admin,
                             json={"disposal": "publicize"})
    assert r.status_code == 204, r.text
    # 处置照常落库:模板与实例行随 publicize 删除(未被 rollback 吞掉)
    async with db_module.SessionLocal() as s:
        left = (await s.execute(_sel(IntegrationTask).where(
            IntegrationTask.id == tpl_id))).scalar_one_or_none()
        insts = (await s.execute(_sel(IntegrationTask).where(
            IntegrationTask.template_id == tpl_id))).scalars().all()
        assert left is None and insts == []
        # 用户行本身已删
        assert (await s.execute(_sel(User).where(
            User.id == tid))).scalar_one_or_none() is None
