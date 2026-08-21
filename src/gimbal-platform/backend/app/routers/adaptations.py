"""适配中心路由(spec §5/§7 P3+P4 裁定):全路由 admin-only。

* ``POST /adaptations/catalog/diff`` —— 冷启动基线是写副作用,POST 如实承载;
* ``GET  /adaptations/impact`` —— 只读影响查询。

批次生命周期端点(batches / ops / apply / rollback)在 Task 10 追加到本文件。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser
from ..schemas.adaptations import CatalogDiffReport, ImpactItem
from ..services import adaptation_service
from ..services.plate_client import PlateUnavailableError

router = APIRouter(prefix="/adaptations", tags=["adaptations"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _plate_502(e: PlateUnavailableError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"code": "plate_unavailable", "message": e.message},
    )


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
