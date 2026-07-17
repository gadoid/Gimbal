"""User-management endpoints: list / create / patch / delete / reset-password.

Spec-1 simplifications (intentional):
* All routes are gated only by ``Depends(get_current_user)`` — no ``require_admin``
  enforcement (spec §7.6.6 — admin gating intentionally deferred to a later
  spec).  This means a regular member can ``PATCH`` / ``DELETE`` other users
  *subject to the hard business constraints below*.
* All endpoints require a Bearer token; missing/invalid → 401 (handled by
  :func:`app.core.deps.get_current_user`).

Hard business constraints:
* DELETE /{user_id}: caller must NOT be the target → 409 / code 4091.
* DELETE /{user_id}: target admin may not be the last admin → 409 / code 4092.
* PATCH /{user_id}: demoting an admin to non-admin may not leave zero admins →
  409 / code 4092.
* Reset-password returns a fresh random 12-char plaintext password exactly
  once; only the bcrypt hash is persisted.
"""
from __future__ import annotations

import random
import string
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..core.security import hash_password
from ..models.user import User
from ..schemas.user import UserCreateIn, UserOut, UserPatchIn

router = APIRouter(prefix="/users", tags=["users"])


# ── helpers ────────────────────────────────────────────────────────────
def _user_out(u: User) -> UserOut:
    return UserOut.model_validate(u)


def _gen_random_password(length: int = 12) -> str:
    """Cryptographically-strong random password (digits + letters)."""
    alphabet = string.ascii_letters + string.digits
    rng = random.SystemRandom()
    return "".join(rng.choice(alphabet) for _ in range(length))


async def _count_admins(db: AsyncSession) -> int:
    """How many users currently have ``is_admin=True``."""
    return (
        await db.execute(select(func.count()).select_from(User).where(User.is_admin.is_(True)))
    ).scalar_one()


# ── GET / ──────────────────────────────────────────────────────────────
@router.get("", response_model=list[UserOut])
async def list_users(
    user: CurrentUser,  # noqa: ARG001 — bearer required
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserOut]:
    """List every user in the system (spec-1: no pagination, no admin gating)."""
    rows = (await db.execute(select(User).order_by(User.id))).scalars().all()
    return [_user_out(u) for u in rows]


# ── POST / ─────────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: UserCreateIn,
    user: CurrentUser,  # noqa: ARG001 — bearer required
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    """Create a new user.  Spec-1: always created as member (is_admin=False)
    regardless of the ``is_admin`` field on the payload."""
    existing = (
        await db.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 4093, "msg": "用户名已被占用"},
        )
    new_user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        is_admin=False,  # spec-1 simplification: always member on creation
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return _user_out(new_user)


# ── PATCH /{user_id} ───────────────────────────────────────────────────
@router.patch("/{user_id}", response_model=UserOut)
async def patch_user(
    user_id: int,
    payload: UserPatchIn,
    caller: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    """Update ``display_name`` / ``is_admin`` / ``is_active`` / ``new_password``.

    Constraint: demoting an admin (``is_admin: false`` on a target whose current
    flag is ``True``) may not leave the system with zero admins.
    """
    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 4041, "msg": "用户不存在"},
        )

    data = payload.model_dump(exclude_unset=True)
    demoting_admin = (
        "is_admin" in data
        and data["is_admin"] is False
        and target.is_admin is True
    )
    if demoting_admin:
        admin_total = await _count_admins(db)
        if admin_total <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": 4092, "msg": "不能降级最后一个管理员"},
            )

    if "display_name" in data:
        target.display_name = data["display_name"]
    if "is_admin" in data:
        target.is_admin = data["is_admin"]
    if "is_active" in data:
        target.is_active = data["is_active"]
    if "new_password" in data:
        target.password_hash = hash_password(data["new_password"])

    await db.commit()
    await db.refresh(target)
    return _user_out(target)


# ── POST /{user_id}/reset-password ─────────────────────────────────────
@router.post(
    "/{user_id}/reset-password",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def reset_password(
    user_id: int,
    caller: CurrentUser,  # noqa: ARG001 — bearer required
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Generate a fresh random password for ``user_id`` and persist its hash.

    The plaintext password is returned **once** in the response and is never
    stored on the server.
    """
    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 4041, "msg": "用户不存在"},
        )

    new_pw = _gen_random_password(12)
    target.password_hash = hash_password(new_pw)
    await db.commit()
    return {
        "user_id": target.id,
        "username": target.username,
        "new_password": new_pw,
    }


# ── DELETE /{user_id} ──────────────────────────────────────────────────
@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    user_id: int,
    caller: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete ``user_id``.

    Constraints (both 409):
    * caller cannot delete themselves (code 4091).
    * cannot delete the last remaining admin (code 4092).
    """
    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 4041, "msg": "用户不存在"},
        )

    if target.id == caller.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 4091, "msg": "不能删除自己"},
        )

    if target.is_admin:
        admin_total = await _count_admins(db)
        if admin_total <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": 4092, "msg": "不能删除最后一个管理员"},
            )

    await db.delete(target)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)