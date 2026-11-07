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
from ._ownership import roles_with as _roles_with
from ..schemas.auth import (
    ChangePasswordIn,
    LoginIn,
    MeOut,
    RefreshIn,
    RegisterIn,
    TokenOut,
    UserPublic,
)
from ..core.config import settings
from ._codes import (
    ACCOUNT_DISABLED, BAD_CREDENTIALS, NAME_TAKEN_ON_REGISTER,
    REGISTRATION_CLOSED, code_detail,
)
from ._name_checks import assert_name_available

router = APIRouter(prefix="/auth", tags=["auth"])


# ── helpers ──────────────────────────────────────────────────────
def _user_public(u: User) -> UserPublic:
    return UserPublic.model_validate(u)


def _token_out(u: User) -> TokenOut:
    # webhook v4 §3.6:access 与 refresh 都带 tv(= users.token_version),
    # 改密「退出其他会话」+1 后旧 JWT(含 refresh)整体失效
    access = create_access_token(subject=u.id, tv=u.token_version)
    refresh = create_refresh_token(subject=u.id, tv=u.token_version)
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
    # 首个真人用户判定 —— 只数 is_system=False(整体评审 2026-10-15:
    # 0015 迁移为集成平台模式种了 ``__platform__`` 系统用户,空库建库后
    # users 表恒有 1 行,此前 count()==0 永不成立 → 上线空库首个注册者
    # 拿不到 admin,且全站无 admin 可开号)。
    humans = (await db.execute(
        select(func.count()).select_from(User).where(
            User.is_system == False)  # noqa: E712
    )).scalar_one()
    first = humans == 0
    if not first and not settings.REGISTRATION_OPEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=code_detail(
                REGISTRATION_CLOSED, "自助注册已关闭,请联系管理员开通账号"),
        )
    # Normalize display_name the same way patch_user does: it doubles as
    # composer-ownership identity, so " Bob " / "Bob" must not coexist.
    payload.display_name = (payload.display_name or "").strip()
    # 用户名/display_name 查重 + 双向冲突检查(见 _name_checks)。
    await assert_name_available(
        db,
        username=payload.username,
        display_name=payload.display_name or None,
        code=NAME_TAKEN_ON_REGISTER,
    )
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role="super_admin" if first else "user",
    )
    db.add(user)
    await db.flush()
    if first:
        # 并发双管理员窗口自愈(仓内审计 P9):count-then-insert 竞态会让
        # 两个并发首注册都拿到 super_admin —— 插入后复检,若已有更早的
        # super_admin 在场,本单降级回 user。
        earlier = (await db.execute(
            select(func.count()).select_from(User).where(
                User.role.in_(_roles_with("users.manage")),
                User.id < user.id,
                User.is_system == False)  # noqa: E712
        )).scalar_one()
        if earlier:
            user.role = "user"
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
            detail=code_detail(BAD_CREDENTIALS, "用户名或密码错误"),
        )
    if getattr(user, "is_system", False):
        # 0015 平台系统用户:持有凭证池,不可登录平台
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=code_detail(BAD_CREDENTIALS, "用户名或密码错误"),
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=code_detail(ACCOUNT_DISABLED, "账号已停用"),
        )
    return _token_out(user)


