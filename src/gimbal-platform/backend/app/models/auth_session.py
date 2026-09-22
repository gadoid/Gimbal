"""AuthSession model — user-owned credential pool (Spec-2 §4.4 D).

Each AuthSession represents a target system's login that the platform
can use to mint bearer tokens at execution time.  Decoupled from any
yaml file: the platform injects ``Config.users[<alias>]`` into a temp
yaml at execution time (Spec-2-2), not at case-upload time.

Encryption: username + password are Fernet-encrypted at rest so a
database dump doesn't leak credentials.  The Fernet key is loaded
from ``settings.FERNET_KEY`` (auto-generated dev-only fallback).
"""
from __future__ import annotations

from datetime import datetime

from ._types import UtcDateTime
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (UniqueConstraint("owner_id", "alias", name="uq_auth_owner_alias"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # NO ACTION DEFERRABLE(§2.1):删除用户的处置由 Python 显式管
    # (P1a 最小显式级联随 M2 同车),FK 是校验器不是级联器。
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"), index=True
    )
    alias: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(Text)
    username_enc: Mapped[str] = mapped_column(Text)  # Fernet ciphertext(长度随密码变)
    password_enc: Mapped[str] = mapped_column(Text)  # Fernet ciphertext(长度随密码变)
    token_type: Mapped[str] = mapped_column(String(32), default="Bearer")
    expires_in: Mapped[int] = mapped_column(Integer, default=7200)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now()
    )