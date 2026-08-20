"""Pydantic schemas for the auth-sessions API (Spec-2 §4.4 D)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuthSessionOut(BaseModel):
    """Public-facing view of an AuthSession row.

    Note: the password is NEVER returned in plaintext.  ``password_masked``
    is a sentinel the UI uses to render ``<REDACTED>``.  凭证解密注入由
    run_dispatcher 服务端完成(不对外下发)。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    alias: str
    url: str
    username: str  # decrypted server-side
    token_type: str
    expires_in: int
    created_at: datetime
    updated_at: datetime
    password_masked: str = Field(default="<REDACTED>")


class AuthSessionCreateIn(BaseModel):
    alias: str = Field(min_length=1, max_length=64)
    url: str = Field(min_length=1, max_length=512)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(default=7200, ge=0)


class AuthSessionPatchIn(BaseModel):
    url: str | None = Field(default=None, min_length=1, max_length=512)
    username: str | None = Field(default=None, min_length=1)
    password: str | None = Field(default=None, min_length=1)
    token_type: str | None = None
    expires_in: int | None = Field(default=None, ge=0)


class TestResult(BaseModel):
    ok: bool
    status_code: int | None = None
    message: str