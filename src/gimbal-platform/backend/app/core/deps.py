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
    """入站分流依赖(webhook 设计 v3 P1 §4.2):按 Authorization 前缀
    分流 ``Bearer gic_…``(入站凭证)/ 其余(JWT,行为与
    :func:`get_current_user` 完全一致)。

    * 入站:凭证命中、未吊销、别名 ``inbound_enabled`` → 得到调用方
      别名;带 ``X-Gimbal-Grant`` 则校验命中/未过期/未撤销/属同一别名,
      失败 403;无 grant → 平台模式(owner=``__platform__`` 系统用户)。
      认证失败(401/403)写审计(v3 定案)。
    * JWT:JWT 请求带 ``X-Gimbal-Grant`` 直接 400 —— grant 只对入站
      凭证有意义,混用是客户端错误,不静默忽略。

    返回 :class:`~app.services.inbound_identity.Principal`(JWT 情况下
    caller_alias=None → 该执行不回调)。
    """
    from ..services import audit as audit_svc
    from ..services.inbound_identity import (
        CREDENTIAL_PREFIX, GRANT_HEADER, InboundAuthError, Principal,
        resolve_inbound_principal,
    )

    auth = request.headers.get("authorization") or ""
    grant_header = (request.headers.get(GRANT_HEADER) or "").strip() or None
    if not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer credential")
    token = auth[7:].strip()
    if token.startswith(CREDENTIAL_PREFIX):
        try:
            return await resolve_inbound_principal(db, token, grant_header)
        except InboundAuthError as e:
            # 认证失败入审计(v3 定案):不记完整令牌,只记哈希前 8 位
            # 定位用。best-effort(audit.record 自吞失败)。
            await audit_svc.record(
                db, actor_id=None, actor_name="inbound",
                action="inbound.auth_failed",
                resource_type="alias",
                detail={"reason": e.code, "message": e.message},
            )
            raise HTTPException(
                status_code=e.status_code,
                detail={"code": e.code, "message": e.message},
            ) from e
    if grant_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "grant_header_on_jwt",
                "message": "X-Gimbal-Grant 只能与入站凭证(gic_)同用",
            })
    user = await _load_jwt_user(db, token)
    return Principal(
        user=user, identity_mode="personal", caller_alias=None)


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
    """入站分流版执行可见性(webhook 设计 v3 §4.4/§5.6,D8)。

    比 :func:`get_owned_execution` 宽两档(只用于三个只读查询端点
    detail/rows/events;写面端点仍走 owner 闸):

    * 入站凭证:只看 ``caller_alias_name`` 等于自己别名的执行
      (平台模式 + 经该别名注册的个人模式);
    * JWT:owner 本人;admin;或执行 owner 为系统用户(平台模式)且
      当前用户是该执行 caller 别名的属主 —— 别名属主在执行列表页
      看不到平台模式执行(「我的执行」按 owner 过滤),详情/排查走
      本判定 + 别名页的投递查询。
    """
    from ..models.execution import Execution
    from ..models.service_alias import ServiceAlias

    ex = await session.get(Execution, execution_id)
    if ex is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"execution not found: {execution_id}",
        )
    if getattr(principal, "inbound", False):
        if ex.caller_alias_name == principal.caller_alias:
            return ex
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"execution not found: {execution_id}",
        )
    user = principal.user
    if ex.owner_id == user.id or user.role == "admin":
        return ex
    if ex.owner_id is not None and ex.caller_alias_name:
        owner = await session.get(User, ex.owner_id)
        if owner is not None and owner.is_system:
            alias = await session.get(ServiceAlias, ex.caller_alias_name)
            if alias is not None and alias.owner_user_id == user.id:
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
    """写面(取消)的入站分流版(收尾评审 2026-11-02 G2)。

    * 入站凭证:``caller_alias_name`` 等于自己别名 —— 与只读查询同一
      规则,调用方能取消自己经由该别名发起的执行(平台模式 owner 是系统
      用户、个人模式 owner 是 grant 用户,按 owner 判它们都取消不了);
    * JWT:维持 owner 本人 —— **不**随 :func:`get_visible_execution` 放宽
      到 admin / 别名属主,写面不扩。

    不满足一律 404(不泄露存在性)。
    """
    from ..models.execution import Execution

    ex = await session.get(Execution, execution_id)
    if ex is not None:
        if getattr(principal, "inbound", False):
            if ex.caller_alias_name == principal.caller_alias:
                return ex
        elif ex.owner_id == principal.user.id:
            return ex
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"execution not found: {execution_id}",
    )