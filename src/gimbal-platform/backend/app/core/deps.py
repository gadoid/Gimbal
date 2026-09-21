"""FastAPI Depends (current user, admin gate, db)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .security import decode_token
from ..models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
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


CurrentUser = Annotated[User, Depends(get_current_user)]


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
# operator = 技术运营权(适配/别名/默认值/信号);admin 天然包含(§1.1)。
OperatorUser = Annotated[User, Depends(require_role("operator", "admin"))]


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
