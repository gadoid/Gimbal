"""P2 迁移入口(仅 admin)。

* ``POST /api/admin/migrate-v1``   body ``{"dryRun": true|false}``

干跑只出报告;真跑执行 owner_id 回填 + V1 文件用例导入 +
favorites→stars。幂等,可反复调用(已迁移的 scenario_id 跳过)。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser
from ..services import migrate_v1

router = APIRouter(prefix="/admin", tags=["admin"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class MigrateV1In(BaseModel):
    # camelCase 别名:请求体是 {"dryRun": false};漏配会静默吃成默认 True
    model_config = ConfigDict(populate_by_name=True)

    dry_run: bool = Field(default=True, alias="dryRun")


@router.post("/migrate-v1")
async def run_migrate_v1(
    _admin: AdminUser, db: DbSession, body: MigrateV1In
) -> dict[str, Any]:
    backfilled = 0
    if not body.dry_run:
        backfilled = await migrate_v1.backfill_owner_ids(db)
    report = await migrate_v1.migrate_v1_cases(db, dry_run=body.dry_run)
    report["ownerIdsBackfilled"] = backfilled
    return report