# ── POST /refresh ────────────────────────────────────────────────
@router.post("/change-password", response_model=TokenOut)
async def change_password(
    payload: ChangePasswordIn, user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenOut:
    """自服务改密(webhook v4 §3.6):核验旧密码 → 写新哈希;两个可选
    动作默认勾选 —— ``invalidateTokens``:本人全部个人令牌落库失效
    (原因 password,平台令牌不受影响),N > 0 时发站内通知;
    ``logoutOthers``:token_version + 1 并返回新 JWT(其他会话的
    access/refresh 因 tv 过期全体 401)。审计按特权写口径不记(本人
    常规自管);令牌失效面走 token.invalidate 审计。"""
    from sqlalchemy import select as _select

    from ..services import access_token as at_svc

    row = (await db.execute(
        _select(User).where(User.id == user.id)
    )).scalar_one()
    if not verify_password(payload.old_password, row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "bad_old_password", "msg": "旧密码不正确"},
        )
    row.password_hash = hash_password(payload.new_password)
    row.must_change_password = False
    invalidated = 0
    if payload.invalidate_tokens:
        # 个人令牌全部落库失效(§3.6):停用/改密是仅有的两个失效入口;
        # 注册方实例按 §3.4 → token_invalidated 暂停并通知
        from ..models.access_token import AccessToken
        from sqlalchemy import update as _sa_update
        res = await db.execute(_sa_update(AccessToken).where(
            AccessToken.user_id == row.id,
            AccessToken.kind == at_svc.PERSONAL_KIND,
            AccessToken.revoked_at.is_(None),
            AccessToken.invalidated_at.is_(None),
        ).values(invalidated_at=at_svc.now_utc(),
                 invalidated_reason=at_svc.REASON_PASSWORD))
        invalidated = int(res.rowcount or 0)
    if payload.logout_others:
        row.token_version = int(row.token_version or 0) + 1
    await db.commit()
    if invalidated:
        # §3.6:N 张访问令牌已因改密失效,需重新生成
        from ..services import audit as audit_svc
        await audit_svc.record(
            db, actor_id=row.id,
            actor_name=row.display_name or row.username,
            action="token.invalidate", resource_type="user",
            resource_id=str(row.id),
            detail={"reason": at_svc.REASON_PASSWORD, "count": invalidated})
        try:
            from ..services.notifications import create_notification
            await create_notification(
                db, user_id=row.id, type_="integration",
                title=f"{invalidated} 张访问令牌已因改密失效",
                body="经它们注册的任务已暂停;如需继续使用,请到"
                     "「个人设置 → 访问令牌」重新生成(完成后任务自动恢复)",
                link="/profile#tokens")
        except Exception:  # noqa: BLE001 — 通知是增强
            pass
        # 逐令牌暂停注册方实例 + 通知(§3.4)
        toks = (await db.execute(_select(AccessToken).where(
            AccessToken.user_id == row.id,
            AccessToken.kind == at_svc.PERSONAL_KIND,
            AccessToken.invalidated_reason == at_svc.REASON_PASSWORD,
            AccessToken.invalidated_at.is_not(None),
        ))).scalars().all()
        for tok in toks:
            await at_svc.pause_token_instances(
                db, tok, at_svc.PAUSE_TOKEN_INVALIDATED,
                "令牌因改密失效;重新生成后任务自动恢复")
        await db.commit()
    return _token_out(await db.get(User, row.id))


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
    # webhook v4 §3.6:refresh 同样带 tv —— 改密「退出其他会话」后,
    # 旧 refresh 不能再换新 access(auth.py:164 只查 is_active 的缺口)
    if int(data.get("tv") or 0) != int(user.token_version or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_version_stale",
                    "message": "会话已被新密码或「退出其他会话」失效,"
                               "请重新登录"},
        )
    return _token_out(user)


# ── GET /me ──────────────────────────────────────────────────────
@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser,
             db: Annotated[AsyncSession, Depends(get_db)]) -> MeOut:
    # authz W2:capabilities 按表 A 求值(前端 can() 的依据);
    # S1.1:projects = 我所在的普通项目(切换器数据源;公共项目不落
    # 成员行,不在此列 —— 全员可读是表 B 派生,不需要成员关系)
    from sqlalchemy import select

    from ._ownership import capabilities_of
    from ..models.project import Project, ProjectMember

    rows = (await db.execute(
        select(Project.id, Project.name, Project.kind, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
        .order_by(Project.id))).all()
    return MeOut(user=_user_public(user),
                 capabilities=capabilities_of(user.role),
                 must_change_password=bool(user.must_change_password),
                 projects=[{"id": pid, "name": name, "kind": kind,
                            "role": role}
                           for pid, name, kind, role in rows])