"""JWT issuance/verification + Fernet symmetric encryption."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_fernet = Fernet(settings.FERNET_KEY.encode())


# ─── Password ───────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_ctx.verify(plain, hashed)
    except Exception:
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
    except JWTError as e:
        raise ValueError(f"invalid token: {e}") from e


# ─── Fernet for auths.password storage ──────────────────────
def fernet_encrypt(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()


def fernet_decrypt(enc: str) -> str:
    try:
        return _fernet.decrypt(enc.encode()).decode()
    except InvalidToken as e:
        raise ValueError(f"fernet decrypt failed: {e}") from e
