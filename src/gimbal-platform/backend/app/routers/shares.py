"""分享(引用/副本)— 权限域二期 P2,《Suite成员层、引用分享与浏览镜头
-设计方案》§7/§9。

对象级权限(§9):
- 发起分享 = **属主**(admin 不可代他人分享,§8.1);
- 撤销 = 属主 ∨ admin(admin 入审计);退订 = 被分享人本人(不通知);
- 转为副本 = 被分享人;副本完全归被分享人,原引用保留。

模式语义(§7.1):ref = upsert share_refs(live link,只读可执行);
copy = 场景走 copy_scenario(与 handoff 同一深拷贝)、suite 走单事务
深拷贝(成员逐个复制 + forked_from 三件套,mode_config P1 恒 {} 免重映射)。
"""
from __future__ import annotations

from datetime import datetime, timezone

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.composer_scenario import ComposerScenario
from ..models.share_ref import ShareRef
from ..models.suite import Suite, SuiteMember
from ..models.user import User
from ..schemas.share import (
    ReferrerViaSuite, ScenarioReferrerOut, ScenarioReferrersOut,
    ShareCopyOut, ShareCreateIn, ShareRefOut,
)
from ..services import audit as audit_svc
from ..services.suite_copy import (
    deep_copy_suite, suite_owner_display)
from ..services import notifications as notify_svc
from ..services import scenario_store
from ._ownership import ensure_owner

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/shares", tags=["shares"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _load_grantee(db, grantee_id: int, sharer_id: int) -> User:
    """接收人校验(§7.7):活跃、非本人。"""
    target = (await db.execute(
        select(User).where(User.id == grantee_id))).scalar_one_or_none()
    if target is None or not target.is_active:
        raise HTTPException(422, "target_user_invalid")
    if target.id == sharer_id:
        raise HTTPException(422, "target_self")
    return target


async def _record_share_event(db, *, actor_id, kind, resource_type,
                              resource_id, detail) -> None:
    """activity_events:全部分享事件(§10;副本历史只存在这里)。"""
    from ..services import activity as activity_svc
    await activity_svc.record(
        db, actor_id=actor_id, kind=kind,
        resource_type=resource_type, resource_id=resource_id,
        detail=detail, coalesce=False)


