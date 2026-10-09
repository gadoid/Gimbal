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

from ..models.composer_scenario import ComposerScenario


def _user_matches(user: Any, owner_id: int) -> bool:
    """Canonical identity match for the composer tables."""
    return user.id == owner_id


def ensure_owner(user: Any, owner_id: int, detail: Any) -> None:
    """403 unless ``user`` is the row owner or an admin.

    ``detail`` is passed through verbatim to the HTTPException so each
    router keeps its existing error contract.
    """
    if user.role != "admin" and not _user_matches(user, owner_id):
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
    if user.role == "admin":
        return True
    if visibility == "public":
        return True
    return _user_matches(user, owner_id)


# ── 引用分享(权限域二期 P2,§7.6)────────────────────────────────
# 判定单点收敛:ref 谓词只在本模块;各 router/查询一律引用此处,
# 禁止自写 EXISTS(§7.6「单点收敛」)。

def ref_exists_clauses(viewer_id: int):
    """PG 谓词用的两条 EXISTS(scenario_query.visibility_clause 引用;
    深度固定不递归:直接引用 ∨ 所在 suite 被引用)。"""
    from sqlalchemy import exists, select

    from ..models.share_ref import ShareRef
    from ..models.suite import SuiteMember

    direct = exists(select(ShareRef.id).where(
        ShareRef.scenario_id == ComposerScenario.scenario_id,
        ShareRef.grantee_user_id == viewer_id)).correlate(ComposerScenario)
    via_suite = exists(
        select(ShareRef.id)
        .join(SuiteMember, SuiteMember.suite_id == ShareRef.suite_id)
        .where(SuiteMember.scenario_id == ComposerScenario.scenario_id,
               ShareRef.grantee_user_id == viewer_id)
    ).correlate(ComposerScenario)
    return direct, via_suite


async def referenced_scenario_ids(db, user_id: int) -> set[str]:
    """SQLite 兜底/徽标用:user 的引用场景全集(直接 ∨ 经 suite),
    一次取集合(团队规模有界,§2.3)。"""
    from sqlalchemy import select

    from ..models.share_ref import ShareRef
    from ..models.suite import SuiteMember

    direct = (await db.execute(
        select(ShareRef.scenario_id).where(
            ShareRef.grantee_user_id == user_id,
            ShareRef.scenario_id.is_not(None)))).scalars().all()
    via = (await db.execute(
        select(SuiteMember.scenario_id)
        .join(ShareRef, ShareRef.suite_id == SuiteMember.suite_id)
        .where(ShareRef.grantee_user_id == user_id))).scalars().all()
    return set(direct) | set(via)


async def has_scenario_ref(db, user_id: int, scenario_id: str) -> bool:
    """can_run_scenario 的引用分支(§7.6):直接引用 ∨ 所在 suite 被引用。"""
    return scenario_id in await referenced_scenario_ids(db, user_id)


async def has_suite_ref(db, user_id: int, suite_id: int) -> bool:
    from sqlalchemy import select

    from ..models.share_ref import ShareRef

    return (await db.execute(
        select(ShareRef.id).where(
            ShareRef.grantee_user_id == user_id,
            ShareRef.suite_id == suite_id))).scalar_one_or_none() is not None


async def can_run_scenario(
    db, user: Any, *, scenario_id: str, owner_id: int | None,
) -> bool:
    """执行判定(§7.6):属主 ∨ admin ∨ 引用(public 不开执行,
    公共资源执行仍需先 fork —— 不变量 7)。owner_id=None(公共化
    无主)时仅 admin/历史引用可跑。"""
    if user.role == "admin" or _user_matches(user, owner_id or -1):
        return True
    return await has_scenario_ref(db, user.id, scenario_id)


async def can_read_scenario_row(db, user: Any, row: Any) -> bool:
    """读判定(对象级,含引用):行对象须有 scenario_id/owner_id/
    visibility。纯判(owner/admin/public)先行,引用分支只在前者
    不通过时查库。"""
    if can_read_scenario(
        user, owner_id=row.owner_id or -1,
        visibility=row.visibility or "private"):
        return True
    return await has_scenario_ref(db, user.id, row.scenario_id)


async def can_read_suite(db, user: Any, suite: Any) -> bool:
    """suite 读判定(§7.6):public ∨ 属主 ∨ admin ∨ suite 引用。"""
    if user.role == "admin" or _user_matches(user, suite.owner_id):
        return True
    if (suite.visibility or "private") == "public":
        return True
    return await has_suite_ref(db, user.id, suite.id)


async def can_run_suite(db, user: Any, suite: Any) -> bool:
    """suite 执行判定(§7.6):属主 ∨ admin ∨ suite 引用
    (运行时再逐成员 can_run_scenario)。"""
    if user.role == "admin" or _user_matches(user, suite.owner_id):
        return True
    return await has_suite_ref(db, user.id, suite.id)
