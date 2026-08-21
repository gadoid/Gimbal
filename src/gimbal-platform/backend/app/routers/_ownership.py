"""Shared composer ownership check.

One canonical rule for the V3 composer routers (scenarios, data-sets,
runs):

* row ownership = ``owner_id`` (int user id) — the single authority
* admins bypass everything

Each call-site keeps its own 403 ``detail`` payload (string or dict) so
API responses stay byte-identical.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def _user_matches(user: Any, owner_id: int) -> bool:
    """Canonical identity match for the composer tables."""
    return user.id == owner_id


def ensure_owner(user: Any, owner_id: int, detail: Any) -> None:
    """403 unless ``user`` is the row owner or an admin.

    ``detail`` is passed through verbatim to the HTTPException so each
    router keeps its existing error contract.
    """
    if not user.is_admin and not _user_matches(user, owner_id):
        raise HTTPException(status_code=403, detail=detail)


def can_read_scenario(
    user: Any,
    *,
    owner_id: int,
    visibility: str = "private",
) -> bool:
    """读侧规则(场景库收紧后):admin 全可见;public 所有登录用户
    可读;private 仅属主(owner_id)可见。
    """
    if user.is_admin:
        return True
    if visibility == "public":
        return True
    return _user_matches(user, owner_id)
