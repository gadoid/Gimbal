"""访问令牌(webhook v4)测试共用种子。

只放跨测试模块复用的直插种子与请求助手;单模块专用助手留在各自文件。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import hash_password
from app.models import Execution, User
from app.models.access_token import AccessToken, AccessTokenScope
from app.models.integration_task import IntegrationTask
from app.models.service_alias import ServiceAlias
from app.models.webhook_delivery import WebhookDelivery
from app.services import access_token as at_svc


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
    """别名本体(base_url + 可选凭证默认);入站/回调列已随 v4 退役。"""
    row = ServiceAlias(
        alias_name=name, base_service="pay-service", kind="external",
        base_url="https://cb.example.local")
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


async def mk_user(username: str, *, role: str = "admin") -> int:
    """直插一个活跃真人用户(幂等;不经注册接口,免 admin 提权副作用)。"""
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.select(User.id).where(
            User.username == username))).scalar_one_or_none()
        if uid is not None:
            return uid
        u = User(username=username, display_name=username,
                 password_hash=hash_password("x"), role=role)
        s.add(u)
        await s.commit()
        return u.id


async def mk_token(
    *, kind: str = "personal", name: str = "t", user_id: int | None = None,
    days: int = 30, revoked=False, invalidated=False,
    invalidate_reason: str = "password", scope_aliases=(), scope_auths=(),
    callback_url: str | None = None, callback_secret: str | None = None,
) -> "tuple[int, str]":
    """直插一张令牌 + 范围行,返回 (id, 明文)。"""
    plaintext = at_svc.generate_plaintext()
    now = datetime.now(timezone.utc)
    if user_id is None:
        raise ValueError("token needs user_id (authz C1:platform 夹具退役)")
    async with db_module.SessionLocal() as s:
        tok = AccessToken(
            user_id=user_id, kind=kind, name=name,
            token_hash=at_svc.sha256_hex(plaintext),
            token_hint=at_svc.token_hint_of(plaintext),
            expires_at=now + timedelta(days=days),
            revoked_at=now if revoked else None,
            invalidated_at=now if invalidated else None,
            invalidated_reason=invalidate_reason if invalidated else None,
            callback_url=callback_url,
            callback_secret=(
                at_svc.encrypt_secret(callback_secret)
                if callback_secret else None))
        s.add(tok)
        await s.flush()
        for alias in scope_aliases:
            s.add(AccessTokenScope(token_id=tok.id, alias_name=alias))
        for aid in scope_auths:
            s.add(AccessTokenScope(token_id=tok.id, auth_id=aid))
        await s.commit()
        return tok.id, plaintext


async def mk_execution(*, token_id=None, status="running", total=1,
                       **over) -> int:
    async with db_module.SessionLocal() as s:
        owner_id = (await s.execute(sa.select(User.id).where(
            User.is_system == True))).scalar()  # noqa: E712
        ex = Execution(scenario_id="sc-w", scenario_name="W",
                       owner_id=owner_id, owner_name="平台系统",
                       status=status, total_runs=total,
                       token_id=token_id, config_json={}, **over)
        s.add(ex)
        await s.commit()
        return ex.id


async def mk_task_pair(*, name="w-task", token_id=None,
                       owner_id=None, scenario_id="sc-w") -> "tuple[int, int, int]":
    """(tpl_id, inst_id, owner_id);holder = 模板 owner(注册方自己的实例)。"""
    async with db_module.SessionLocal() as s:
        if owner_id is None:
            owner = (await s.execute(sa.select(User.id).where(
                User.is_system == False))).scalar()  # noqa: E712
            if owner is None:
                u = User(username="w_owner", display_name="o",
                         password_hash=hash_password("x"), role="admin")
                s.add(u)
                await s.commit()
                owner = u.id
            owner_id = owner
        holder = owner_id
        tpl = IntegrationTask(name=name, owner_id=owner_id,
                              scenario_id=scenario_id, token_id=token_id)
        s.add(tpl)
        await s.flush()
        inst = IntegrationTask(
            name=name, owner_id=owner_id, template_id=tpl.id,
            holder_id=holder, state="running",
            running_since=datetime.now(timezone.utc))
        s.add(inst)
        await s.commit()
        return tpl.id, inst.id, owner_id


async def mk_pending(**over) -> int:
    row = WebhookDelivery(
        token_id=over.get("token_id"),
        token_name=over.get("token_name", "t"),
        event_type=over.get("event_type", "execution.finished"),
        url=over.get("url", "https://cb.example.local/gimbal/callback"),
        body=over.get("body", '{"event":"execution.finished"}'),
        status="pending", attempts=0)
    async with db_module.SessionLocal() as s:
        s.add(row)
        await s.commit()
        return row.id


def allow_delivery_hosts(monkeypatch, allowlist: str | None = None) -> None:
    """投递面测试放行:D16 投递时白名单复核(评审 2026-11-05 P1)后,
    直插的投递行 URL 也要过投递面白名单 —— 默认放开全部测试主机
    (*.example / *.example.com / *.example.local);私址解析打桩放行
    (沙箱无外网 DNS,真实解析一律 fail-closed 拒)。"""
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "CALLBACK_HOST_ALLOWLIST",
        allowlist if allowlist is not None
        else "*.example,*.example.com,*.example.local")

    async def _not_private(host: str) -> bool:
        return False

    monkeypatch.setattr(at_svc, "host_is_private", _not_private)


async def deliveries() -> "list[WebhookDelivery]":
    async with db_module.SessionLocal() as s:
        return list((await s.execute(
            sa.select(WebhookDelivery).order_by(WebhookDelivery.id))
        ).scalars().all())


def body_of(row: WebhookDelivery) -> dict:
    return json.loads(row.body)
