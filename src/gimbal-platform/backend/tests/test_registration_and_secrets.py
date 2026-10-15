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


def test_registration_open_default_is_true(monkeypatch):
    # 2026-10-15 拍板:默认开放自助注册。空 env + 不读 .env 构造
    # Settings 必须得到 True —— 防止日后误翻回 False 而无测试报警;
    # _env_file=None:开发机 .env 若写 REGISTRATION_OPEN=false 不得
    # 污染本用例(默认值是代码层的契约,不是本机环境的事实)。
    monkeypatch.delenv("REGISTRATION_OPEN", raising=False)
    from app.core.config import Settings
    assert Settings(_env_file=None).REGISTRATION_OPEN is True


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


# ── 口令哈希/JWT 换库兼容(整体评审 2026-10-15 #6:passlib→bcrypt,
#    python-jose→PyJWT)—— 存量账号必须照常登录 ──────────────────────
# 以下两条哈希由 passlib 1.7.4 + bcrypt 4.0.1(换库前的生产组合)生成。
_PASSLIB_SHORT = "$2b$12$d/0ZL5fdo03axIzkXrpLIOH3163QpL8l38j48RYBN90df5MhcnpHe"
_PASSLIB_LONG = "$2b$12$MHW5RUKFY0pt0ewOpXiJC.HDMQO1ZSbXlcTxgJHLiqtKEZWLZWpdO"
_LONG_PW = "长口令" * 30          # 270 字节:passlib 静默截断到 72 字节


def test_passlib_hashes_still_verify():
    from app.core.security import hash_password, verify_password
    assert verify_password("Passw0rd!123", _PASSLIB_SHORT)
    assert not verify_password("wrong", _PASSLIB_SHORT)
    assert verify_password(_LONG_PW, _PASSLIB_LONG)
    # 新哈希同为 $2b$,>72 字节不抛错(bcrypt>=5 原生会抛 ValueError)
    h = hash_password(_LONG_PW)
    assert h.startswith("$2b$") and verify_password(_LONG_PW, h)
    assert not verify_password("x", "not-a-bcrypt-hash")


def test_jwt_roundtrip_and_tamper():
    from app.core.security import create_access_token, decode_token
    tok = create_access_token(subject=42)
    assert decode_token(tok)["sub"] == "42"
    with pytest.raises(ValueError, match="invalid token"):
        decode_token(tok[:-2] + ("aa" if not tok.endswith("aa") else "bb"))
