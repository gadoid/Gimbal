"""§14.2 场景资产包端点(UPC M2 最小闭环,AC-45/46)。

* ``GET /api/scenarios/{scenario_id}/asset-bundle`` —— 导出(场景读闸);
* ``POST /api/projects/{project_id}/asset-bundles`` —— 原子恢复(目标
  项目内容写权;同键同摘要重放返回已有映射,同键不同摘要 409)。

恢复入口调用只 flush 的写入函数,整场景一个数据库事务提交(§14.2)。
导出不携带明文秘密(服务层剥离 ``config.users``)。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, \
    Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..services import scenario_asset_package as asset_pkg
from ..services import scenario_store
from ._error_mapping import not_found_404
from ._ownership import can_read_scenario_row

router = APIRouter(tags=["asset-bundles"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _err(e: asset_pkg.AssetBundleError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": e.code, "message": e.message, **e.detail})


@router.get("/scenarios/{scenario_id}/asset-bundle")
async def export_asset_bundle(
    user: CurrentUser, db: DbSession, scenario_id: str,
) -> dict:
    """导出场景资产包(§14.2:定义 + 数据集 + 方案 + 组合依赖;秘密剥离)。"""
    row = await scenario_store.get_row(db, scenario_id)
    if row is None or not await can_read_scenario_row(db, user, row):
        raise not_found_404("scenario", scenario_id)
    return await asset_pkg.export_bundle(db, row)


@router.post("/projects/{project_id}/asset-bundles")
async def restore_asset_bundle(
    user: CurrentUser, db: DbSession,
    project_id: Annotated[int, PathParam(ge=1)],
    bundle: dict,
) -> Response:
    """原子恢复资产包到目标项目(幂等键 = 包标识 × 源场景标识;
    重放返回 200 + 已提交映射,首次恢复 201 + 报告)。"""
    try:
        await asset_pkg.resolve_import_target(db, user, project_id)
        report = await asset_pkg.restore_bundle(
            db, project_id=project_id, bundle=bundle, user=user)
    except asset_pkg.AssetBundleError as e:
        await db.rollback()
        raise _err(e) from None
    replayed = bool(report.get("replayed"))
    await db.commit()
    return Response(
        status_code=status.HTTP_200_OK if replayed
        else status.HTTP_201_CREATED,
        media_type="application/json",
        content=asset_pkg._canonical(report))
