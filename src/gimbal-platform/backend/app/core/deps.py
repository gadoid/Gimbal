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
    request: Request,
) -> User:
    user = await _load_jwt_user(db, token)
    # authz W6 只能改密门:must_change_password 为真 → 一律 403
    # password_change_required,白名单三口(评审 R4:前端登录态靠
    # /auth/me 证明 —— 拦了 me,改密页永远到不了):
    #   /api/auth/me(响应带 must_change_password,路由守卫跳转依据)
    #   /api/auth/refresh(会话续期)
    #   /api/auth/change-password(唯一的出口)
    # 令牌路径不进此门(重置已把个人令牌整体失效,天然覆盖)。
    if user.must_change_password and request.url.path not in (
            "/api/auth/me", "/api/auth/refresh", "/api/auth/change-password"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "password_change_required",
                "message": "密码已被重置,请先修改密码后再使用其他功能",
            },
        )
    return user


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
      判定。失败
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


# ── 能力门(authz W2,表 A 驱动)───────────────────────────────────
# role 不进 JWT:每请求查库,升降级即时生效(§1.3)。前端守卫只是 UX,
# 这些依赖才是边界(§0.4)。表 A(_ownership.CAPABILITIES)是唯一规则
# 来源,错误契约统一 {code: capability_forbidden, capability}
# (取代旧的 role_forbidden / admin_only 两种形状,方案 9.7)。


def require_capability(capability: str):
    """能力门工厂:表 A 判定;不满足 → 403 capability_forbidden。"""
    # 延迟 import:routers 包 __init__ 会拉起各 router → 回引本模块,
    # 顶部 import 会成环(_ownership 自身只依赖 models,无环)。
    from ..routers._ownership import roles_with

    allowed = roles_with(capability)

    async def _dep(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "capability_forbidden",
                    "capability": capability,
                    "message": f"requires capability: {capability}",
                },
            )
        return user

    return _dep


async def require_admin(user: CurrentUser) -> User:
    """users.manage 能力门的具名形态(表 A:super_admin —— 原 admin 级,
    W1 更名后)。既有 AdminUser 消费面不变。"""
    from ..routers._ownership import roles_with

    if user.role not in roles_with("users.manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "capability_forbidden",
                "capability": "users.manage",
                "message": "requires capability: users.manage",
            },
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
# 技术运营面(原 member+,W1 更名后 = admin+)。名字保留:9 个 router 的
# import 面不动,判定已由表 A 驱动;W8 后端清理时可整体更名。
MemberUser = Annotated[User, Depends(require_capability("ops.write"))]


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


async def can_view_execution(principal, ex, session: AsyncSession) -> bool:
    """执行可读判定(单一实现;get_visible_execution 与报告 / 批次汇总共用)。

    执行及其一切子资源只有属主可见(authz W4,方案 §9.3):
    * 令牌:``execution.token_id == 当前令牌``(D8);
    * JWT:owner 本人。

    admin/super_admin 的越属主旁路与「平台身份执行对 admin+ 可见」的
    平台分支均已删(W4)——admin 排查走审计日志。
    """
    if getattr(principal, "is_token", False):
        return ex.token_id == principal.token_id
    return ex.owner_id == principal.user.id


async def get_visible_execution(
    principal: Annotated["object", Depends(principal_or_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    execution_id: Annotated[int, Path(ge=1)],
):
    """执行可见性(webhook v4 §5.2/D8):只读三端点(detail/rows/events)。

    判定见 :func:`can_view_execution`;不可见与不存在同为 404(不泄露存在性)。
    """
    from ..models.execution import Execution

    ex = await session.get(Execution, execution_id)
    if ex is None or not await can_view_execution(principal, ex, session):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"execution not found: {execution_id}",
        )
    return ex


async def get_controllable_execution(
    principal: Annotated["object", Depends(principal_or_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    execution_id: Annotated[int, Path(ge=1)],
):
    """写面(取消)的令牌分流版(§5.2/D25)。

    * 令牌:``execution.token_id == 当前令牌``(D25 —— 只能取消本令牌
      发起的执行);
    * JWT:owner 本人。

    平台分支已删(authz W4):admin+ 不再可取消平台身份的他人执行。
    不满足一律 404(不泄露存在性)。
    """
    from ..models.execution import Execution

    ex = await session.get(Execution, execution_id)
    if ex is not None:
        if getattr(principal, "is_token", False):
            if ex.token_id == principal.token_id:
                return ex
        elif ex.owner_id == principal.user.id:
            return ex
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"execution not found: {execution_id}",
    )
