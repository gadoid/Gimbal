"""User-management endpoints: list / create / patch / delete / reset-password.

Authorization (hardened):
* ``DELETE /{user_id}`` — admin only (a member can never delete another
  account; self-delete is separately refused with 409/code 4091).
* ``PATCH /{user_id}``  — admin may patch anyone; a member may only patch
  **themselves** and may NOT touch the ``is_admin`` flag (403/code 4032).
* ``reset-password``    — admin (for anyone) or the target user (for
  themselves); a member resetting *someone else's* password is refused
  (403/code 4033) — this used to be a full account-takeover vector.
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
from ._codes import (
    ADMIN_REQUIRED,
    LAST_ADMIN,
    MEMBER_PATCH_FORBIDDEN,
    NAME_TAKEN,
    RESET_OTHER_PASSWORD,
    SELF_DELETE,
    USER_NOT_FOUND,
    code_detail,
)
from ._name_checks import assert_name_available

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
    # Normalize display_name like patch_user: it doubles as composer
    # ownership identity, so " Bob " / "Bob" must not coexist.
    payload.display_name = (payload.display_name or "").strip()
    # 用户名/display_name 查重 + 双向冲突检查(见 _name_checks):
    # display_name 兼作归属标识,冒用他人显示名 = 提权接管其资源。
    await assert_name_available(
        db,
        username=payload.username,
        display_name=payload.display_name or None,
        code=NAME_TAKEN,
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

    Authorization:
    * admin caller — may patch any user, any field.
    * member caller — may only patch **themselves** (403/4032 on other
      targets) and may never touch ``is_admin`` (privilege-escalation fix).

    Constraint: demoting an admin (``is_admin: false`` on a target whose current
    flag is ``True``) may not leave the system with zero admins.
    """
    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=code_detail(USER_NOT_FOUND, "用户不存在"),
        )

    data = payload.model_dump(exclude_unset=True)

    # ── authorization (privilege-escalation fix) ──
    if not caller.is_admin:
        if target.id != caller.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=code_detail(MEMBER_PATCH_FORBIDDEN, "普通用户只能修改自己的资料"),
            )
        if "is_admin" in data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=code_detail(MEMBER_PATCH_FORBIDDEN, "只有管理员可以变更管理员标志"),
            )

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
                detail=code_detail(LAST_ADMIN, "不能降级最后一个管理员"),
            )

    if "display_name" in data:
        new_name = (data["display_name"] or "").strip()
        if new_name and new_name != (target.display_name or ""):
            # Ownership-identity uniqueness (see _name_checks).
            await assert_name_available(
                db, display_name=new_name, code=NAME_TAKEN, exclude_id=target.id
            )
        target.display_name = new_name
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

    Authorization: admin (any target) or the target user themselves
    (account-takeover fix: a member can no longer reset *someone else's*
    password and receive the plaintext).  The plaintext password is
    returned **once** in the response and is never stored on the server.
    """
    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=code_detail(USER_NOT_FOUND, "用户不存在"),
        )
    if not caller.is_admin and caller.id != target.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=code_detail(RESET_OTHER_PASSWORD, "只有管理员或本人可以重置该密码"),
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

    Authorization: admin only — a member can never delete another account
    (403/4031).  Self-delete is separately refused below (409/code 4091),
    so effectively "admin deleting someone else".

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
            detail=code_detail(USER_NOT_FOUND, "用户不存在"),
        )

    if target.id == caller.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=code_detail(SELF_DELETE, "不能删除自己"),
        )

    if not caller.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=code_detail(ADMIN_REQUIRED, "需要管理员权限"),
        )

    if target.is_admin:
        admin_total = await _count_admins(db)
        if admin_total <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=code_detail(LAST_ADMIN, "不能删除最后一个管理员"),
            )

    await db.delete(target)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)