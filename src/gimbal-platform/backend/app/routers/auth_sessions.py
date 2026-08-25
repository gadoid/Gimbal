"""Auth-sessions API (Spec-2 §4.4 D).

Endpoints:
- GET    /api/auths                 list owner's credentials
- POST   /api/auths                 create
- GET    /api/auths/{id}            detail
- PATCH  /api/auths/{id}            update (url/username/password/token_type/expires_in)
- DELETE /api/auths/{id}            delete
- POST   /api/auths/{id}/test       hit alias.url with username+password; parse token

(fetch-token 端点已随 V1 executor 退役移除 —— 凭证解密注入由
run_dispatcher 服务端完成,不再对外下发明文凭证。)

All endpoints are owner-scoped — a user can never see another user's
auth-sessions, even if they know the integer id.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..core.security import fernet_decrypt, fernet_encrypt
from ..models import AuthSession
from ..schemas.auth_session import (
    AuthSessionCreateIn,
    AuthSessionOut,
    AuthSessionPatchIn,
    AuthSessionSecretsOut,
    TestResult,
)
from ..services import auth_probe

router = APIRouter(prefix="/auths", tags=["auths"])


DbSession = Annotated[AsyncSession, Depends(get_db)]


def _safe_decrypt(encrypted: str) -> str:
    """Decrypt, degrading gracefully after a FERNET_KEY rotation.

    Rows encrypted under a previous (ephemeral) key become
    undecryptable; blowing up with ValueError → HTTP 500 on every
    GET would take the whole auth list down.  Masked placeholder
    instead — the row is still visible/editable so the user can
    re-enter the credential.
    """
    try:
        return fernet_decrypt(encrypted)
    except ValueError:
        return "<无法解密：密钥已轮换，请重新编辑保存>"


def _to_out(a: AuthSession) -> AuthSessionOut:
    """Decrypt username for the response (password stays masked)."""
    return AuthSessionOut(
        id=a.id,
        alias=a.alias,
        url=a.url,
        username=_safe_decrypt(a.username_enc),
        token_type=a.token_type,
        expires_in=a.expires_in,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


async def _get_owned(session: AsyncSession, auth_id: int, owner_id: int) -> AuthSession:
    a = await session.get(AuthSession, auth_id)
    if a is None or a.owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"auth not found: {auth_id}"
        )
    return a


# ── list ────────────────────────────────────────────────────────
@router.get("", response_model=list[AuthSessionOut])
async def list_auths(
    user: CurrentUser, session: DbSession
) -> list[AuthSessionOut]:
    rows = (
        (
            await session.execute(
                select(AuthSession)
                .where(AuthSession.owner_id == user.id)
                .order_by(AuthSession.alias.asc())
            )
        )
        .scalars()
        .all()
    )
    return [_to_out(a) for a in rows]


# ── create ──────────────────────────────────────────────────────
@router.post("", response_model=AuthSessionOut, status_code=status.HTTP_201_CREATED)
async def create_auth(
    payload: AuthSessionCreateIn,
    user: CurrentUser,
    session: DbSession,
) -> AuthSessionOut:
    a = AuthSession(
        owner_id=user.id,
        alias=payload.alias,
        url=payload.url,
        username_enc=fernet_encrypt(payload.username),
        password_enc=fernet_encrypt(payload.password),
        token_type=payload.token_type,
        expires_in=payload.expires_in,
    )
    session.add(a)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"alias '{payload.alias}' already exists for this user",
        )
    await session.refresh(a)
    return _to_out(a)


# ── detail ─────────────────────────────────────────────────────
@router.get("/{auth_id}", response_model=AuthSessionSecretsOut | AuthSessionOut)
async def get_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
    include_secrets: bool = False,
) -> AuthSessionOut | AuthSessionSecretsOut:
    a = await _get_owned(session, auth_id, user.id)
    if not include_secrets:
        return _to_out(a)
    # 严解密:密钥轮换后的旧密文不可恢复。快照拷贝会把返回值当真值写进
    # 场景导出产物,不能像列表 _safe_decrypt 那样降级为占位符 — 显式 422。
    try:
        username = fernet_decrypt(a.username_enc)
        password = fernet_decrypt(a.password_enc)
    except ValueError as e:
        logger.warning("auth.get include_secrets: fernet decrypt failed: {}", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="加密凭据已损坏或密钥已轮换，请先在认证管理重新编辑保存",
        )
    return AuthSessionSecretsOut(
        id=a.id,
        alias=a.alias,
        url=a.url,
        username=username,
        password=password,
        token_type=a.token_type,
        expires_in=a.expires_in,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


# ── patch ──────────────────────────────────────────────────────
@router.patch("/{auth_id}", response_model=AuthSessionOut)
async def patch_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    payload: AuthSessionPatchIn,
    user: CurrentUser,
    session: DbSession,
) -> AuthSessionOut:
    a = await _get_owned(session, auth_id, user.id)
    if payload.url is not None:
        a.url = payload.url
    if payload.username is not None:
        a.username_enc = fernet_encrypt(payload.username)
    if payload.password is not None:
        a.password_enc = fernet_encrypt(payload.password)
    if payload.token_type is not None:
        a.token_type = payload.token_type
    if payload.expires_in is not None:
        a.expires_in = payload.expires_in
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="更新冲突"
        )
    await session.refresh(a)
    return _to_out(a)


# ── delete ─────────────────────────────────────────────────────
@router.delete("/{auth_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
) -> None:
    a = await _get_owned(session, auth_id, user.id)
    await session.delete(a)
    await session.commit()


# ── test ───────────────────────────────────────────────────────
@router.post("/{auth_id}/test", response_model=TestResult)
async def test_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
) -> TestResult:
    """Dial the stored credential against ``url`` (probe service)."""
    a = await _get_owned(session, auth_id, user.id)
    try:
        username = fernet_decrypt(a.username_enc)
        password = fernet_decrypt(a.password_enc)
    except ValueError as e:
        logger.warning("auth.test: fernet decrypt failed: {}", e)
        return TestResult(ok=False, message="加密凭据已损坏，请重新录入")

    ok, status_code, message = await auth_probe.probe(a.url, username, password)
    return TestResult(ok=ok, status_code=status_code, message=message)