@router.post("", response_model=None, status_code=201)
async def create_share(
    user: CurrentUser, db: DbSession, body: ShareCreateIn,
) -> ShareRefOut | ShareCopyOut:
    sharer_disp = user.display_name or user.username

    if body.resourceType == "scenario":
        row = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == body.resourceId))
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "scenario_not_found")
        # §8.1:发起分享 = 属主;admin 无豁免(防 admin 借分享转内容)
        if user.id != row.owner_id:
            raise HTTPException(403, "not_owner")
        target = await _load_grantee(db, body.granteeUserId, user.id)
        if body.mode == "copy":
            resolved, _ = await scenario_store.resolve_name_conflict(
                db, target.id, row.name or row.scenario_id)
            out = await scenario_store.copy_scenario(
                db, row.scenario_id,
                new_owner=target.display_name or target.username,
                new_owner_id=target.id, new_name=resolved,
                activity_kind="scenario.share_copy",
                activity_detail={"senderId": user.id,
                                 "senderName": sharer_disp},
                origin_id=row.scenario_id,
                origin_owner_name=row.owner_name or "")
            await _notify(db, target.id, "resource_handoff",
                         f"收到副本:{out.meta.name}",
                         f"{sharer_disp} 拷贝分享了场景「{row.name or row.scenario_id}」给你",
                         link=f"/scenarios/{out.meta.scenario_id}/detail",
                         resource_id=out.meta.scenario_id)
            await _record_share_event(
                db, actor_id=user.id, kind="scenario.share_copy",
                resource_type="scenario", resource_id=row.scenario_id,
                detail={"granteeId": target.id, "copyId": out.meta.scenario_id})
            return ShareCopyOut(mode="copy", scenarioId=out.meta.scenario_id)
        # ref:幂等 upsert + cap(§7.7)
        await _ensure_ref_cap(db, user.id)
        existing = (await db.execute(select(ShareRef).where(
            ShareRef.grantee_user_id == target.id,
            ShareRef.scenario_id == row.scenario_id))).scalar_one_or_none()
        if existing is None:
            db.add(ShareRef(grantee_user_id=target.id,
                            scenario_id=row.scenario_id,
                            granted_by_name=sharer_disp))
            await db.commit()
            await _notify(db, target.id, "share_ref_received",
                         f"收到引用:{row.name or row.scenario_id}",
                         f"{sharer_disp} 把场景「{row.name or row.scenario_id}」以引用分享给你(只读可执行,实时跟随对方修改)",
                         link=f"/scenarios/{row.scenario_id}/detail",
                         resource_id=row.scenario_id)
            await _record_share_event(
                db, actor_id=user.id, kind="scenario.share_ref",
                resource_type="scenario", resource_id=row.scenario_id,
                detail={"granteeId": target.id})
        ref = (await db.execute(select(ShareRef).where(
            ShareRef.grantee_user_id == target.id,
            ShareRef.scenario_id == row.scenario_id))).scalar_one()
        return _ref_out(ref, grantee=target, scenario_name=row.name)

    # suite
    suite = (await db.execute(select(Suite).where(
        Suite.id == int(body.resourceId)))).scalar_one_or_none()
    if suite is None:
        raise HTTPException(404, "suite_not_found")
    if user.id != suite.owner_id:
        raise HTTPException(403, "not_owner")
    if (suite.mode_config or {}).get("draft"):
        # 重构方案:草稿不可分享(ref/copy 同拒)
        raise HTTPException(409, {
            "code": "suite_is_draft",
            "message": "草稿不可分享(完成编排后可分享)"})
    target = await _load_grantee(db, body.granteeUserId, user.id)
    if body.mode == "copy":
        out = await deep_copy_suite(db, suite, target, sharer_disp)
        await _notify(db, target.id, "resource_handoff",
                     f"收到副本:{out['name']}",
                     f"{sharer_disp} 拷贝分享了 Suite「{suite.name}」给你({out['count']} 个成员)",
                     link=f"/suites/{out['suiteId']}",
                     resource_id=str(out["suiteId"]))
        await _record_share_event(
            db, actor_id=user.id, kind="suite.share_copy",
            resource_type="suite", resource_id=str(suite.id),
            detail={"granteeId": target.id, "copyId": out["suiteId"]})
        return ShareCopyOut(mode="copy", suiteId=out["suiteId"],
                            suiteName=out["name"], memberCount=out["count"])
    await _ensure_ref_cap(db, user.id)
    existing = (await db.execute(select(ShareRef).where(
        ShareRef.grantee_user_id == target.id,
        ShareRef.suite_id == suite.id))).scalar_one_or_none()
    if existing is None:
        db.add(ShareRef(grantee_user_id=target.id, suite_id=suite.id,
                        granted_by_name=sharer_disp))
        await db.commit()
        await _notify(db, target.id, "share_ref_received",
                     f"收到引用:Suite {suite.name}",
                     f"{sharer_disp} 把 Suite「{suite.name}」以引用分享给你(可读可整组执行)",
                     link=f"/suites/{suite.id}",
                     resource_id=str(suite.id))
        await _record_share_event(
            db, actor_id=user.id, kind="suite.share_ref",
            resource_type="suite", resource_id=str(suite.id),
            detail={"granteeId": target.id})
    ref = (await db.execute(select(ShareRef).where(
        ShareRef.grantee_user_id == target.id,
        ShareRef.suite_id == suite.id))).scalar_one()
    mc = int((await db.execute(select(func.count()).select_from(
        SuiteMember).where(SuiteMember.suite_id == suite.id))).scalar() or 0)
    return _ref_out(ref, grantee=target, suite_name=suite.name,
                    member_count=mc)


