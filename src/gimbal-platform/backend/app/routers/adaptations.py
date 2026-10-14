"""适配中心路由(spec §5/§7 P3+P4 裁定):admin-only,唯 ``GET /batches?scope=mine``
member 可访问(C13 owner 知情视图)。

A-6 清理(2026-10-12):catalog/diff、impact、impact-bulk、
impact-summary、refs-drift 五个 working 全局目录口径的读面已删除
(影响提示由版本提示/生效修订口径承接);引用索引健康检查仅存
C10 unindexed-steps。

批次生命周期端点(batches / ops / apply / rollback)在 Task 10 追加到本文件。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser, CurrentUser
from ..schemas.adaptations import (
    BatchDetail,
    BatchListOut,
    BatchOut,
    CarryBatchIn,
    OpCreateIn,
    OpOut,
    OpPatchIn,
    RollbackReport,
    UnindexedStepOut,
)
from ..services import adaptation_service
from ..services.endpoint_ref_index import unindexed_steps as collect_unindexed
from ..services.plate_client import PlateUnavailableError
from ._error_mapping import _plate_502, key_error_404, value_error_http

router = APIRouter(prefix="/adaptations", tags=["adaptations"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/unindexed-steps", response_model=list[UnindexedStepOut])
async def unindexed_steps(user: CurrentUser, db: DbSession) -> list[UnindexedStepOut]:
    """C10:缺 endpoint_id 的步骤清单(只读警示,不产生任何写)。"""
    return [
        UnindexedStepOut.model_validate({
            "scenarioId": i["scenario_id"],
            "stepIndex": i["step_index"],
            "reason": i["reason"],
        })
        for i in await collect_unindexed(db)
    ]


@router.post("/carry-batches", response_model=BatchDetail, status_code=201)
async def open_carry_batch(
    user: AdminUser, body: CarryBatchIn, db: DbSession,
) -> BatchDetail:
    """开 carry 值表批(漂移面板入口,spec §7);ops 经既有
    POST /batches/{id}/ops,apply/rollback 走既有逐条/整批端点。"""
    detail = await adaptation_service.open_carry_batch(
        db, service=body.service, operator_id=user.id,
    )
    return BatchDetail.model_validate(detail)


@router.get("/batches", response_model=BatchListOut)
async def list_batches(
    user: CurrentUser, db: DbSession,
    scope: str | None = Query(default=None),
    status: str | None = Query(default=None, max_length=16),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> BatchListOut:
    """批次列表:member/admin 全量;user 仅 ``scope=mine``(C13 owner
    知情视图;M2.5 起技术运营权归 member 级,权限方案 §1.2)。M4(§6.3):
    status 精确 + Page 信封。"""
    if scope != "mine" and user.role == "user":
        from fastapi import status as http_status

        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="operator_only: members must use ?scope=mine",
        )
    rows, total = (
        await adaptation_service.list_batches_for_owner(
            db, user.id, status=status, page=page, page_size=page_size,
            viewer=user)
        if scope == "mine"
        else await adaptation_service.list_batches(
            db, status=status, page=page, page_size=page_size,
            viewer=user)
    )
    return BatchListOut(
        items=[BatchOut.model_validate(b) for b in rows],
        total=total, page=page, page_size=page_size,
    )


@router.get("/batches/{batch_id}", response_model=BatchDetail)
async def get_batch(batch_id: str, user: AdminUser, db: DbSession) -> BatchDetail:
    try:
        detail = await adaptation_service.get_batch_detail(
            db, batch_id, viewer=user)
    except KeyError as e:
        raise key_error_404(e) from e
    return BatchDetail.model_validate(detail)


@router.post("/batches/{batch_id}/ops", response_model=OpOut, status_code=201)
async def create_op(
    user: CurrentUser, batch_id: str, body: OpCreateIn, db: DbSession,
) -> OpOut:
    """人工补 op(renameVar / 数据集 op —— 自动草案之外,§5.4)。"""
    try:
        op = await adaptation_service.create_op(
            db, batch_id,
            op_type=body.op_type, scenario_id=body.scenario_id,
            dataset_id=body.dataset_id, payload=body.payload,
        )
    except KeyError as e:
        raise key_error_404(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "batch_not_active": 409, "bad_op_type": 400,
            "op_needs_dataset": 400,
        }) from e
    return OpOut.model_validate(op)


@router.post("/ops/{op_id}/apply", response_model=OpOut)
async def apply_op(user: CurrentUser, op_id: int, db: DbSession) -> OpOut:
    """逐条应用:幂等重放 / C5 冲突标 conflict / 末条完成推戳。"""
    try:
        op = await adaptation_service.apply_op(db, op_id)
    except KeyError as e:
        raise key_error_404(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "op_not_applicable": 409, "batch_not_active": 409,
        }) from e
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="adaptation.op.apply", resource_type="adaptation_op",
        resource_id=str(op_id),
        resource_name=op.get("scenario_display_name") or None,
        detail={"status": op.get("status"), "op_type": op.get("op_type")},
    )
    return OpOut.model_validate(op)


@router.post("/ops/{op_id}/skip", response_model=OpOut)
async def skip_op(user: CurrentUser, op_id: int, db: DbSession) -> OpOut:
    """跳过一条 pending op(末条跳过同样收敛 completed + 推戳)。"""
    try:
        op = await adaptation_service.skip_op(db, op_id)
    except KeyError as e:
        raise key_error_404(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "op_not_applicable": 409, "batch_not_active": 409,
        }) from e
    return OpOut.model_validate(op)


@router.patch("/ops/{op_id}", response_model=OpOut)
async def patch_op(
    user: CurrentUser, op_id: int, body: OpPatchIn, db: DbSession,
) -> OpOut:
    """仅 pending 可整包替换 payload(mapValue 骨架补值 / 参数修正)。"""
    try:
        op = await adaptation_service.update_op(db, op_id, body.payload)
    except KeyError as e:
        raise key_error_404(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={"op_not_applicable": 409}) from e
    return OpOut.model_validate(op)


@router.post("/batches/{batch_id}/rollback", response_model=RollbackReport)
async def rollback_batch(
    user: CurrentUser, batch_id: str, db: DbSession,
    force: bool = Query(default=False),
) -> RollbackReport:
    """整批回滚:before+重放乐观比对,冲突实体跳过不盲写。

    force(M4/R27):RS4a 批次提交后场景被编辑过时,编辑者确认放弃
    这些修改后带 force 还原快照。
    """
    try:
        report = await adaptation_service.rollback_batch(
            db, batch_id, force=force)
    except KeyError as e:
        raise key_error_404(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "batch_not_rollbackable": 409,
            "not_latest": 409,
        }) from e
    from ..services import audit as audit_svc

    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="adaptation.batch.rollback", resource_type="adaptation_batch",
        resource_id=batch_id,
        detail={"skipped": len(getattr(report, "skipped", []) or [])},
    )
    return RollbackReport.model_validate(report)


# ─── RS4a 新流程（Release v4.4 §5）：比较 → 保存检查 → 提交 ────────

@router.get("/compare")
async def compare_revisions(
    user: CurrentUser, db: DbSession,
    scenarioId: str = Query(..., min_length=3),
    target: str = Query(..., min_length=1),
    system: str | None = Query(default=None),
) -> dict:
    """RS4a 比较（§5.3）:场景起点修订 vs 目标修订的 plate 差异 + 三组影响。

    R22:读面全员(差异本身不涉编辑权)。
    """
    try:
        item = await adaptation_service.compare_scenario(
            db, scenario_id=scenarioId, target_revision=target,
            system=system)
    except PlateUnavailableError as e:
        raise _plate_502(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "scenario_not_found": 404,
            "multi_system_scenario": 422,
            "no_system_declared": 422,
            "release_not_found": 404,
        }) from e
    return {"item": item}


class SaveCheckIn(BaseModel):
    """RS4a 保存检查入参（§5.6）。"""

    scenarioId: str
    targetRevision: str
    system: str | None = None


@router.post("/save-check")
async def save_check(user: CurrentUser, db: DbSession,
                     body: SaveCheckIn) -> dict:
    """RS4a 保存检查:①目标修订试算（阻断）②引用检查 ③保存方式推荐。

    R14:review_items 非空时提示确认,未确认提交被拒。
    """
    try:
        return await adaptation_service.save_check(
            db, scenario_id=body.scenarioId,
            target_revision=body.targetRevision, system=body.system)
    except PlateUnavailableError as e:
        raise _plate_502(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "scenario_not_found": 404,
            "multi_system_scenario": 422,
            "no_system_declared": 422,
        }) from e


class SubmitIn(BaseModel):
    """RS4a 提交入参（§5.7）。"""

    scenarioId: str
    ops: list[dict] = Field(default_factory=list)
    targetRevision: str
    saveMode: str = Field(pattern="^(direct|copy)$")
    system: str | None = None
    reviewConfirmed: bool = False
    # W22/RS4b:可展开的结构级 op(replaceEndpoint/removeStep/splitStep)
    # 按锚点端点应用到同场景内同类步骤(§5.4)
    applyToSimilar: bool = False


@router.post("/submit")
async def submit_adaptation(user: CurrentUser, db: DbSession,
                            body: SubmitIn) -> dict:
    """RS4a 提交:按场景单事务(快照 → 应用 op → meta.plate → 审计/通知)。

    R22:编辑权随场景(_ensure_edit_rights,admin 或 owner)。
    """
    try:
        return await adaptation_service.submit_adaptation(
            db, scenario_id=body.scenarioId, ops=body.ops,
            target_revision=body.targetRevision, save_mode=body.saveMode,
            review_confirmed=body.reviewConfirmed, system=body.system,
            user=user, apply_to_similar=body.applyToSimilar)
    except PlateUnavailableError as e:
        raise _plate_502(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "scenario_not_found": 404,
            "save_check_failed": 409,
            "review_items_unconfirmed": 409,
            "multi_system_scenario": 422,
            "no_system_declared": 422,
        }) from e
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 — _ensure_edit_rights 的 403
        if "not_scenario_owner" in str(e):
            raise HTTPException(status_code=403, detail=str(e)) from e
        raise


@router.get("/stale")
async def stale_scenarios(
    user: CurrentUser, db: DbSession,
    scope: str | None = Query(default=None),
) -> dict:
    """RS4a 陈旧清单（§2.3）:预览/新线/已修正/已退役。scope=mine 只看自己。"""
    user_id = user.id if (scope == "mine" or user.role != "admin") else None
    try:
        items = await adaptation_service.stale_scenarios(db, user_id=user_id)
    except PlateUnavailableError as e:
        raise _plate_502(e) from e
    return {"items": items, "total": len(items)}

class BatchSubmitIn(BaseModel):
    """批量提交入参（§5.3 直接切换/字段级的多场景聚合）。"""

    scenarioIds: list[str] = Field(min_length=1)
    targetRevision: str
    system: str | None = None
    reviewConfirmed: bool = False


@router.post("/submit-batch")
async def submit_batch(user: CurrentUser, db: DbSession,
                       body: BatchSubmitIn) -> dict:
    """批量提交:逐场景走 submit_adaptation(单事务语义保持),聚合结果。

    §5.5「一次编辑作用于所有受影响场景」的最小落地:ops 起草按场景
    compare 差异各自生成(直接切换场景零 op);单场景失败不回滚已成的
    (结果按场景报告,失败项重试)。
    """
    results: list[dict] = []
    for sid in body.scenarioIds:
        try:
            compare = await adaptation_service.compare_scenario(
                db, scenario_id=sid, target_revision=body.targetRevision,
                system=body.system)
            out = await adaptation_service.submit_adaptation(
                db, scenario_id=sid, ops=compare.get("drafted_ops") or [],
                target_revision=body.targetRevision, save_mode="direct",
                review_confirmed=body.reviewConfirmed,
                system=body.system, user=user)
            results.append({"scenario_id": sid, **out})
        except PlateUnavailableError as e:
            raise _plate_502(e) from e
        except ValueError as e:
            results.append({"scenario_id": sid, "success": False,
                            "message": str(e)})
        except HTTPException as e:
            results.append({"scenario_id": sid, "success": False,
                            "message": str(e.detail)})
    ok = sum(1 for r in results if r.get("success"))
    return {"total": len(results), "succeeded": ok,
            "failed": len(results) - ok, "items": results}


class SuiteSubmitIn(BaseModel):
    """Suite 整体适配入参（§5.8）。"""

    suiteId: int
    targetRevision: str
    saveMode: str = Field(pattern="^(direct|copy)$")
    system: str | None = None


@router.post("/submit-suite")
async def submit_suite(user: CurrentUser, db: DbSession,
                       body: SuiteSubmitIn) -> dict:
    """Suite 整体适配（§5.8/R25）:逐成员 compare→submit 聚合。

    R25 闸:direct 模式时同系统成员须一起提交(此处全量提交,天然满足);
    copy 模式时连 Suite 一起复制(deep_copy_suite + 各成员副本)。
    """
    from ..models.suite import Suite
    from ..services import suite_copy

    suite = await db.get(Suite, body.suiteId)
    if suite is None:
        raise HTTPException(404, f"suite_not_found: {body.suiteId}")
    units = (suite.mode_config or {}).get("units") or {}
    scenario_ids = sorted(units.keys()) if isinstance(units, dict) else []
    if not scenario_ids:
        return {"total": 0, "succeeded": 0, "failed": 0, "items": [],
                "suite_id": body.suiteId}

    # R25 前置:版本线一致性检查(direct 模式)
    if body.saveMode == "direct":
        from ..services.suite_version import check_and_resolve_suite_versions
        from ..services import scenario_store as ss
        member_payloads = []
        for sid in scenario_ids:
            row = await ss.get_row(db, sid)
            member_payloads.append(row.payload or {} if row else {})
        try:
            await check_and_resolve_suite_versions(member_payloads)
        except Exception as e:
            raise HTTPException(409, detail={
                "code": "SUITE_VERSION_MISMATCH",
                "message": str(e)}) from e

    # copy 模式:先 fork Suite,再逐成员适配到副本
    new_suite_id = None
    if body.saveMode == "copy":
        forked = await suite_copy.deep_copy_suite(
            db, suite, owner_id=user.id,
            owner_name=user.display_name or user.username)
        new_suite_id = forked.id if forked else None
        # 适配目标:新 Suite 的成员(副本场景)
        if new_suite_id:
            fork = await db.get(Suite, new_suite_id)
            funits = (fork.mode_config or {}).get("units") or {}
            scenario_ids = sorted(funits.keys()) if isinstance(funits, dict) else []

    results: list[dict] = []
    for sid in scenario_ids:
        try:
            compare = await adaptation_service.compare_scenario(
                db, scenario_id=sid, target_revision=body.targetRevision,
                system=body.system)
            out = await adaptation_service.submit_adaptation(
                db, scenario_id=sid, ops=compare.get("drafted_ops") or [],
                target_revision=body.targetRevision,
                save_mode="direct",   # Suite 内成员统一 direct(整体已选 copy)
                system=body.system, user=user)
            results.append({"scenario_id": sid, **out})
        except PlateUnavailableError as e:
            raise _plate_502(e) from e
        except (ValueError, HTTPException) as e:
            msg = str(e) if isinstance(e, ValueError) else str(e.detail)
            results.append({"scenario_id": sid, "success": False,
                            "message": msg})

    ok = sum(1 for r in results if r.get("success"))
    return {"total": len(results), "succeeded": ok,
            "failed": len(results) - ok, "items": results,
            "suite_id": body.suiteId,
            **({"new_suite_id": new_suite_id} if new_suite_id else {})}
