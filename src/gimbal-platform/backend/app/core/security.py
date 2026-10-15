"""JWT issuance/verification + Fernet symmetric encryption."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from .config import settings

_fernet = Fernet(settings.FERNET_KEY.encode())


# ─── Password ───────────────────────────────────────────────
# 直接使用 bcrypt(整体评审 2026-10-15 #6:passlib 已停止维护,且迫使
# bcrypt 锁在 <4.1)。存量 passlib 产出的 $2b$ 哈希与 bcrypt 原生格式
# 相同,可直接校验。passlib 对 >72 字节口令静默截断,bcrypt>=5 改为
# 抛错 —— 这里按 passlib 同口径截断到 72 字节,存量长口令仍可登录。
_BCRYPT_MAX_BYTES = 72


def _pw_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_pw_bytes(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


# ─── JWT ────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(*, subject: str | int, **claims: Any) -> str:
    expire = _now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MIN)
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": _now(),
        "type": "access",
        # jti guarantees uniqueness even when two tokens are issued in the
        # same wall-clock second (otherwise the JWT payload — and hence the
        # encoded string — would be byte-identical).
        "jti": uuid.uuid4().hex,
        **claims,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGO)


def create_refresh_token(*, subject: str | int) -> str:
    expire = _now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": _now(),
        "type": "refresh",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGO)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGO])
    except jwt.PyJWTError as e:
        raise ValueError(f"invalid token: {e}") from e


# ─── Fernet for auths.password storage ──────────────────────
def fernet_encrypt(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()


def fernet_decrypt(enc: str) -> str:
    try:
        return _fernet.decrypt(enc.encode()).decode()
    except InvalidToken as e:
        raise ValueError(f"fernet decrypt failed: {e}") from e
