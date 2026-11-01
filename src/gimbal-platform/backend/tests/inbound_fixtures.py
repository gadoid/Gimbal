"""入站/回调修复轮共用种子(修复方案 2026-11-01)。

只放跨测试模块复用的直插种子与请求助手;单模块专用助手留在各自文件。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import hash_password
from app.models import Execution, User
from app.models.integration_task import IntegrationTask
from app.models.service_alias import ServiceAlias
from app.models.webhook_delivery import WebhookDelivery


async def seed_platform_user() -> int:
    async with db_module.SessionLocal() as db:
        uid = (await db.execute(
            sa.select(User.id).where(User.is_system == True)  # noqa: E712
        )).scalar()
        if uid is None:
            u = User(username="__platform__", display_name="平台系统",
                     password_hash=hash_password("x"), is_system=True)
            db.add(u)
            await db.commit()
            uid = u.id
    return uid


async def seed_alias(name: str = "agent-sys", **over) -> None:
    from app.core.security import fernet_encrypt
    row = ServiceAlias(
        alias_name=name, base_service="pay-service", kind="external",
        base_url="https://cb.example.local", inbound_enabled=True,
        callback_enabled=True, callback_path="/gimbal/callback",
        callback_secret=fernet_encrypt("cb-secret-1"))
    for k, v in over.items():
        setattr(row, k, v)
    async with db_module.SessionLocal() as s:
        s.add(row)
        await s.commit()


async def publish_scenario(scenario_id: str) -> None:
    """场景可见性是列(发布走独立端点),测试里直改。"""
    from app.models.composer_scenario import ComposerScenario
    async with db_module.SessionLocal() as s:
        row = (await s.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == scenario_id))).scalar_one()
        row.visibility = "public"
        await s.commit()


async def mk_user(username: str) -> int:
    """直插一个活跃真人用户(不经注册接口,免 admin 提权副作用)。"""
    async with db_module.SessionLocal() as s:
        u = User(username=username, display_name=username,
                 password_hash=hash_password("x"))
        s.add(u)
        await s.commit()
        return u.id


async def mk_execution(*, caller="agent-sys", grant_id=None,
                       status="running", total=1, **over) -> int:
    async with db_module.SessionLocal() as s:
        owner_id = (await s.execute(sa.select(User.id).where(
            User.is_system == True))).scalar()  # noqa: E712
        ex = Execution(scenario_id="sc-w", scenario_name="W",
                       owner_id=owner_id, owner_name="平台系统",
                       status=status, total_runs=total,
                       caller_alias_name=caller, grant_id=grant_id,
                       config_json={}, **over)
        s.add(ex)
        await s.commit()
        return ex.id


async def mk_task_pair(*, name="w-task") -> "tuple[int, int]":
    """(tpl_id, inst_id);holder = 模板 owner(注册方自己的实例)。"""
    async with db_module.SessionLocal() as s:
        owner = (await s.execute(sa.select(User.id).where(
            User.is_system == False))).scalar()  # noqa: E712
        if owner is None:
            u = User(username="w_owner", display_name="o",
                     password_hash=hash_password("x"))
            s.add(u)
            await s.commit()
            owner = u.id
        tpl = IntegrationTask(name=name, owner_id=owner,
                              identity_mode="personal", scenario_id="sc-w",
                              caller_alias_name="agent-sys")
        s.add(tpl)
        await s.flush()
        inst = IntegrationTask(
            name=name, owner_id=owner, template_id=tpl.id,
            holder_id=owner, state="running",
            running_since=datetime.now(timezone.utc))
        s.add(inst)
        await s.commit()
        return tpl.id, inst.id


async def mk_pending(**over) -> int:
    row = WebhookDelivery(
        alias_name=over.get("alias_name", "agent-sys"),
        event_type=over.get("event_type", "execution.finished"),
        url=over.get("url", "https://cb.example.local/gimbal/callback"),
        body=over.get("body", '{"event":"execution.finished"}'),
        status="pending", attempts=0)
    async with db_module.SessionLocal() as s:
        s.add(row)
        await s.commit()
        return row.id


async def deliveries() -> "list[WebhookDelivery]":
    async with db_module.SessionLocal() as s:
        return list((await s.execute(
            sa.select(WebhookDelivery).order_by(WebhookDelivery.id))
        ).scalars().all())


def body_of(row: WebhookDelivery) -> dict:
    return json.loads(row.body)