@router.get("", response_model=list[ShareRefOut])
async def list_shares(
    user: CurrentUser, db: DbSession,
    direction: str = "out",
    resourceType: str | None = None,
    resourceId: str | None = None,
) -> list[ShareRefOut]:
    """引用清单(只返回 ref;副本历史见 activity_events,§9)。
    direction=out = 我分享出去的(属主治理面);in = 共享给我的。"""
    stmt = select(ShareRef)
    if direction == "out":
        # 属主治理面 = 我名下资源的引用;P2 资源属主可从行推导,
        # 逐资源查询成本可接受(团队规模有界)
        own_scen = select(ComposerScenario.scenario_id).where(
            ComposerScenario.owner_id == user.id)
        own_suite = select(Suite.id).where(Suite.owner_id == user.id)
        stmt = select(ShareRef).where(or_(
            ShareRef.scenario_id.in_(own_scen),
            ShareRef.suite_id.in_(own_suite)))
        if user.role == "admin":
            stmt = select(ShareRef)  # admin 治理:全量
    else:
        stmt = select(ShareRef).where(ShareRef.grantee_user_id == user.id)
    if resourceType == "scenario":
        stmt = stmt.where(ShareRef.scenario_id.is_not(None))
        if resourceId:
            stmt = stmt.where(ShareRef.scenario_id == resourceId)
    elif resourceType == "suite":
        stmt = stmt.where(ShareRef.suite_id.is_not(None))
        if resourceId:
            stmt = stmt.where(ShareRef.suite_id == int(resourceId))
    rows = (await db.execute(stmt.order_by(
        ShareRef.granted_at.desc()))).scalars().all()
    # 展示名反查(评审补记):场景引用补 scenarioName、suite 引用补
    # memberCount —— 前端「共享给我的」行两类都已在消费;批查防 N+1。
    scen_names: dict[str, str] = {}
    scen_ids = [r.scenario_id for r in rows if r.scenario_id is not None]
    if scen_ids:
        scen_names = dict((await db.execute(
            select(ComposerScenario.scenario_id, ComposerScenario.name)
            .where(ComposerScenario.scenario_id.in_(scen_ids)))).all())
    member_counts: dict[int, int] = {}
    suite_ids = [r.suite_id for r in rows if r.suite_id is not None]
    if suite_ids:
        member_counts = {
            sid: int(n) for sid, n in (await db.execute(
                select(SuiteMember.suite_id, func.count())
                .where(SuiteMember.suite_id.in_(suite_ids))
                .group_by(SuiteMember.suite_id))).all()}
    out = []
    for r in rows:
        suite_name = None
        if r.suite_id is not None:
            s = (await db.execute(select(Suite.name).where(
                Suite.id == r.suite_id))).scalar_one_or_none()
            suite_name = s
        grantee = (await db.execute(select(User).where(
            User.id == r.grantee_user_id))).scalar_one_or_none()
        out.append(_ref_out(
            r, grantee=grantee, suite_name=suite_name,
            scenario_name=(scen_names.get(r.scenario_id)
                           if r.scenario_id is not None else None),
            member_count=(member_counts.get(r.suite_id, 0)
                          if r.suite_id is not None else None)))
    return out


