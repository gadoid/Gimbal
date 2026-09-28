"""Report Definitions API — P3-07/C7。

报告定义(选择+投影+呈现)按用户/团队存储;执行时选择定义
(RunRequest.reportDefinitionId → 引擎 definition reporter 产出工件,
平台从工件目录读取供下载)。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.report_definition import ReportDefinitionRow

router = APIRouter(prefix="/report-definitions", tags=["report-definitions"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class ReportDefinitionOut(BaseModel):
    id: int
    name: str
    description: str
    definition: dict
    ownerId: int | None
    isPublic: bool
    createdAt: str | None = None

    model_config = {"from_attributes": True}
    # alias 映射
    def __init__(self, **kw):
        kw.setdefault("isPublic", kw.pop("owner_id", None) is None)
        kw.setdefault("ownerId", kw.pop("owner_id", None))
        kw.setdefault("createdAt", str(kw.pop("created_at", "") or ""))
        super().__init__(**kw)


class ReportDefinitionCreate(BaseModel):
    """定义创建:接受完整 ReportDefinition 形态(选择/投影/呈现顶层
    展开)或 definition 键内嵌(平台内部形态)。"""
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    definition: dict | None = None    # 内嵌形态;缺省从顶层合成
    selection: dict | None = None
    projection: dict | None = None
    presentation: dict | None = None
    public: bool = False

    def effective_definition(self) -> dict:
        if self.definition is not None:
            return self.definition
        out: dict = {}
        if self.selection is not None:
            out["selection"] = self.selection
        if self.projection is not None:
            out["projection"] = self.projection
        if self.presentation is not None:
            out["presentation"] = self.presentation
        return out


class ReportDefinitionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    definition: dict | None = None
    public: bool | None = None


def _to_out(row: ReportDefinitionRow) -> ReportDefinitionOut:
    return ReportDefinitionOut(
        id=row.id, name=row.name, description=row.description,
        definition=row.definition, owner_id=row.owner_id,
        isPublic=row.owner_id is None,
        createdAt=str(row.created_at) if row.created_at else None,
    )


@router.get("")
async def list_definitions(
    user: CurrentUser, db: DbSession,
) -> dict:
    rows = (await db.execute(
        select(ReportDefinitionRow)
        .where((ReportDefinitionRow.owner_id == user.id)
               | (ReportDefinitionRow.owner_id.is_(None)))
        .order_by(ReportDefinitionRow.id.desc())
    )).scalars().all()
    return {"items": [_to_out(r).model_dump() for r in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_definition(
    user: CurrentUser, db: DbSession, body: ReportDefinitionCreate,
) -> dict:
    row = ReportDefinitionRow(
        name=body.name, description=body.description,
        definition=body.effective_definition(),
        owner_id=None if body.public else user.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_out(row).model_dump()


async def _get_owned(db: AsyncSession, user, did: int,
                     *, allow_public_read=True) -> ReportDefinitionRow:
    row = await db.get(ReportDefinitionRow, did)
    if row is None:
        raise HTTPException(404, detail={"code": "not_found",
                                         "message": f"definition not found: {did}"})
    if row.owner_id == user.id:
        return row
    if row.owner_id is None and allow_public_read and user.role == "admin":
        return row   # 公共区 admin 可改
    if row.owner_id is None and allow_public_read:
        return row   # 公共区全员可读(修改/删除限 admin/owner)
    raise HTTPException(404, detail={"code": "not_found",
                                     "message": f"definition not found: {did}"})


@router.get("/{definition_id}")
async def get_definition(
    user: CurrentUser, db: DbSession, definition_id: int,
) -> dict:
    row = await _get_owned(db, user, definition_id)
    return _to_out(row).model_dump()


@router.put("/{definition_id}")
async def update_definition(
    user: CurrentUser, db: DbSession, definition_id: int,
    body: ReportDefinitionUpdate,
) -> dict:
    row = await db.get(ReportDefinitionRow, definition_id)
    if row is None:
        raise HTTPException(404, detail={"code": "not_found",
                                         "message": "not found"})
    # 私有 = 仅 owner;公共 = admin 也可改
    is_owner = row.owner_id == user.id
    is_public_admin = row.owner_id is None and user.role == "admin"
    if not (is_owner or is_public_admin):
        raise HTTPException(404, detail={"code": "not_found",
                                         "message": "not found"})
    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    if body.definition is not None:
        row.definition = body.definition
    if body.public is not None:
        row.owner_id = None if body.public else user.id
    await db.commit()
    await db.refresh(row)
    return _to_out(row).model_dump()


@router.delete("/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_definition(
    user: CurrentUser, db: DbSession, definition_id: int,
) -> None:
    row = await db.get(ReportDefinitionRow, definition_id)
    if row is None:
        raise HTTPException(404, detail={"code": "not_found",
                                         "message": "not found"})
    is_owner = row.owner_id == user.id
    is_public_admin = row.owner_id is None and user.role == "admin"
    if not (is_owner or is_public_admin):
        raise HTTPException(404, detail={"code": "not_found",
                                         "message": "not found"})
    await db.delete(row)
    await db.commit()
