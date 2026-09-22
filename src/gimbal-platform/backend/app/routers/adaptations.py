"""适配中心路由(spec §5/§7 P3+P4 裁定):admin-only,唯 ``GET /batches?scope=mine``
member 可访问(C13 owner 知情视图)。

* ``POST /adaptations/catalog/diff`` —— 冷启动基线是写副作用,POST 如实承载;
* ``GET  /adaptations/impact`` —— 只读影响查询。

批次生命周期端点(batches / ops / apply / rollback)在 Task 10 追加到本文件。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser, CurrentUser
from ..schemas.adaptations import (
    BatchDetail,
    BatchListOut,
    BatchOut,
    CarryBatchIn,
    CatalogDiffReport,
    ImpactItem,
    ImpactSummaryReport,
    OpenBatchIn,
    OpCreateIn,
    OpOut,
    OpPatchIn,
    RefsDriftReport,
    RollbackReport,
    UnindexedStepOut,
)
from ..services import adaptation_service
from ..services.endpoint_ref_index import unindexed_steps as collect_unindexed
from ..services.plate_client import PlateUnavailableError
from ._error_mapping import _plate_502, key_error_404, value_error_http

router = APIRouter(prefix="/adaptations", tags=["adaptations"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("/catalog/diff", response_model=CatalogDiffReport)
async def catalog_diff(user: AdminUser, db: DbSession) -> CatalogDiffReport:
    """拉 plate 目录对戳:待适配 / 异常(C12 忘 bump、下架)/ 本次新落基线数。"""
    try:
        report = await adaptation_service.catalog_diff(db)
    except PlateUnavailableError as e:
        raise _plate_502(e) from e
    return CatalogDiffReport.model_validate(report)


@router.get("/impact", response_model=list[ImpactItem])
async def impact(
    user: AdminUser,
    db: DbSession,
    endpointId: str = Query(min_length=1),
    field: str | None = Query(default=None),
) -> list[ImpactItem]:
    """endpoint(可选 field)→ 受影响清单(直填/模板、数据集列标注)。"""
    items = await adaptation_service.impact(db, endpointId, field or None)
    return [ImpactItem.model_validate(i) for i in items]


@router.get("/impact-bulk")
async def impact_bulk(
    user: AdminUser,
    db: DbSession,
    endpointIds: list[str] = Query(default=[]),
) -> dict:
    """批量 impact(M5,债 12):一次请求回全部 pending 端点的受影响
    清单 —— 前端 useInterfaceChange 的「每端点一次 × 限并发 4」N+1
    消除。返回 {endpointId: [ImpactItem...]}(与单端点 /impact 同条目
    形状,未命中端点给空数组)。"""
    out: dict[str, list] = {}
    for eid in endpointIds[:50]:  # 防御上限:适配面单批不会超
        items = await adaptation_service.impact(db, eid, None)
        out[eid] = [ImpactItem.model_validate(i).model_dump(by_alias=True)
                    for i in items]
    return out


@router.get("/unindexed-steps", response_model=list[UnindexedStepOut])
async def unindexed_steps(user: AdminUser, db: DbSession) -> list[UnindexedStepOut]:
    """C10:缺 endpoint_id 的步骤清单(只读警示,不产生任何写)。"""
    return [
        UnindexedStepOut.model_validate({
            "scenarioId": i["scenario_id"],
            "stepIndex": i["step_index"],
            "reason": i["reason"],
        })
        for i in await collect_unindexed(db)
    ]


@router.get("/refs-drift", response_model=RefsDriftReport)
async def refs_drift(user: AdminUser, db: DbSession) -> RefsDriftReport:
    """倒排索引 vs plate 接口目录 diff(只读):悬空引用 / 全网零引用。"""
    return RefsDriftReport.model_validate(await adaptation_service.refs_drift(db))


@router.get("/impact-summary", response_model=ImpactSummaryReport)
async def impact_summary(
    user: AdminUser,
    db: DbSession,
    endpointIds: list[str] = Query(default=[]),
) -> ImpactSummaryReport:
    """本批影响面摘要(配套方案 §3.2):pending 端点集(客户端从
    catalog/diff 拿到后传入)→ 按服务聚合的 波及用例 / 最近失败 数。
    纯读 —— 不复算 diff(catalog_diff 带基线写副作用,不藏进 GET);
    recentFail 全站口径(跨 owner 聚合数,方案 §3.5)。"""
    return ImpactSummaryReport.model_validate(
        await adaptation_service.impact_summary(db, endpoint_ids=endpointIds))


@router.post("/batches", response_model=BatchDetail, status_code=201)
async def open_batch(
    user: AdminUser, body: OpenBatchIn, db: DbSession,
) -> BatchDetail:
    """开批次:校验基线/版本前进 → 存档受影响实体 → 展开自动草案。"""
    try:
        detail = await adaptation_service.open_batch(
            db, endpoint_id=body.endpoint_id, operator_id=user.id,
        )
    except PlateUnavailableError as e:
        raise _plate_502(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "no_baseline": 409, "no_pending_change": 409,
        }) from e
    return BatchDetail.model_validate(detail)


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
    """批次列表:operator/admin 全量;member 仅 ``scope=mine``(C13 owner
    知情视图;M2.5 起技术运营权归 operator,权限方案 §1.2)。M4(§6.3):
    status 精确 + Page 信封。"""
    if scope != "mine" and user.role == "member":
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
    user: AdminUser, batch_id: str, body: OpCreateIn, db: DbSession,
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
async def apply_op(user: AdminUser, op_id: int, db: DbSession) -> OpOut:
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
        resource_id=str(op_id), detail={"status": op.get("status")},
    )
    return OpOut.model_validate(op)


@router.post("/ops/{op_id}/skip", response_model=OpOut)
async def skip_op(user: AdminUser, op_id: int, db: DbSession) -> OpOut:
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
    user: AdminUser, op_id: int, body: OpPatchIn, db: DbSession,
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
    user: AdminUser, batch_id: str, db: DbSession,
) -> RollbackReport:
    """整批回滚:before+重放乐观比对,冲突实体跳过不盲写。"""
    try:
        report = await adaptation_service.rollback_batch(db, batch_id)
    except KeyError as e:
        raise key_error_404(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "batch_not_rollbackable": 409,
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
