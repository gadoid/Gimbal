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
    # authz W9-2:公共态看 visibility(公共定义有维护者 ownerId ≠ None)
    isPublic: bool
    createdAt: str | None = None

    model_config = {"from_attributes": True}
    # alias 映射
    def __init__(self, **kw):
        kw.setdefault("isPublic",
                      kw.pop("visibility", "private") == "public")
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
        visibility=("public" if row.project_id is not None else "private"),
        isPublic=row.project_id is not None,
        createdAt=str(row.created_at) if row.created_at else None,
    )


@router.get("")
async def list_definitions(
    user: CurrentUser, db: DbSession,
) -> dict:
    # S1.2:列表三区(私有区属主 ∨ 我所在项目 ∨ 公共项目;无引用分支)
    from ..services.zone import zone_read_clause

    rows = (await db.execute(
        select(ReportDefinitionRow)
        .where(zone_read_clause(ReportDefinitionRow, user.id))
        .order_by(ReportDefinitionRow.id.desc())
    )).scalars().all()
    return {"items": [_to_out(r).model_dump() for r in rows]}


def _validate_m2(definition: dict, name: str) -> None:
    """M2 §6:保存时按平台生成物(app/schemas/_m2)校验报告定义。

    name 是 M2 必填但存在行的列上 —— 校验时补入,不回写定义。"""
    from pydantic import ValidationError
    from ..schemas._m2 import ReportDefinition
    try:
        ReportDefinition.model_validate({**definition, "name": name})
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"code": "report_definition_invalid",
                    "message": f"报告定义不符合 M2 ReportDefinition: {e}"}
        ) from e

def _validated_definition(body) -> dict:
    d = body.effective_definition()
    _validate_m2(d, body.name)
    return d

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_definition(
    user: CurrentUser, db: DbSession, body: ReportDefinitionCreate,
) -> dict:
    # authz W9-2:公共定义建维护者(owner 不置 None)—— 编辑权 =
    # 维护者;公共态由 visibility 独立表达
    row = ReportDefinitionRow(
        name=body.name, description=body.description,
        definition=_validated_definition(body),
        owner_id=user.id,
    )
    # S1.1 影子写:公共态 = visibility + project_id 同步(services.zone)
    from ..services.zone import apply_private, apply_public, public_project_id
    if body.public:
        apply_public(row, await public_project_id(db))
    else:
        apply_private(row)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_out(row).model_dump()


async def _get_owned(db: AsyncSession, user, did: int) -> ReportDefinitionRow:
    # 表 B report_definition.read:owner ∨ public_reader(S1.1 项目维度
    # 谓词,async can;修改 = 维护者 / 删除的 public_admin 面在写端点另判)。
    from ._ownership import can

    row = await db.get(ReportDefinitionRow, did)
    if row is None:
        raise HTTPException(404, detail={"code": "not_found",
                                         "message": f"definition not found: {did}"})
    if await can(db, user, "report_definition", "read", row):
        return row
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
    # 表 B report_definition.write(S1.1):私有区属主 ∨ 公共项目维护者
    # (admin 不再可编辑他人维护的公共定义,公共 ≠ 无主)。
    from ._ownership import can

    if not await can(db, user, "report_definition", "write", row):
        raise HTTPException(404, detail={"code": "not_found",
                                         "message": "not found"})
    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    if body.definition is not None:
        row.definition = body.definition
    # 公共/私有切换不动 owner(维护者恒定;编辑权随 owner);影子写
    # visibility ⇔ project_id 同步翻转(S1.1)
    if body.public is not None:
        from ..services.zone import apply_private, apply_public, \
            public_project_id
        if body.public:
            apply_public(row, await public_project_id(db))
        else:
            apply_private(row)
    await db.commit()
    await db.refresh(row)
    return _to_out(row).model_dump()


class TransferIn(BaseModel):
    toUserId: int


@router.post("/{definition_id}/transfer")
async def transfer_definition(
    user: CurrentUser, db: DbSession, definition_id: int,
    body: TransferIn,
) -> dict:
    """S1-e 转移维护者(表 B report_definition.transfer = maintainer ∨
    public_admin;仅公共项目定义,私有定义不适用)。"""
    from ._ownership import can

    from ..models.user import User
    from ..services import maintenance_transfer as mt
    from ..services.zone import public_project_id

    row = await db.get(ReportDefinitionRow, definition_id)
    if row is None or row.project_id != await public_project_id(db):
        raise HTTPException(404, detail={"code": "not_found",
                                         "message": f"definition not found: {definition_id}"})
    if not await can(db, user, "report_definition", "transfer", row):
        raise HTTPException(404, detail={"code": "not_found",
                                         "message": "not found"})
    to_user = await db.get(User, body.toUserId)
    if (to_user is None or not to_user.is_active or to_user.is_system
            or to_user.id == row.owner_id):
        raise HTTPException(422, detail={
            "code": "transferee_invalid",
            "message": "受让人须为在职、非系统用户(且非当前维护者)"})
    await mt.transfer_maintenance(
        db, obj=row, obj_type="report_definition", to_user=to_user,
        actor=user, obj_name=row.name)
    return {"transferredTo": to_user.id, "definitionId": definition_id}


@router.delete("/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_definition(
    user: CurrentUser, db: DbSession, definition_id: int,
) -> None:
    row = await db.get(ReportDefinitionRow, definition_id)
    if row is None:
        raise HTTPException(404, detail={"code": "not_found",
                                         "message": "not found"})
    # 表 B report_definition.delete(S1.1):owner ∨ maintainer ∨
    # public_admin(Admin+ 下架公共定义,与场景/suite 下架同口径)
    from ._ownership import can

    if not await can(db, user, "report_definition", "delete", row):
        raise HTTPException(404, detail={"code": "not_found",
                                         "message": "not found"})
    await db.delete(row)
    await db.commit()
