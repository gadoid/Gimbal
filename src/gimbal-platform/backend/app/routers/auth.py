"""Auth endpoints: register / login / refresh / me."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..models.user import User
from ..schemas.auth import (
    LoginIn,
    MeOut,
    RefreshIn,
    RegisterIn,
    TokenOut,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── helpers ──────────────────────────────────────────────────────
def _user_public(u: User) -> UserPublic:
    return UserPublic.model_validate(u)


def _token_out(u: User) -> TokenOut:
    access = create_access_token(subject=u.id)
    refresh = create_refresh_token(subject=u.id)
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        user=_user_public(u),
    )


# ── POST /register ───────────────────────────────────────────────
@router.post(
    "/register",
    response_model=TokenOut,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenOut:
    existing = (
        await db.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 4003, "msg": "用户名已被占用"},
        )
    # First registered user becomes admin.
    count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    is_admin = count == 0

    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        is_admin=is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _token_out(user)


# ── POST /login ──────────────────────────────────────────────────
@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenOut:
    user = (
        await db.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 4004, "msg": "用户名或密码错误"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 4005, "msg": "账号已停用"},
        )
    return _token_out(user)


# ── POST /refresh ────────────────────────────────────────────────
@router.post("/refresh", response_model=TokenOut)
async def refresh(
    payload: RefreshIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenOut:
    try:
        data = decode_token(payload.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    if data.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not a refresh token",
        )
    user = (
        await db.execute(select(User).where(User.id == int(data["sub"])))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not found or inactive",
        )
    return _token_out(user)


# ── GET /me ──────────────────────────────────────────────────────
@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser) -> MeOut:
    return MeOut(user=_user_public(user))