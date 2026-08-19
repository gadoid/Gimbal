"""Shared composer ownership check.

One canonical rule for the V3 composer routers (scenarios, cases,
data-sets, runs):

* caller identity  = ``display_name or username`` (string match — the
  composer tables store the display name, unlike V1 which uses int ids)
* row ownership    = ``owner`` / ``created_by`` column
* empty owner      = LOCKED (legacy / migrated / plate-synced rows);
  only an admin may touch it
* admins bypass everything

Each call-site keeps its own 403 ``detail`` payload (string or dict) so
API responses stay byte-identical.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def _user_matches(
    user: Any, owner_name: str | None, owner_id: int
) -> bool:
    """Canonical identity match for the composer tables.

    ``owner_id > 0`` (P1 起写入) → int user.id 比对;存量行 owner_id==0
    回退 display_name/username 名字比对(P2 迁移脚本回填后消亡)。
    """
    if owner_id:
        return user.id == owner_id
    user_name = user.display_name or user.username
    return user_name == (owner_name or "")


def ensure_owner(
    user: Any,
    owner_name: str | None,
    detail: Any,
    *,
    owner_id: int = 0,
) -> None:
    """403 unless ``user`` is the row owner or an admin.

    ``detail`` is passed through verbatim to the HTTPException so each
    router keeps its existing error contract.
    """
    if not user.is_admin and not _user_matches(user, owner_name, owner_id):
        raise HTTPException(status_code=403, detail=detail)


def can_read_scenario(
    user: Any,
    owner_name: str | None,
    *,
    owner_id: int = 0,
    visibility: str = "private",
) -> bool:
    """读侧规则(场景库收紧后):admin 全可见;public 所有登录用户
    可读;private 仅属主(owner_id 优先,存量行按名字回退)可见。
    取代 V1 的"目录即真相"(mine/public 目录)模型。
    """
    if user.is_admin:
        return True
    if visibility == "public":
        return True
    return _user_matches(user, owner_name, owner_id)
