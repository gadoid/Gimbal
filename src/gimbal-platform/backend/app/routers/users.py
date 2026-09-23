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

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser, CurrentUser, OperatorUser
from ..core.security import hash_password
from ..models.user import User
from ..models.auth_session import AuthSession
from ..models.constant_entry import ConstantEntry
from ..models.service_alias import ServiceAlias
from ..schemas.page import PageOut
from ..schemas.user import (
    UserCreateIn,
    UserDeleteIn,
    UserListOut,
    UserOut,
    UserPatchIn,
)
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
    """How many users currently hold the ``admin`` role(role 权威)。"""
    return (
        await db.execute(select(func.count()).select_from(User).where(User.role == "admin"))
    ).scalar_one()


# ── GET /roster — 成员选择器(2026-09-23 批次 F1 分发)─────────────────
@router.get("/roster")
async def get_roster(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """分发对话框的成员选择器:CurrentUser 可调(分发是 member 级能力,
    现有 GET /users 是 operator+ 且带管理字段,不能降级复用)。

    仅 ``is_active`` 用户、排除自己;User 表无 email 列,不为选人器
    加列 —— ``display_name (username)`` 对内部平台足够定位人。
    不分页、上限 200,前端本地过滤(团队规模下比搜索接口省事)。
    """
    rows = (await db.execute(
        select(User)
        .where(User.is_active.is_(True), User.id != user.id)
        .order_by(User.display_name, User.username)
        .limit(200)
    )).scalars().all()
    return {"items": [
        {"id": u.id, "username": u.username,
         "display_name": u.display_name or ""}
        for u in rows
    ]}


# ── GET / ──────────────────────────────────────────────────────────────
@router.get("", response_model=UserListOut)
async def list_users(
    user: OperatorUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=64)] = None,
    role: Annotated[str | None, Query(max_length=16)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> UserListOut:
    """List every user(M2.5 收紧:operator+ 可见;原「任何登录用户全量
    可见」的 spec-1 遗留闭合 —— 权限方案 §5.3)。M4(§6.3):q
    (username/display_name 子串)+ role 精确 + Page 信封。"""
    base = select(User)
    if q:
        base = base.where(or_(
            User.username.ilike(f"%{q}%"),
            User.display_name.ilike(f"%{q}%"),
        ))
    if role:
        base = base.where(User.role == role)
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()
    rows = (await db.execute(
        base.order_by(User.id)
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return UserListOut(
        items=[_user_out(u) for u in rows],
        total=total, page=page, page_size=page_size,
    )


# ── POST / ─────────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: UserCreateIn,
    user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    """Create a new user(M2.5 收紧:admin 开号 —— 创建账号是人事权,
    spec-1「任何登录用户可开号」的遗留闭合,权限方案 §5.3)。"""
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
        role=payload.role,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="user.create", resource_type="user", resource_id=str(new_user.id),
        detail={"username": new_user.username, "role": new_user.role},
    )
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
      targets) and may never touch ``role`` (privilege-escalation fix).

    Constraint: demoting the last admin(``role`` 从 admin 降下)被 409 拒。
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
    if caller.role != "admin":
        if target.id != caller.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=code_detail(MEMBER_PATCH_FORBIDDEN, "普通用户只能修改自己的资料"),
            )
        if "role" in data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=code_detail(MEMBER_PATCH_FORBIDDEN, "只有管理员可以变更角色"),
            )

    demoting_admin = (
        "role" in data
        and data["role"] != "admin"
        and target.role == "admin"
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
    if "role" in data and data["role"] != target.role:
        old_role = target.role
        target.role = data["role"]
        # 通知接线(P1b,权限方案 §3.2):升降级即时告知本人
        from ..services import notifications as notify_svc
        try:
            await notify_svc.create_notification(
                db,
                user_id=target.id,
                type_="role_changed",
                title=f"角色已变更为 {data['role']}",
                body=f"管理员将你的角色从 {old_role} 调整为 {data['role']}。"
                     "权限即时生效。",
                link="/home",
                commit=False,
            )
        except Exception:  # noqa: BLE001
            pass
    if "is_active" in data:
        target.is_active = data["is_active"]
    if "new_password" in data:
        target.password_hash = hash_password(data["new_password"])

    await db.commit()
    await db.refresh(target)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=caller.id,
        actor_name=caller.display_name or caller.username,
        action="user.role_change", resource_type="user", resource_id=str(target.id),
        detail={"username": target.username, "changed": sorted(data.keys()),
                "role": target.role, "is_active": target.is_active},
    )
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
    if caller.role != "admin" and caller.id != target.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=code_detail(RESET_OTHER_PASSWORD, "只有管理员或本人可以重置该密码"),
        )

    new_pw = _gen_random_password(12)
    target.password_hash = hash_password(new_pw)
    await db.commit()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=caller.id,
        actor_name=caller.display_name or caller.username,
        action="user.reset_password", resource_type="user",
        resource_id=str(user_id),
        detail={"username": target.username, "self": caller.id == target.id},
    )
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
    body: UserDeleteIn | None = None,
):
    """Delete ``user_id``(P2-2:资源处置三选一)。

    Authorization: admin only — a member can never delete another account
    (403/4031).  Self-delete is separately refused below (409/code 4091),
    so effectively "admin deleting someone else".

    Constraints (both 409):
    * caller cannot delete themselves (code 4091).
    * cannot delete the last remaining admin (code 4092).

    处置(权限方案 §4.3):``publicize`` 私有场景转公共库(默认,署名
    保留 owner_name 快照)/ ``transfer`` 转让给指定成员(数据集/方案
    随场景走,个人别名转共享,受让人收 resource_transferred 通知)/
    ``purge`` 一并删除。执行台账恒保留(outlive 用户:owner_id 置空 +
    owner_name 快照,展示「已注销」);case 目录按 owner 定位 runId
    当场清扫(case.json 含注入后明文凭证,不等 14 天周期)。
    """
    disposal = body.disposal if body is not None else "publicize"
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

    if caller.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=code_detail(ADMIN_REQUIRED, "需要管理员权限"),
        )

    if target.role == "admin":
        admin_total = await _count_admins(db)
        if admin_total <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=code_detail(LAST_ADMIN, "不能删除最后一个管理员"),
            )

    # 受让人校验(transfer):在场且非目标本人
    transferee = None
    if disposal == "transfer":
        if body is None or body.transfer_to is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="disposal=transfer 需要 transfer_to",
            )
        transferee = (await db.execute(
            select(User).where(User.id == body.transfer_to)
        )).scalar_one_or_none()
        if transferee is None or transferee.id == target.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="transfer_to 用户不存在(或与被删用户相同)",
            )

    from sqlalchemy import update as sa_update

    from ..models.board_card import BoardCard
    from ..models.composer_scenario import ComposerScenario
    from ..models.execution import Execution
    from ..models.permission import UserStar
    from ..services import audit as audit_svc
    from ..services import scenario_store
    from ..services.notifications import create_notification
    from ..services.run_dispatcher import purge_case_dir

    caller_label = caller.display_name or caller.username

    # ── 场景处置(三选一)─────────────────────────────────────────
    scenario_ids = list((await db.execute(
        select(ComposerScenario.scenario_id)
        .where(ComposerScenario.owner_id == user_id)
    )).scalars())
    if disposal == "publicize":
        if scenario_ids:
            # owner_id 显式置空(SET NULL 语义;SQLite 方言 FK 不强制的
            # 双方言兜底),owner_name 快照保留原作者署名
            await db.execute(
                sa_update(ComposerScenario)
                .where(ComposerScenario.owner_id == user_id)
                .values(visibility="public", owner_id=None))
    elif disposal == "transfer":
        if scenario_ids:
            transferee_label = transferee.display_name or transferee.username
            await db.execute(
                sa_update(ComposerScenario)
                .where(ComposerScenario.owner_id == user_id)
                .values(owner_id=transferee.id, owner_name=transferee_label))
    else:  # purge
        for sid in scenario_ids:
            await scenario_store.delete(db, sid)

    # ── 台账/线索板 SET NULL(显式:SQLite 方言 FK 不强制)─────────
    user_execs = list((await db.execute(
        select(Execution).where(Execution.owner_id == user_id)
    )).scalars())
    await db.execute(
        sa_update(Execution).where(Execution.owner_id == user_id)
        .values(owner_id=None))
    await db.execute(
        sa_update(BoardCard).where(BoardCard.author_id == user_id)
        .values(author_id=None))
    await db.execute(
        sa_delete(UserStar).where(UserStar.user_id == user_id))

    # case 目录立即清扫:按 owner 的执行定位 runId 当场清(case.json
    # 含注入后明文凭证,不等 14 天保留周期 —— 权限方案 §4.3)。
    for ex in user_execs:
        run_id = (ex.config_json or {}).get("runId")
        if run_id:
            purge_case_dir(str(run_id))

    # ── P1a 最小显式级联(NO ACTION 三表;transfer 时个人别名转共享)──
    await db.execute(
        sa_delete(AuthSession).where(AuthSession.owner_id == user_id))
    await db.execute(
        sa_delete(ConstantEntry).where(ConstantEntry.owner_id == user_id))
    if disposal == "transfer":
        await db.execute(
            sa_update(ServiceAlias)
            .where(ServiceAlias.owner_user_id == user_id)
            .values(owner_user_id=None))
    else:
        await db.execute(
            sa_delete(ServiceAlias).where(ServiceAlias.owner_user_id == user_id))

    await db.delete(target)
    await db.commit()

    # 处置后动作:转让通知 + 审计(特权写,权限方案 §6)
    if disposal == "transfer" and scenario_ids:
        await create_notification(
            db,
            user_id=transferee.id,
            type_="resource_transferred",
            title=f"{len(scenario_ids)} 个场景已转让给你",
            body=f"管理员将 {target.display_name or target.username} 的 "
                 f"{len(scenario_ids)} 个场景转让给你,请查收。",
            commit=False,
        )
    await audit_svc.record(
        db,
        actor_id=caller.id, actor_name=caller_label,
        action="user.delete",
        resource_type="user", resource_id=str(user_id),
        detail={
            "username": target.username,
            "disposal": disposal,
            "transfer_to": transferee.id if transferee else None,
            "scenarios": len(scenario_ids),
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)