@router.get("/referrers", response_model=ScenarioReferrersOut)
async def scenario_referrers(
    user: CurrentUser, db: DbSession, scenarioId: str,
) -> ScenarioReferrersOut:
    """场景的全部引用人(§7.11 防误伤名单,属主治理面):直接引用 +
    经由所属 Suite 的间接引用(§7.6 判定式,同一引用人合并成一行)。

    保存提示与「已引用分享」徽标的数据源 —— 此前两者只查直接引用,
    场景仅因所在 Suite 被分享而间接被引用时名单落空(重构方案补遗)。"""
    scen = (await db.execute(select(ComposerScenario).where(
        ComposerScenario.scenario_id == scenarioId))
    ).scalar_one_or_none()
    if scen is None:
        raise HTTPException(404, "scenario_not_found")
    if user.id != scen.owner_id and user.role != "admin":
        raise HTTPException(403, "not_owner")

    direct_refs = (await db.execute(select(ShareRef).where(
        ShareRef.scenario_id == scenarioId))).scalars().all()
    # 间接引用:场景所在 Suite(组合外键 ⇒ 与属主同源)上的引用行
    suite_ids = select(SuiteMember.suite_id).where(
        SuiteMember.scenario_id == scenarioId)
    indirect_refs = (await db.execute(select(ShareRef).where(
        ShareRef.suite_id.in_(suite_ids)))).scalars().all()
    suite_names: dict[int, str] = {}
    ids = {r.suite_id for r in indirect_refs if r.suite_id is not None}
    if ids:
        suite_names = dict((await db.execute(
            select(Suite.id, Suite.name).where(Suite.id.in_(ids)))).all())
    uids = {r.grantee_user_id for r in [*direct_refs, *indirect_refs]}
    names: dict[int, str] = {}
    if uids:
        names = {u.id: (u.display_name or u.username)
                 for u in (await db.execute(
                     select(User).where(User.id.in_(uids)))).scalars()}

    merged: dict[int, ScenarioReferrerOut] = {}

    def _entry(grantee_id: int) -> ScenarioReferrerOut:
        if grantee_id not in merged:
            merged[grantee_id] = ScenarioReferrerOut(
                granteeUserId=grantee_id,
                granteeName=names.get(grantee_id, ""),
                direct=False)
        return merged[grantee_id]

    for r in direct_refs:
        _entry(r.grantee_user_id).direct = True
    for r in indirect_refs:
        _entry(r.grantee_user_id).viaSuites.append(ReferrerViaSuite(
            suiteId=r.suite_id, suiteName=suite_names.get(r.suite_id, "")))
    items = sorted(merged.values(), key=lambda m: m.granteeUserId)
    return ScenarioReferrersOut(items=items)


@router.delete("/{share_id}", status_code=204)
async def delete_share(
    user: CurrentUser, db: DbSession, share_id: int,
) -> None:
    """撤销(属主/admin;admin 入审计)或退订(被分享人,不通知)。"""
    ref = (await db.execute(select(ShareRef).where(
        ShareRef.id == share_id))).scalar_one_or_none()
    if ref is None:
        raise HTTPException(404, "share_not_found")
    is_grantee = ref.grantee_user_id == user.id
    if is_grantee and user.role != "admin":
        await db.delete(ref)          # 退订(§7.7):删行,不通知
        await db.commit()
        return
    # 撤销:资源属主 ∨ admin
    owned = False
    if ref.scenario_id is not None:
        row = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == ref.scenario_id))
        ).scalar_one_or_none()
        owned = row is not None and row.owner_id == user.id
    else:
        s = (await db.execute(select(Suite).where(
            Suite.id == ref.suite_id))).scalar_one_or_none()
        owned = s is not None and s.owner_id == user.id
    if not owned and user.role != "admin":
        raise HTTPException(403, "not_owner")
    await db.delete(ref)
    await db.commit()
    # 通知被分享人(§10);admin 撤销入审计
    name = ref.scenario_id or f"suite#{ref.suite_id}"
    await _notify(db, ref.grantee_user_id, "share_ref_revoked",
                 f"引用已撤销:{name}",
                 f"分享者撤销了「{name}」的引用分享,下一次访问即失效",
                 resource_id=ref.scenario_id or (
                     str(ref.suite_id) if ref.suite_id else None))
    if user.role == "admin" and not owned:
        await audit_svc.record(
            db, actor_id=user.id, actor_name=user.username,
            action="share.admin_revoke",
            resource_type=ref.scenario_id and "scenario" or "suite",
            resource_id=ref.scenario_id or str(ref.suite_id),
            detail={"granteeUserId": ref.grantee_user_id})


