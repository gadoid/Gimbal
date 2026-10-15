"""注册开关 + 首个 admin 引导 + 密钥 fail-fast(整体评审 2026-10-15 #4/#5)。

关键回归:空库建库后 users 表恒有 0015 种下的 ``__platform__`` 系统用户
(is_system=True)。旧实现按 ``count(users)==0`` 判首个注册者,上线空库
上永不成立 → 首个注册者拿不到 admin、全站无 admin。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.core.config import settings
from app.models.user import User


async def _seed_system_user() -> None:
    async with db_module.SessionLocal() as db:
        db.add(User(username="__platform__", display_name="__platform__",
                    password_hash="!", role="user", is_system=True))
        await db.commit()


def _reg(username: str) -> dict:
    return {"username": username, "password": "Passw0rd!123",
            "display_name": username.capitalize()}


async def test_first_human_becomes_admin_despite_system_user(client):
    await _seed_system_user()
    r = await client.post("/api/auth/register", json=_reg("alice"))
    assert r.status_code == 201, r.text
    async with db_module.SessionLocal() as db:
        alice = (await db.execute(
            select(User).where(User.username == "alice"))).scalar_one()
    assert alice.role == "admin"


async def test_registration_closed_after_bootstrap(client, monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_OPEN", False)
    await _seed_system_user()
    r = await client.post("/api/auth/register", json=_reg("alice"))
    assert r.status_code == 201            # 空库引导首个 admin 放行
    r = await client.post("/api/auth/register", json=_reg("bob"))
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == 4006


async def test_registration_open_gives_user_role(client, monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_OPEN", True)
    await client.post("/api/auth/register", json=_reg("alice"))
    r = await client.post("/api/auth/register", json=_reg("bob"))
    assert r.status_code == 201
    async with db_module.SessionLocal() as db:
        bob = (await db.execute(
            select(User).where(User.username == "bob"))).scalar_one()
    assert bob.role == "user"


@pytest.mark.parametrize("jwt_eph,fernet_eph,allow,raises", [
    (False, False, False, False),
    (True, False, False, True),
    (False, True, False, True),
    (True, True, True, False),
])
def test_check_crypto_secrets(monkeypatch, jwt_eph, fernet_eph, allow, raises):
    from app.main import check_crypto_secrets
    monkeypatch.setattr(settings, "JWT_SECRET_EPHEMERAL", jwt_eph)
    monkeypatch.setattr(settings, "FERNET_KEY_EPHEMERAL", fernet_eph)
    monkeypatch.setattr(settings, "ALLOW_EPHEMERAL_SECRETS", allow)
    if raises:
        with pytest.raises(RuntimeError, match="secrets_missing"):
            check_crypto_secrets()
    else:
        check_crypto_secrets()
