"""M2a S7.2 提升流程路由(加入项目 / 加入申请)。

* ``POST /projects/{pid}/promotions/analyze`` — 析出分析(成员发起;
  冲突清单 = 两区 carry 解析差;阻断项;槽位提示)。
* ``POST /projects/{pid}/promotions`` — 无冲突立即复制;有冲突生成
  pending 申请 + 通知项目管理员。
* ``GET /projects/{pid}/promotions`` — 项目管理员见全部,成员见自己。
* ``GET|POST /project-promotions/{id}`` — 详情 / 批准(逐项裁决,
  以批准那一刻的原件内容复制)/ 驳回(须理由)/ 撤回(申请人)。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Query as _Q  # noqa: F401 — 保持与兄弟路由一致的可读性
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.project_promotion import ProjectPromotion
from ..services import notifications as notify_svc
from ..services.project_promotion import (
    PromotionError,
    analyze_promotion,
    execute_promotion_copy,
    project_admin_ids,
    require_member,
    require_project_admin,
    source_changed_since,
)

router = APIRouter(tags=["projects"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class AnalyzeIn(BaseModel):
    kind: Literal["scenario", "suite"]
    sourceId: str = Field(min_length=1, max_length=128)


class CreateIn(AnalyzeIn):
    pass


class DecisionIn(BaseModel):
    service: str
    path: str
    # source = 采纳原件值(写入项目层);project = 保留项目层值
    use: Literal["source", "project"]
    sourceValue: str | None = None


class ApproveIn(BaseModel):
    decisions: list[DecisionIn] = Field(default_factory=list)


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


def _promo_out(promo: ProjectPromotion, *, changed: bool | None = None,
               copy: dict | None = None) -> dict:
    out = {
        "id": promo.id,
        "projectId": promo.project_id,
        "kind": promo.kind,
        "sourceId": promo.source_id,
        "applicantId": promo.applicant_id,
        "status": promo.status,
        "conflicts": promo.conflicts or [],
        "resolution": promo.resolution,
        "note": promo.note or "",
        "createdAt": promo.created_at.isoformat() + "Z"
        if promo.created_at else None,
        "updatedAt": promo.updated_at.isoformat() + "Z"
        if promo.updated_at else None,
    }
    if changed is not None:
        out["sourceChangedSinceApplication"] = changed
    if copy is not None:
        out["copy"] = copy
    return out


async def _load_promo(db: AsyncSession, promo_id: int) -> ProjectPromotion:
    promo = await db.get(ProjectPromotion, promo_id)
    if promo is None:
        raise HTTPException(404, detail={
            "code": "not_found", "message": f"promotion not found: {promo_id}"})
    return promo


@router.post("/projects/{project_id}/promotions/analyze")
async def analyze(
    user: CurrentUser, db: DbSession, project_id: int, body: AnalyzeIn,
) -> dict:
    try:
        return await analyze_promotion(
            db, kind=body.kind, source_id=body.sourceId,
            project_id=project_id, user=user)
    except PromotionError as e:
        raise e from None


@router.post("/projects/{project_id}/promotions", status_code=201)
async def create_promotion(
    user: CurrentUser, db: DbSession, project_id: int, body: CreateIn,
) -> dict:
    """发起加入:无冲突 → 立即复制(copied);有冲突 → pending 申请。"""
    try:
        analysis = await analyze_promotion(
            db, kind=body.kind, source_id=body.sourceId,
            project_id=project_id, user=user)
    except PromotionError as e:
        raise e from None
    if analysis["blockers"]:
        raise HTTPException(422, detail={
            "code": "members_blocked",
            "message": "存在阻断项(成员场景不在本项目且不能随行),先处理再发起",
            "blockers": analysis["blockers"]})
    if not analysis["conflicts"]:
        # 直通路径:无冲突不落申请行,直接复制(裁决记录 = 立即加入)
        direct = ProjectPromotion(
            project_id=project_id, kind=body.kind, source_id=body.sourceId,
            applicant_id=user.id, status="approved", conflicts=[],
            resolution={"decisions": [], "immediate": True,
                        "decidedBy": user.id,
                        "decidedAt": datetime.now(timezone.utc).isoformat()})
        copy = await execute_promotion_copy(db, direct, [], approver=user)
        await db.commit()
        return {"status": "copied", "copy": copy}
    promo = ProjectPromotion(
        project_id=project_id, kind=body.kind, source_id=body.sourceId,
        applicant_id=user.id, conflicts=analysis["conflicts"])
    db.add(promo)
    await db.flush()
    # 通知项目管理员(无项目管理员的极边缘态静默 —— 创建仍成功)
    for uid in await project_admin_ids(db, project_id):
        await notify_svc.create_notification(
            db, user_id=uid, type_="project_promotion.pending",
            title="加入申请待审批",
            body=f"{user.display_name or user.username} 申请把"
                 f"{'场景' if body.kind == 'scenario' else '用例集'}"
                 f" {body.sourceId} 加入项目(待裁决冲突 "
                 f"{len(analysis['conflicts'])} 项)",
            link=f"/projects/{project_id}?tab=promotions",
            payload={"promotionId": promo.id}, commit=False)
    await db.commit()
    return {"status": "pending", "promotionId": promo.id,
            "conflicts": analysis["conflicts"]}


@router.get("/projects/{project_id}/promotions")
async def list_promotions(
    user: CurrentUser, db: DbSession, project_id: int,
    status: Annotated[str | None, _Q(pattern="^(pending|approved|rejected|"
                                              "withdrawn)$")] = None,
) -> dict:
    """项目管理员(∨ Admin+)见全部;成员见自己的申请。"""
    await require_member(db, project_id, user.id)
    stmt = select(ProjectPromotion).where(
        ProjectPromotion.project_id == project_id)
    from ._ownership import has_capability

    sees_all = has_capability(user, "ops.write") or user.id in \
        await project_admin_ids(db, project_id)
    if not sees_all:
        stmt = stmt.where(ProjectPromotion.applicant_id == user.id)
    if status:
        stmt = stmt.where(ProjectPromotion.status == status)
    rows = (await db.execute(stmt.order_by(
        ProjectPromotion.id.desc()))).scalars().all()
    return {"items": [_promo_out(r) for r in rows]}


@router.get("/project-promotions/{promo_id}")
async def get_promotion(user: CurrentUser, db: DbSession, promo_id: int,
                        ) -> dict:
    promo = await _load_promo(db, promo_id)
    allowed = promo.applicant_id == user.id
    if not allowed:
        try:
            await require_project_admin(db, promo.project_id, user)
            allowed = True
        except PromotionError:
            pass
    if not allowed:
        raise HTTPException(404, detail={
            "code": "not_found", "message": f"promotion not found: {promo_id}"})
    return _promo_out(
        promo,
        changed=await source_changed_since(db, promo)
        if promo.status == "pending" else None)


@router.post("/project-promotions/{promo_id}/approve")
async def approve_promotion(
    user: CurrentUser, db: DbSession, promo_id: int, body: ApproveIn,
) -> dict:
    """批准:以**批准那一刻**的原件内容复制;use=source 的裁决先落
    项目层(合并写)。decisions 须覆盖全部冲突路径。"""
    promo = await _load_promo(db, promo_id)
    await require_project_admin(db, promo.project_id, user)
    if promo.status != "pending":
        raise HTTPException(409, detail={
            "code": "not_pending",
            "message": f"申请当前状态 {promo.status},只有 pending 可批准"})
    conflicts = promo.conflicts or []
    want = {(d.service, d.path): d for d in body.decisions}
    missing = [c for c in conflicts if (c["service"], c["path"]) not in want]
    extra = [k for k in want if k not in {
        (c["service"], c["path"]) for c in conflicts}]
    if missing or extra:
        raise HTTPException(422, detail={
            "code": "decisions_mismatch",
            "message": "裁决须逐项覆盖冲突清单,不多不少",
            "missing": [{"service": c["service"], "path": c["path"]}
                        for c in missing],
            "extra": [{"service": s, "path": p} for s, p in extra]})
    copy = await execute_promotion_copy(
        db, promo, [d.model_dump() for d in body.decisions], approver=user)
    promo.status = "approved"
    promo.resolution = {
        "decisions": [d.model_dump() for d in body.decisions],
        "decidedBy": user.id,
        "decidedAt": datetime.now(timezone.utc).isoformat(),
    }
    await notify_svc.create_notification(
        db, user_id=promo.applicant_id, type_="project_promotion.approved",
        title="加入申请已批准",
        body=f"{'场景' if promo.kind == 'scenario' else '用例集'} "
             f"{promo.source_id} 已复制进项目(副本已就位)",
        link=f"/projects/{promo.project_id}",
        payload={"promotionId": promo.id}, commit=False)
    await db.commit()
    return _promo_out(promo, copy=copy)


@router.post("/project-promotions/{promo_id}/reject")
async def reject_promotion(
    user: CurrentUser, db: DbSession, promo_id: int, body: RejectIn,
) -> dict:
    promo = await _load_promo(db, promo_id)
    await require_project_admin(db, promo.project_id, user)
    if promo.status != "pending":
        raise HTTPException(409, detail={
            "code": "not_pending",
            "message": f"申请当前状态 {promo.status},只有 pending 可驳回"})
    promo.status = "rejected"
    promo.note = body.reason
    promo.resolution = {
        "decisions": [], "decidedBy": user.id,
        "decidedAt": datetime.now(timezone.utc).isoformat(),
        "reason": body.reason}
    await notify_svc.create_notification(
        db, user_id=promo.applicant_id, type_="project_promotion.rejected",
        title="加入申请被驳回",
        body=f"{'场景' if promo.kind == 'scenario' else '用例集'} "
             f"{promo.source_id}:{body.reason}",
        link=f"/projects/{promo.project_id}",
        payload={"promotionId": promo.id}, commit=False)
    await db.commit()
    return _promo_out(promo)


@router.post("/project-promotions/{promo_id}/withdraw", status_code=200)
async def withdraw_promotion(
    user: CurrentUser, db: DbSession, promo_id: int,
) -> dict:
    promo = await _load_promo(db, promo_id)
    if promo.applicant_id != user.id:
        raise HTTPException(404, detail={
            "code": "not_found", "message": f"promotion not found: {promo_id}"})
    if promo.status != "pending":
        raise HTTPException(409, detail={
            "code": "not_pending",
            "message": f"申请当前状态 {promo.status},只有 pending 可撤回"})
    promo.status = "withdrawn"
    await db.commit()
    return _promo_out(promo)