@router.post("/{share_id}/fork", response_model=ShareCopyOut, status_code=201)
async def fork_share(
    user: CurrentUser, db: DbSession, share_id: int,
) -> ShareCopyOut:
    """转为副本(§7.7):被分享人把引用转成自己的副本,原引用保留。"""
    ref = (await db.execute(select(ShareRef).where(
        ShareRef.id == share_id))).scalar_one_or_none()
    if ref is None:
        raise HTTPException(404, "share_not_found")
    if ref.grantee_user_id != user.id:
        raise HTTPException(403, "not_grantee")
    if ref.scenario_id is not None:
        row = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == ref.scenario_id))
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "scenario_not_found")
        resolved, _ = await scenario_store.resolve_name_conflict(
            db, user.id, row.name or row.scenario_id)
        out = await scenario_store.copy_scenario(
            db, row.scenario_id,
            new_owner=user.display_name or user.username,
            new_owner_id=user.id, new_name=resolved,
            activity_kind="scenario.share_fork",
            activity_detail={"fromRef": ref.id},
            origin_id=row.scenario_id,
            origin_owner_name=row.owner_name or "")
        await _record_share_event(
            db, actor_id=user.id, kind="scenario.share_fork",
            resource_type="scenario", resource_id=row.scenario_id,
            detail={"copyId": out.meta.scenario_id})
        return ShareCopyOut(mode="copy", scenarioId=out.meta.scenario_id)
    suite = (await db.execute(select(Suite).where(
        Suite.id == ref.suite_id))).scalar_one_or_none()
    if suite is None:
        raise HTTPException(404, "suite_not_found")
    # 来源属主名 = 原 Suite 属主,不是转副本人自己(评审补记修复)
    out = await deep_copy_suite(
        db, suite, user, await suite_owner_display(db, suite))
    await _record_share_event(
        db, actor_id=user.id, kind="suite.share_fork",
        resource_type="suite", resource_id=str(suite.id),
        detail={"copyId": out["suiteId"]})
    return ShareCopyOut(mode="copy", suiteId=out["suiteId"],
                        suiteName=out["name"], memberCount=out["count"])


# ── 内部 ──────────────────────────────────────────────────────────

async def _ensure_ref_cap(db, sharer_id: int) -> None:
    """SHARE_REF_CAP(§6.3):每人**发出**的引用数上限(防蔓延对冲)。"""
    # 发出数 = 自己名下资源上的引用;P2 简化口径 = 该用户作为属主的
    # 场景/suite 上的引用行数(团队规模有界,精确到属主推导成本可接受)
    own_scen = select(ComposerScenario.scenario_id).where(
        ComposerScenario.owner_id == sharer_id)
    own_suite = select(Suite.id).where(Suite.owner_id == sharer_id)
    n = (await db.execute(
        select(func.count()).select_from(ShareRef).where(or_(
            ShareRef.scenario_id.in_(own_scen),
            ShareRef.suite_id.in_(own_suite)))
    )).scalar() or 0
    if n >= settings.SHARE_REF_CAP:
        raise HTTPException(409, {
            "code": "share_ref_cap_exceeded",
            "message": f"share ref cap per user is {settings.SHARE_REF_CAP}"})



async def _notify(db, user_id: int, type_: str, title: str, body: str,
                  link: str | None = None, resource_id: str | None = None,
                  resource_type: str = "scenario") -> None:
    """通知 best-effort(§10;失败 rollback+记日志,不阻断业务)。"""
    from loguru import logger
    try:
        await notify_svc.create_notification(
            db, user_id=user_id, type_=type_, title=title, body=body,
            link=link, resource_type=resource_type, resource_id=resource_id,
            commit=True)
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.warning("shares: notify {} failed: {}", type_, e)


def _ref_out(ref: ShareRef, *, grantee, suite_name: str | None = None,
             scenario_name: str | None = None,
             member_count: int | None = None) -> ShareRefOut:
    return ShareRefOut(
        id=ref.id,
        resourceType="scenario" if ref.scenario_id else "suite",
        scenarioId=ref.scenario_id,
        suiteId=ref.suite_id,
        suiteName=suite_name,
        scenarioName=scenario_name,
        memberCount=member_count,
        granteeUserId=ref.grantee_user_id,
        granteeName=(getattr(grantee, "display_name", None)
                     or getattr(grantee, "username", "") or ""),
        grantedByName=ref.granted_by_name,
        grantedAt=ref.granted_at.isoformat() if ref.granted_at else None,
    )
