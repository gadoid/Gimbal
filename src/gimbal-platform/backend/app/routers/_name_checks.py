"""Shared username / display-name availability checks.

display_name 兼作 composer 资源归属标识(scenario / data-set 行存它为
``owner``),因此必须全局唯一、且不得与任何 username 相互冒用 —— 否则
成员可通过采用他人 display_name 接管其资源(提权向量)。

曾被 auth.register 与 users.create_user / patch_user 三处复制粘贴,
现收敛于此。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..models.user import User

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def assert_name_available(
    db: AsyncSession,
    *,
    username: str | None = None,
    display_name: str | None = None,
    code: int,
    exclude_id: int | None = None,
) -> None:
    """Raise 409 when ``username`` / ``display_name`` 已被占用或互相冲突。

    * ``username`` 非空 → 检查:①用户名已被注册;②用户名与已有
      display_name 冲突(归属匹配用 ``display_name or username``)。
    * ``display_name`` 非空 → 检查它与任何 display_name / username
      唯一(``exclude_id`` 用于 patch 自身时排除自己)。
    """
    if username:
        existing = (
            await db.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": code, "msg": "用户名已被占用"},
            )
        name_clash = (
            await db.execute(select(User).where(User.display_name == username))
        ).scalar_one_or_none()
        if name_clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": code, "msg": "用户名与已有显示名冲突（作为资源归属标识必须唯一）"},
            )
    if display_name:
        cond = (User.display_name == display_name) | (User.username == display_name)
        if exclude_id is not None:
            cond = cond & (User.id != exclude_id)
        clash = (
            await db.execute(select(User).where(cond))
        ).scalar_one_or_none()
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": code, "msg": "显示名已被占用（作为资源归属标识必须唯一）"},
            )
