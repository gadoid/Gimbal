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
    # Normalize display_name the same way patch_user does: it doubles as
    # composer-ownership identity, so " Bob " / "Bob" must not coexist.
    payload.display_name = (payload.display_name or "").strip()
    existing = (
        await db.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 4003, "msg": "用户名已被占用"},
        )
    # display_name uniqueness — it doubles as composer-ownership identity
    # (see users.create_user). Registered names must not collide either.
    if payload.display_name:
        clash = (
            await db.execute(
                select(User).where(
                    (User.display_name == payload.display_name)
                    | (User.username == payload.display_name)
                )
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": 4003, "msg": "显示名已被占用（作为资源归属标识必须唯一）"},
            )
    # Conversely, the new USERNAME must not collide with an existing
    # display_name: ownership checks match ``display_name or username``
    # against the stored owner string, so a username equal to someone's
    # display_name would grant ownership of their resources.
    name_clash = (
        await db.execute(
            select(User).where(User.display_name == payload.username)
        )
    ).scalar_one_or_none()
    if name_clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 4003, "msg": "用户名与已有显示名冲突（作为资源归属标识必须唯一）"},
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