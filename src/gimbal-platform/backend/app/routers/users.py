"""User-management endpoints: list / create / patch / delete / reset-password.

Authorization (hardened):
* ``DELETE /{user_id}`` — admin only (a non-admin can never delete another
  account; self-delete is separately refused with 409/code 4091).
* ``PATCH /{user_id}``  — admin may patch anyone; a non-admin may only patch
  **themselves** and may NOT touch the ``role`` field (403/code 4032).
* ``reset-password``    — admin (for anyone) or the target user (for
  themselves); a non-admin resetting *someone else's* password is refused
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
from ..core.deps import AdminUser, CurrentUser, MemberUser
from ..core.security import hash_password
from ._ownership import has_capability, roles_with
from ..models.user import User
from ..services import access_token as at_svc
from ..models.auth_session import AuthSession
from ..models.constant_entry import ConstantEntry
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
    """末位管理员保护计数:按 ``super_admin`` 计(authz W1 更名后原
    admin 级 = super_admin;若仍按 admin 计,迁移后计数为 0、保护失效)。"""
    return (
        await db.execute(select(func.count()).select_from(User).where(
            User.role.in_(roles_with("users.manage"))))
    ).scalar_one()


# ── GET /roster — 成员选择器(2026-09-23 批次 F1 分发)─────────────────
@router.get("/roster")
async def get_roster(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """分发对话框的成员选择器:CurrentUser 可调(分发是 user 级能力,
    现有 GET /users 是 member+ 且带管理字段,不能降级复用)。

    仅 ``is_active`` 用户、排除自己;User 表无 email 列,不为选人器
    加列 —— ``display_name (username)`` 对内部平台足够定位人。
    不分页、上限 200,前端本地过滤(团队规模下比搜索接口省事)。
    """
    rows = (await db.execute(
        select(User)
        .where(User.is_active.is_(True), User.id != user.id,
               User.is_system.is_(False))
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
    user: MemberUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=64)] = None,
    role: Annotated[str | None, Query(max_length=16)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> UserListOut:
    """List every user(M2.5 收紧:member+ 可见;原「任何登录用户全量
    可见」的 spec-1 遗留闭合 —— 权限方案 §5.3)。M4(§6.3):q
    (username/display_name 子串)+ role 精确 + Page 信封。"""
    base = select(User).where(User.is_system.is_(False))
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
        resource_name=new_user.display_name or new_user.username,
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
    * non-admin caller — may only patch **themselves** (403/4032 on other
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
    # D32 系统用户保护:按 id 直取的 PATCH 无防护 —— 一次调用就能停用
    # __platform__(全部平台令牌失效)。系统用户一律 409。
    if getattr(target, "is_system", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "system_user_protected",
                    "message": "系统用户(__platform__)受保护,"
                               "不能停用或修改"},
        )

    data = payload.model_dump(exclude_unset=True)
    # 审计前值快照:role/is_active 的旧值在改写前留底(读侧渲染
    # 「从 X 改为 Y」,事后资源/记录不可追)
    prev_role, prev_active = target.role, target.is_active

    # ── authorization (privilege-escalation fix) ──
    if not has_capability(caller, "users.manage"):
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

    # 末位保护按表 A 判「是否用户管理者」(更名只动表,不动这里)
    managers = roles_with("users.manage")
    demoting_admin = (
        "role" in data
        and data["role"] not in managers
        and target.role in managers
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
    revoked_tokens = 0
    if "is_active" in data:
        target.is_active = data["is_active"]
        # webhook v4 §3.6(D13):停用 → 本人全部个人令牌落库失效
        # (原因 deactivated;平台令牌属 __platform__,不受影响)——
        # 本路由是唯一的停用入口。重新启用**不**恢复,需重新生成。
        if prev_active and not data["is_active"]:
            from sqlalchemy import update as _sa_update

            from ..models.access_token import AccessToken
        
            # RETURNING 只取本次 UPDATE 命中的行(评审 2026-11-05 P2:
            # 按 invalidated_reason==deactivated 重取会把上一轮停用
            # 失效、尚未重新生成的历史令牌再通知一遍)
            res = await db.execute(_sa_update(AccessToken).where(
                AccessToken.user_id == target.id,
                AccessToken.kind == at_svc.PERSONAL_KIND,
                AccessToken.revoked_at.is_(None),
                AccessToken.invalidated_at.is_(None),
            ).values(invalidated_at=at_svc.now_utc(),
                     invalidated_reason=at_svc.REASON_DEACTIVATED)
                .returning(AccessToken.id))
            hit_ids = list(res.scalars().all())
            revoked_tokens = len(hit_ids)
            if hit_ids:
                # 逐令牌暂停注册方实例 + 通知(§3.4)
                toks = (await db.execute(select(AccessToken).where(
                    AccessToken.id.in_(hit_ids)))).scalars().all()
                for tok in toks:
                    await at_svc.pause_token_instances(
                        db, tok, at_svc.PAUSE_TOKEN_INVALIDATED,
                        "令牌因属主停用失效;属主重新启用后需重新生成令牌")
            # M2b Q2:停用者负责的项目令牌 —— 不落库失效(认证派生拒绝),
            # 提醒各项目其余管理员换绑负责人
            from .project_tokens import notify_holder_lost
            pids = (await db.execute(select(AccessToken.project_id).where(
                AccessToken.kind == at_svc.PROJECT_KIND,
                AccessToken.holder_id == target.id,
                AccessToken.revoked_at.is_(None)).distinct())).scalars().all()
            for _pid in pids:
                await notify_holder_lost(db, _pid, target.id)
    if "new_password" in data:
        target.password_hash = hash_password(data["new_password"])

    await db.commit()
    await db.refresh(target)
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=caller.id,
        actor_name=caller.display_name or caller.username,
        action="user.role_change", resource_type="user", resource_id=str(target.id),
        resource_name=target.display_name or target.username,
        detail={"username": target.username, "changed": sorted(data.keys()),
                "role": target.role, "is_active": target.is_active,
                "role_from": prev_role, "is_active_from": prev_active},
    )
    if revoked_tokens:
        # 停用连带令牌失效单独留痕(访问授权的收缩,取证面)
        await audit_svc.record(
            db, actor_id=caller.id,
            actor_name=caller.display_name or caller.username,
            action="token.invalidate", resource_type="user",
            resource_id=str(target.id),
            resource_name=target.display_name or target.username,
            detail={"reason": "deactivated", "count": revoked_tokens},
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
    (account-takeover fix: a non-admin can no longer reset *someone else's*
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
    if not has_capability(caller, "users.manage") and caller.id != target.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=code_detail(RESET_OTHER_PASSWORD, "只有管理员或本人可以重置该密码"),
        )

    new_pw = _gen_random_password(12)
    target.password_hash = hash_password(new_pw)
    # authz W6(方案 10.1):重置不再是接管通道 —— 三件套:
    # ① must_change_password(只能改密门,deps.CurrentUser 403
    #    password_change_required,白名单 /auth/me//auth/refresh/
    #    /auth/change-password);
    # ② 本人全部个人令牌落库失效(REASON_PASSWORD,与自服务改密同款);
    # ③ token_version + 1(旧 JWT access/refresh 整体失效)。
    # 临时密码仍返回给管理员一次(R8 定死:当前没有其他通道交给用户,
    # 方案接受「能接管、做不到悄悄接管」——审计 + 通知 + 强制改密在)。
    from datetime import datetime, timezone as _tz

    from sqlalchemy import update as _sa_update

    from ..models.access_token import AccessToken

    target.must_change_password = True
    target.token_version = int(target.token_version or 0) + 1
    res = await db.execute(_sa_update(AccessToken).where(
        AccessToken.user_id == target.id,
        AccessToken.kind == at_svc.PERSONAL_KIND,
        AccessToken.revoked_at.is_(None),
        AccessToken.invalidated_at.is_(None),
    ).values(invalidated_at=datetime.now(_tz.utc),
             invalidated_reason=at_svc.REASON_PASSWORD))
    invalidated = int(res.rowcount or 0)
    await db.commit()
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=caller.id,
        actor_name=caller.display_name or caller.username,
        action="user.reset_password", resource_type="user",
        resource_id=str(user_id),
        resource_name=target.display_name or target.username,
        detail={"username": target.username, "self": caller.id == target.id},
    )
    # 通知本人(强制改密 + 令牌失效两件事都说清)
    try:
        from ..services.notifications import create_notification

        await create_notification(
            db, user_id=target.id, type_="account",
            title="密码已被管理员重置",
            body=("管理员重置了你的密码,请使用临时密码登录后立即修改;"
                  f"你的 {invalidated} 张个人令牌已同步失效(经它们注册的"
                  "任务已暂停,改密后到「个人设置 → 访问令牌」重新生成)"),
            link="/profile#security")
    except Exception:  # noqa: BLE001 — 通知是增强,不阻断
        pass
    # 逐令牌暂停注册方实例(与自服务改密同款,§3.4)
    toks = (await db.execute(select(AccessToken).where(
        AccessToken.user_id == target.id,
        AccessToken.kind == at_svc.PERSONAL_KIND,
        AccessToken.invalidated_reason == at_svc.REASON_PASSWORD,
        AccessToken.invalidated_at.is_not(None),
    ))).scalars().all()
    for tok in toks:
        await at_svc.pause_token_instances(
            db, tok, at_svc.PAUSE_TOKEN_INVALIDATED,
            "令牌因密码重置失效;重新生成后任务自动恢复")
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
    body: UserDeleteIn | None = None,
):
    """Delete ``user_id``(P2-2:资源处置三选一)。

    Authorization: admin only — a non-admin can never delete another account
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

    # D32 系统用户保护:删除 __platform__ 会把平台令牌级联清零
    if getattr(target, "is_system", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "system_user_protected",
                    "message": "系统用户(__platform__)受保护,不能删除"},
        )

    if not has_capability(caller, "users.manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=code_detail(ADMIN_REQUIRED, "需要管理员权限"),
        )

    if target.role in roles_with("users.manage"):
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
        # S1-e:公共项目内容默认受让人 = 执行删除的 Admin(可改选);
        # 校验同款(在场、非目标本人)
        public_transferee = None
        pub_tid = (getattr(body, "public_transfer_to", None)
                   or caller.id)
        if pub_tid == caller.id:
            public_transferee = caller
        else:
            public_transferee = (await db.execute(
                select(User).where(User.id == pub_tid)
            )).scalar_one_or_none()
        if (public_transferee is None
                or public_transferee.id == target.id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="public_transfer_to 用户不存在(或与被删用户相同)",
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

    # ── suite 处置(权限域二期 P1,《Suite成员层、引用分享与浏览镜头-
    #    设计方案》§7.10;必须在场景处置之前)────────────────────────
    # publicize:先删该用户全部 suite(成员行随组合外键 CASCADE;SQLite
    #   不强制 FK,显式删成员行兜底),再置空场景属主 —— suite_members
    #   的组合外键 (scenario_id, owner_id) 在 owner 置 NULL 时失配,
    #   顺序不可倒;无主公共资源上也不该挂「可执行」的组语义。
    # transfer:suite/成员/场景三处 owner_id 同一事务改写 —— 组合外键
    #   DEFERRED 到提交时校验,「只转场景不转 suite」的拆分会被整体
    #   拒绝,处置不可拆分即由库层保证。
    # purge:suite 删除(成员行级联),场景照旧走 scenario_store.delete。
    from ..models.suite import Suite, SuiteMember

    # S7.4:引用处理整段随 share_refs 退役移除(存量已转私有副本;
    # 此前的引用失效/属主变更通知不再有数据源)

    # suite id 删前物化:publicize/purge 都会删掉本用户全部 suite,
    # 删后再查恒空 —— 下方「引用已删 suite 的模板兜底删」(§3.6 通用
    # 约束)需要这份清单。
    own_suite_ids = set((await db.execute(
        select(Suite.id).where(Suite.owner_id == user_id))).scalars())

    if disposal == "publicize":
        # S1.5 起成员行无 owner_id 冗余列:套件删除经 FK CASCADE 收
        # 成员行,不再按属主单独清扫
        await db.execute(
            sa_delete(Suite).where(Suite.owner_id == user_id))
    elif disposal == "transfer":
        # S1-e:公共项目套件默认转给执行 Admin;其余走 transfer_to
        from ..services.zone import public_project_id as _ppid

        await db.execute(
            sa_update(Suite).where(
                Suite.owner_id == user_id,
                Suite.project_id == await _ppid(db))
            .values(owner_id=public_transferee.id))
        await db.execute(
            sa_update(Suite).where(Suite.owner_id == user_id)
            .values(owner_id=transferee.id))
    else:  # purge
        await db.execute(
            sa_delete(Suite).where(Suite.owner_id == user_id))

    # ── 场景处置(三选一)─────────────────────────────────────────
    scenario_ids = list((await db.execute(
        select(ComposerScenario.scenario_id)
        .where(ComposerScenario.owner_id == user_id)
    )).scalars())

    # S1.7 purge 拦截闸(D8):被**平台模板**引用的场景不能随 purge 删除
    # —— 列出受影响模板,先转移/下架模板再删。S1.3 起平台模板只引用
    # 公共项目场景,此闸主要拦迁移前遗留与平台模板引用公共副本的形态。
    if disposal == "purge" and scenario_ids:
        from ..models.integration_task import IntegrationTask as _IT

        _refs = (await db.execute(select(_IT).where(
            _IT.template_id.is_(None),
            _IT.removed_at.is_(None),
            _IT.is_platform_template.is_(True),
            _IT.scenario_id.in_(scenario_ids)))
        ).scalars().all()
        if _refs:
            # rollback 会过期 ORM 实例(属性访问触发懒加载)→ 先物化
            refs_payload = [{"id": t.id, "name": t.name,
                             "scenarioId": t.scenario_id} for t in _refs]
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "platform_template_references",
                        "message": "部分场景被平台模板引用,"
                                   "先转移或删除这些模板再 purge",
                        "templates": refs_payload})
    if disposal == "publicize":
        if scenario_ids:
            # owner_id 显式置空(SET NULL 语义;SQLite 方言 FK 不强制的
            # 双方言兜底),owner_name 快照保留原作者署名
            from ..services.zone import public_project_id
            await db.execute(
                sa_update(ComposerScenario)
                .where(ComposerScenario.owner_id == user_id)
                # 影子写:公共态同步 project_id(S1.1)
                .values(owner_id=None,
                        project_id=await public_project_id(db)))
    elif disposal == "transfer":
        if scenario_ids:
            # S1-e:公共项目内容(维护者位)默认转给执行删除的 Admin
            # (public_transfer_to 可改选);私有区内容走 transfer_to
            from ..services.zone import public_project_id

            pub_label = (public_transferee.display_name
                         or public_transferee.username)
            await db.execute(
                sa_update(ComposerScenario)
                .where(ComposerScenario.owner_id == user_id,
                       ComposerScenario.project_id
                       == await public_project_id(db))
                .values(owner_id=public_transferee.id,
                        owner_name=pub_label))
            transferee_label = transferee.display_name or transferee.username
            await db.execute(
                sa_update(ComposerScenario)
                .where(ComposerScenario.owner_id == user_id)
                .values(owner_id=transferee.id, owner_name=transferee_label))
    else:  # purge
        for sid in scenario_ids:
            await scenario_store.delete(db, sid)

    # ── 报告定义处置(S1.6 补:此前删用户零处理,owner 悬空)─────
    if disposal == "transfer":
        from ..models.report_definition import ReportDefinitionRow
        from ..services.zone import public_project_id as _ppid3

        await db.execute(
            sa_update(ReportDefinitionRow).where(
                ReportDefinitionRow.owner_id == user_id,
                ReportDefinitionRow.project_id == await _ppid3(db))
            .values(owner_id=public_transferee.id))
        await db.execute(
            sa_update(ReportDefinitionRow).where(
                ReportDefinitionRow.owner_id == user_id)
            .values(owner_id=transferee.id))
    else:
        from ..models.report_definition import ReportDefinitionRow
        await db.execute(
            sa_update(ReportDefinitionRow).where(
                ReportDefinitionRow.owner_id == user_id)
            .values(owner_id=None))

    # ── 访问令牌 + 集成任务处置(webhook v4 §3.6)──────────────────
    # 修现存外键缺陷:此前 delete_user 对 integration_tasks 零处理,
    # owner_id/holder_id 外键无 ON DELETE —— 删除任何拥有模板或实例的
    # 用户都会违反外键而失败。处置沿用三选一,受让人沿用同一 transferee。
    from ..models.access_token import AccessToken
    from ..models.integration_task import IntegrationTask
    from ..services.webhook_outbox import fail_pending_of_token

    # 个人令牌:删除前其 pending 投递显式置 failed(token_deleted),再随
    # 用户整删(CASCADE);executions.token_id 等 SET NULL,追溯靠快照
    user_tokens = (await db.execute(select(AccessToken).where(
        AccessToken.user_id == user_id))).scalars().all()
    for tok in user_tokens:
        await fail_pending_of_token(db, tok.id, "token_deleted")
    await db.execute(
        sa_delete(AccessToken).where(AccessToken.user_id == user_id))

    own_tpls = (await db.execute(select(IntegrationTask).where(
        IntegrationTask.template_id.is_(None),
        IntegrationTask.removed_at.is_(None),
        IntegrationTask.owner_id == user_id))).scalars().all()
    disposed_tasks: list[tuple[IntegrationTask, str]] = []

    from ..services import maintenance_transfer as _mt
    from ..services.zone import public_project_id as _ppid2

    _pub_pid = await _ppid2(db)
    for tpl in own_tpls:
        if disposal == "transfer":
            # S1-e:公共项目模板默认转给执行 Admin(维护者位),连带
            # 走共用服务(令牌解绑 + 原属主自有实例删除);私有模板
            # 转给 transfer_to(同款连带,处置口径不变)
            _to = (public_transferee if tpl.project_id == _pub_pid
                   else transferee)
            tpl.owner_id = _to.id
            tpl.token_id = None
            await db.execute(sa_delete(IntegrationTask).where(
                IntegrationTask.template_id == tpl.id,
                IntegrationTask.holder_id == user_id))
            disposed_tasks.append((tpl, "transfer"))
        elif disposal == "publicize":
            # 模板连同全部实例删除;通知受影响订阅者(authz C1:平台
            # 模板转挂 __platform__ 的分支随平台模式退役;平台模板本就
            # 归 __platform__ 持有,不经过个人账号处置)
            holders = (await db.execute(select(IntegrationTask.holder_id).where(
                IntegrationTask.template_id == tpl.id,
                IntegrationTask.holder_id.is_not(None),
                IntegrationTask.holder_id != user_id))).scalars().all()
            for uid in holders:
                try:
                    await create_notification(
                        db, user_id=uid, type_="integration",
                        title=f"集成任务「{tpl.name}」已删除",
                        body="任务属主账号已注销,模板随之删除;"
                             "卡片会显示「已移除」,可自行删卡")
                except Exception:  # noqa: BLE001
                    await db.rollback()
            await db.execute(sa_delete(IntegrationTask).where(
                IntegrationTask.template_id == tpl.id))
            # 模板行本身也删(方案 §3.6;评审 2026-11-05 P1:漏删会
            # 被下方 owner_id 统一更新挂到 __platform__ 名下,留下
            # 属主为系统用户的僵尸模板)
            await db.delete(tpl)
            disposed_tasks.append((tpl, "publicize"))
        else:  # purge
            # 模板连同实例删除(purge 删除场景;scenario_id 无外键,
            # 保留只会留下僵尸任务)
            await db.execute(sa_delete(IntegrationTask).where(
                IntegrationTask.template_id == tpl.id))
            await db.delete(tpl)
            disposed_tasks.append((tpl, "purge"))

    # S1.7(D10):软删模板**直接删除** —— 不再兜底挂到 __platform__
    #(挂靠行会污染平台模板的属主判定;平台模板改 is_platform_template
    # 显式标记,0040 已迁移存量)。连带其实例行(卡片本就「已移除」)。
    await db.execute(sa_delete(IntegrationTask).where(
        IntegrationTask.template_id.in_(select(IntegrationTask.id).where(
            IntegrationTask.owner_id == user_id,
            IntegrationTask.removed_at.is_not(None)))))
    await db.execute(sa_delete(IntegrationTask).where(
        IntegrationTask.owner_id == user_id,
        IntegrationTask.removed_at.is_not(None)))
    # 剩余**活**模板及其实例的 owner_id 跟随新属主(transfer → 受让人
    # /公共分流入循环内;publicize/purge 的活模板已在处置循环删净,
    # 此处仅为外键兜底),否则删除用户行违反 owner_id 外键。
    new_owner_id = (transferee.id if disposal == "transfer" else None)
    if new_owner_id is not None:
        await db.execute(sa_update(IntegrationTask).where(
            IntegrationTask.owner_id == user_id,
        ).values(owner_id=new_owner_id))

    # 该用户持有的订阅者实例:三种处置一律删除
    await db.execute(sa_delete(IntegrationTask).where(
        IntegrationTask.template_id.is_not(None),
        IntegrationTask.holder_id == user_id))

    # 通用约束:凡是会删除场景或 suite 的处置,同时删除引用它们的模板
    # (publicize 场景转公共不删;suite 删除发生在 publicize/purge 两处置,
    # 引用已删 suite 的模板 —— 含其他用户保留的模板 —— 一并兜底删)
    if disposal != "transfer":
        removed_scen = set(scenario_ids) if disposal == "purge" else set()
        removed_suites = own_suite_ids
        cond = None
        from sqlalchemy import or_ as _or
        if removed_scen:
            cond = IntegrationTask.scenario_id.in_(removed_scen)
        if removed_suites:
            suite_cond = IntegrationTask.suite_id.in_(removed_suites)
            cond = _or(cond, suite_cond) if cond is not None else suite_cond
        if cond is not None:
            # publicize 上面已删全部本用户模板;suite/场景引用的模板兜底删
            dangling = (await db.execute(select(IntegrationTask).where(
                IntegrationTask.template_id.is_(None),
                IntegrationTask.removed_at.is_(None),
                cond))).scalars().all()
            for tpl in dangling:
                await db.execute(sa_delete(IntegrationTask).where(
                    IntegrationTask.template_id == tpl.id))
                await db.delete(tpl)

    for tpl, how in disposed_tasks:
        await audit_svc.record(
            db, actor_id=caller.id, actor_name=caller_label,
            action="integration.task.dispose",
            resource_type="integration", resource_id=str(tpl.id),
            resource_name=tpl.name,
            detail={"disposal": how,
                    "new_owner": (transferee.id if how == "transfer"
                                  and disposal == "transfer" else None),
                    })

    # 受让人通知(§3.6):并入 resource_transferred —— 场景或集成任务
    # 任一非空即发;正文逐个列出任务及当前状态
    transfer_tasks = [(t, h) for t, h in disposed_tasks if h == "transfer"]
    transfer_notify_detail: list[str] = []
    for tpl, _ in transfer_tasks:
        transfer_notify_detail.append(f"「{tpl.name}」需启动以建立实例")

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

    # ── P1a 最小显式级联(NO ACTION 两表;个人别名随 S6 退役)──
    await db.execute(
        sa_delete(AuthSession).where(AuthSession.owner_id == user_id))
    await db.execute(
        sa_delete(ConstantEntry).where(ConstantEntry.owner_id == user_id))

    await db.delete(target)
    await db.commit()

    # 处置后动作:转让通知 + 审计(特权写,权限方案 §6)
    # §3.6:场景**或集成任务**任一非空即发;任务逐个列出当前状态
    if disposal == "transfer" and (scenario_ids or transfer_notify_detail):
        parts = []
        if scenario_ids:
            parts.append(f"{len(scenario_ids)} 个场景")
        if transfer_notify_detail:
            parts.append(f"{len(transfer_notify_detail)} 个集成任务"
                         + (";" + ";".join(transfer_notify_detail)
                            if transfer_notify_detail else ""))
        await create_notification(
            db,
            user_id=transferee.id,
            type_="resource_transferred",
            title="、".join(parts) + "已转让给你",
            body=f"管理员将 {target.display_name or target.username} 的 "
                 + "、".join(parts)
                 + ("转让给你,请查收。"
                    + ("集成任务在集成中心接管。" if transfer_notify_detail
                       else "")),
            commit=False,
        )
    await audit_svc.record(
        db,
        actor_id=caller.id, actor_name=caller_label,
        action="user.delete",
        resource_type="user", resource_id=str(user_id),
        resource_name=target.display_name or target.username,
        detail={
            "username": target.username,
            "disposal": disposal,
            "transfer_to": transferee.id if transferee else None,
            "transfer_to_name": (
                transferee.display_name or transferee.username
            ) if transferee else None,
            "scenarios": len(scenario_ids),
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)