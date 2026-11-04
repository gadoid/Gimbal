"""FastAPI Depends (current user, admin gate, db, 入站分流)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .security import decode_token
from ..models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def _load_jwt_user(db: AsyncSession, token: str) -> User:
    try:
        payload = decode_token(token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not an access token")
    user_id = int(payload["sub"])
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found or inactive")
    # webhook v4 §3.6:改密「退出其他会话」—— access/refresh 都带 tv,
    # 不等于当前 token_version 即 401(旧 JWT 整体失效)
    if int(payload.get("tv") or 0) != int(user.token_version or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_version_stale",
                    "message": "会话已被新密码或「退出其他会话」失效,请重新登录"},
        )
    return user


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    return await _load_jwt_user(db, token)


CurrentUser = Annotated[User, Depends(get_current_user)]


async def principal_or_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """入站分流依赖(webhook v4 §2.1):按 Authorization 前缀分流
    ``Bearer gtk_…``(访问令牌)/ 其余(JWT,行为与
    :func:`get_current_user` 完全一致)。

    * 令牌::func:`app.services.access_token.authenticate` —— hash 命中
      → 状态机(吊销/失效/到期)→ 个人令牌按属主当前角色与启用状态派生
      判定(平台令牌跳过,``__platform__`` 种子 role='user')。失败
      401/403 写审计 ``inbound.denied``(hash 命中的令牌行归到该令牌
      名下,§7.2;未命中则资源列为空)。
    * 旧前缀 ``gic_`` / ``ggt_``:401 ``token_invalid``,message 注明
      v4 仅接受 ``gtk_``(§2.2)。

    返回 :class:`~app.services.access_token.Principal`(JWT 情况下
    token=None → 该执行不回调)。
    """
    from ..services import access_token as at_svc
    from ..services import audit as audit_svc
    from ..services.access_token import Principal, TokenAuthError

    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer credential")
    token = auth[7:].strip()
    if token.startswith(at_svc.LEGACY_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": at_svc.ERR_TOKEN_INVALID,
                    "message": at_svc.LEGACY_TOKEN_MESSAGE},
        )
    if token.startswith(at_svc.TOKEN_PREFIX):
        try:
            return await at_svc.authenticate(db, token)
        except TokenAuthError as e:
            # 认证失败入审计(§7.2):hash 命中某张令牌时(含已吊销/失效/
            # 到期)资源列记该令牌 id;属主角色/启用面命中时同理。best-effort。
            hit = e.token
            await audit_svc.record(
                db, actor_id=None, actor_name="inbound",
                action="inbound.denied",
                resource_type="access_token" if hit is not None else None,
                resource_id=str(hit.id) if hit is not None else None,
                detail={"reason": e.code, "message": e.message,
                        "token_hint": hit.token_hint if hit is not None else None,
                        "token_kind": hit.kind if hit is not None else None},
            )
            raise HTTPException(
                status_code=e.status_code,
                detail={"code": e.code, "message": e.message},
            ) from e
    user = await _load_jwt_user(db, token)
    return Principal(user=user, identity_mode="personal")


# ── 三级单角色(M2.5,权限方案 §1)─────────────────────────────────
# role 不进 JWT:每请求查库,升降级即时生效(§1.3)。前端守卫只是 UX,
# 这些依赖才是边界(§0.4)。
def require_role(*roles: str):
    """角色门工厂:允许的角色集合;不满足 → 403。"""
    allowed = frozenset(roles)

    async def _dep(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "role_forbidden",
                    "message": f"requires role in {sorted(allowed)}",
                },
            )
        return user

    return _dep


async def require_admin(user: CurrentUser) -> User:
    """Admin 门(require_role("admin") 的具名形态;既有 AdminUser 消费面不变)。"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_only: this route requires an administrator",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
# member = 技术运营权(适配/别名/默认值/信号);admin 天然包含(§1.1)。
# (2026-09-29 三级更名:原 operator 级现叫 member,原 member 级现叫 user。)
MemberUser = Annotated[User, Depends(require_role("member", "admin"))]


async def get_owned_execution(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    execution_id: Annotated[int, Path(ge=1)],
):
    """Resolve an Execution row scoped to ``user``.

    Returns 404 when the row is missing OR owned by someone else — that
    "merge" of 404/403 is intentional: it does not leak ownership of
    executions the caller can't see.
    """
    # Late import to avoid a circular: ``models.execution`` imports Base
    # from ``core.db``, and we want to keep ``core.deps`` free of the
    # heavier model graph.
    from ..models.execution import Execution

    ex = await session.get(Execution, execution_id)
    if ex is None or ex.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"execution not found: {execution_id}",
        )
    return ex


async def get_visible_execution(
    principal: Annotated["object", Depends(principal_or_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    execution_id: Annotated[int, Path(ge=1)],
):
    """执行可见性(webhook v4 §5.2/D8):只读三端点(detail/rows/events)。

    * 令牌:``execution.token_id == 当前令牌``,否则 404(D8 —— 令牌
      只能查本令牌发起的执行);
    * JWT:owner 本人;admin;或执行 owner 为系统用户(平台模式)且
      当前用户 member+ —— 平台身份的执行与投递对 member+ 可见(D7)。
    """
    from ..models.execution import Execution
    from ..models.user import User as _U

    ex = await session.get(Execution, execution_id)
    if ex is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"execution not found: {execution_id}",
        )
    if getattr(principal, "is_token", False):
        if ex.token_id == principal.token_id:
            return ex
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"execution not found: {execution_id}",
        )
    user = principal.user
    if ex.owner_id == user.id or user.role == "admin":
        return ex
    if ex.owner_id is not None:
        owner = await session.get(_U, ex.owner_id)
        if owner is not None and owner.is_system \
                and user.role in ("member", "admin"):
            return ex
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"execution not found: {execution_id}",
    )


async def get_controllable_execution(
    principal: Annotated["object", Depends(principal_or_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    execution_id: Annotated[int, Path(ge=1)],
):
    """写面(取消)的令牌分流版(§5.2/D25)。

    * 令牌:``execution.token_id == 当前令牌``(D25 —— 只能取消本令牌
      发起的执行);
    * JWT:owner 本人;平台身份的执行(owner 为系统用户)member+ 可取消;
      其余不扩。

    不满足一律 404(不泄露存在性)。
    """
    from ..models.execution import Execution
    from ..models.user import User as _U

    ex = await session.get(Execution, execution_id)
    if ex is not None:
        if getattr(principal, "is_token", False):
            if ex.token_id == principal.token_id:
                return ex
        else:
            user = principal.user
            if ex.owner_id == user.id:
                return ex
            if ex.owner_id is not None and user.role in ("member", "admin"):
                owner = await session.get(_U, ex.owner_id)
                if owner is not None and owner.is_system:
                    return ex
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"execution not found: {execution_id}",
    )
