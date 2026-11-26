"""账户组合资源 API(UPC M2;组合 v4 §5 适配统一容器,§9 契约)。

组合 = 服务 → 已登记身份条目的引用集,归属真实项目(``project_id``)。
方案经 ``accountComboId`` DTO ↔ ``composer_run_schemes.account_combo_id``
显式列绑定(§16.1;绑定写面在 ``/scenarios/{sid}/run-schemes``,本
router 只管理组合资源)。

Endpoints(前缀 ``/projects/{project_id}/account-combos``,同项目凭证
先例;§9 建议契约):

- GET                  列表 —— 项目可见者;含引用计数(显式列 SQL)
- POST                 新建 —— 项目内容写权(private 属主 / normal 可写
                       成员);公共项目 422(§7 能力关闭,API 同样拒绝)
- GET  /{combo_id}     详情 + 引用方案清单(编辑/删除前差异确认)
- PATCH /{combo_id}    改名/描述/条目(逐条保存面校验;仅条目变化
                       revision +1)
- POST /{combo_id}/set-default   换默认(旧默认自动摘除)
- DELETE /{combo_id}   删除 —— 被引用 409 ``account_combo_in_use`` +
                       引用方案清单(in-use 复核与删除同事务)

审计:account_combo.create/update/set_default/delete(治理面);
方案绑定/解绑随 run-schemes 写面记录。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, \
    status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.account_combo import AccountCombo
from ..models.composer_run_scheme import ComposerRunScheme
from ..models.project import Project, ProjectMember
from ..services import account_combo as combo_svc
from ..services import audit as audit_svc
from ..services import project_access
from ..services.zone import ProjectCreateDenied

router = APIRouter(prefix="/projects/{project_id}/account-combos",
                   tags=["account-combos"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# 引用键长度对齐既有列口径:service 键 = 目录服务名(String(128)),
# alias = service_identities.alias_name(String(128))。
_ServiceName = Annotated[str, Field(min_length=1, max_length=128)]
_AliasName = Annotated[str, Field(min_length=1, max_length=128)]
_Description = Annotated[str, Field(max_length=2048)]


def _not_found(project_id: int) -> HTTPException:
    """项目不可见/不存在统一 404(§21,不泄露存在性)。"""
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found",
                "message": f"project not found: {project_id}"})


def _combo_error(e: combo_svc.ComboError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": e.code, "message": e.message, **e.detail})


async def _load_project(
    db: AsyncSession, user: CurrentUser, project_id: int, *,
    write: bool,
) -> Project:
    """读门 = 项目可见;写门 = 内容写权(private 属主 / normal 可写
    成员;Admin+ 非成员不旁路);能力闸(§7:公共 422)统一在此。"""
    proj = await db.get(Project, project_id)
    if proj is None or not await project_access.can_view_project(
            db, user.id, proj):
        raise _not_found(project_id)
    if write:
        if proj.kind == Project.KIND_PRIVATE:
            if not await project_access.can_view_project(db, user.id, proj):
                raise _not_found(project_id)
            if project_access.relation_of_project(proj, user.id) != "owner":
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail={"code": "capability_forbidden",
                            "message": "仅私有空间所有者可维护组合"})
        else:
            role = (await db.execute(select(ProjectMember.role).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id))).scalar_one_or_none()
            if role is None:
                raise _not_found(project_id)
            if role not in ProjectMember.WRITER_ROLES:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail={"code": "project_role_readonly",
                            "message": "项目用户只能读和执行项目内容,"
                                       "不能维护组合"})
    combo_svc._check_capability(proj.kind)  # §7 关闭即 API 拒绝
    return proj


async def _load_combo(
    db: AsyncSession, user: CurrentUser, project_id: int, combo_id: int,
) -> tuple[Project, AccountCombo]:
    proj = await _load_project(db, user, project_id, write=False)
    combo = await db.get(AccountCombo, combo_id)
    if combo is None or combo.project_id != project_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "account_combo_not_found",
                    "message": f"账户组合不存在: {combo_id}"})
    return proj, combo


# ── body / view 形态 ─────────────────────────────────────────────

class ComboEntry(BaseModel):
    """组合条目:服务键 → 身份条目名(一条一服务)。

    字段形状不做 pydantic 级收窄 —— 空串/形状违例由服务层统一给出
    ``account_combo_entry_invalid``(422 detail 归一为域码,而非
    pydantic 校验清单)。"""
    service: str
    alias: str


class AccountComboCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: _Description = ""
    entries: list[ComboEntry] = Field(default_factory=list, max_length=64)
    isDefault: bool = False


class AccountComboUpdate(BaseModel):
    """整体替换式 PATCH。None = 不改;entries 显式给值(含 [])则整体
    替换 —— 替换后逐条过保存面校验,条目有实质变化 revision +1。"""
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: _Description | None = None
    entries: list[ComboEntry] | None = Field(default=None, max_length=64)


class AccountComboSchemeRef(BaseModel):
    comboId: int
    schemeId: str
    schemeName: str
    scenarioId: str
    scenarioName: str


class AccountComboView(BaseModel):
    id: int
    projectId: int
    name: str
    description: str = ""
    isDefault: bool
    revision: int
    entries: list[ComboEntry]
    referenceCount: int = 0
    schemes: list[AccountComboSchemeRef] = Field(default_factory=list)


def _view(db: AsyncSession, combo: AccountCombo, *,
          refs: list[dict] | None = None) -> AccountComboView:
    payload = combo.payload or {}
    entries = [ComboEntry.model_validate(e)
               for e in payload.get("entries") or []
               if isinstance(e, dict)]
    return AccountComboView(
        id=combo.id, projectId=combo.project_id, name=combo.name,
        description=combo.description, isDefault=bool(combo.is_default),
        revision=combo.revision, entries=entries,
        referenceCount=(len(refs) if refs is not None else 0),
        schemes=[AccountComboSchemeRef.model_validate(r)
                 for r in (refs or [])])


async def _audit(db, user: CurrentUser, action: str, combo: AccountCombo,
           extra: dict | None = None) -> None:
    """治理面审计(best-effort,既有审计流;组合 v4 §5.5)。"""
    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=getattr(user, "display_name", "") or "",
        action=action, resource_type="account_combo",
        resource_id=str(combo.id), resource_name=combo.name,
        detail={"project_id": combo.project_id, **(extra or {})})


# ── 端点 ────────────────────────────────────────────────────────

@router.get("", response_model=list[AccountComboView])
async def list_account_combos(
    user: CurrentUser, db: DbSession,
    project_id: Annotated[int, PathParam(ge=1)],
) -> list[AccountComboView]:
    await _load_project(db, user, project_id, write=False)
    combos = (await db.execute(
        select(AccountCombo).where(AccountCombo.project_id == project_id)
        .order_by(AccountCombo.is_default.desc(), AccountCombo.name)
    )).scalars().all()
    # 引用计数批量(显式列 SQL 聚合;引用统计不扫 payload)
    from sqlalchemy import func

    ids = [c.id for c in combos]
    counts = dict((await db.execute(
        select(ComposerRunScheme.account_combo_id, func.count())
        .where(ComposerRunScheme.account_combo_id.in_(ids or [0]))
        .group_by(ComposerRunScheme.account_combo_id)
    )).all())
    return [AccountComboView(
        id=c.id, projectId=c.project_id, name=c.name,
        description=c.description, isDefault=bool(c.is_default),
        revision=c.revision,
        entries=[ComboEntry.model_validate(e)
                 for e in (c.payload or {}).get("entries") or []
                 if isinstance(e, dict)],
        referenceCount=counts.get(c.id, 0),
    ) for c in combos]


@router.post("", status_code=status.HTTP_201_CREATED,
             response_model=AccountComboView)
async def create_account_combo(
    user: CurrentUser, db: DbSession,
    project_id: Annotated[int, PathParam(ge=1)],
    body: AccountComboCreate,
) -> AccountComboView:
    try:
        proj = await project_access.resolve_content_target(
            db, user.id, project_id)
    except ProjectCreateDenied as e:
        raise HTTPException(status_code=e.status, detail={
            "code": e.code, "message": e.message}) from None
    try:
        combo = await combo_svc.create_combo(
            db, project=proj, name=body.name, description=body.description,
            entries=[e.model_dump() for e in body.entries],
            is_default=body.isDefault, updated_by_id=user.id)
    except combo_svc.ComboError as e:
        raise _combo_error(e) from None
    await db.commit()
    await _audit(db, user, "account_combo.create", combo)
    return _view(db, combo, refs=[])


@router.get("/{combo_id}", response_model=AccountComboView)
async def get_account_combo(
    user: CurrentUser, db: DbSession,
    project_id: Annotated[int, PathParam(ge=1)],
    combo_id: Annotated[int, PathParam(ge=1)],
) -> AccountComboView:
    _, combo = await _load_combo(db, user, project_id, combo_id)
    refs = await combo_svc.referencing_schemes(db, combo.id)
    return _view(db, combo, refs=refs)


@router.patch("/{combo_id}", response_model=AccountComboView)
async def update_account_combo(
    user: CurrentUser, db: DbSession,
    project_id: Annotated[int, PathParam(ge=1)],
    combo_id: Annotated[int, PathParam(ge=1)],
    body: AccountComboUpdate,
) -> AccountComboView:
    await _load_project(db, user, project_id, write=True)
    combo = await db.get(AccountCombo, combo_id)
    if combo is None or combo.project_id != project_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "account_combo_not_found",
                    "message": f"账户组合不存在: {combo_id}"})
    try:
        await combo_svc.update_combo(
            db, combo, name=body.name, description=body.description,
            entries=None if body.entries is None
            else [e.model_dump() for e in body.entries],
            updated_by_id=user.id)
    except combo_svc.ComboError as e:
        raise _combo_error(e) from None
    await db.commit()
    await _audit(db, user, "account_combo.update", combo)
    refs = await combo_svc.referencing_schemes(db, combo.id)
    return _view(db, combo, refs=refs)


@router.post("/{combo_id}/set-default", response_model=AccountComboView)
async def set_default_account_combo(
    user: CurrentUser, db: DbSession,
    project_id: Annotated[int, PathParam(ge=1)],
    combo_id: Annotated[int, PathParam(ge=1)],
) -> AccountComboView:
    await _load_project(db, user, project_id, write=True)
    combo = await db.get(AccountCombo, combo_id)
    if combo is None or combo.project_id != project_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "account_combo_not_found",
                    "message": f"账户组合不存在: {combo_id}"})
    combo.updated_by_id = user.id
    await combo_svc.set_default(db, combo)
    await db.commit()
    await _audit(db, user, "account_combo.set_default", combo)
    return _view(db, combo, refs=[])


@router.delete("/{combo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_combo(
    user: CurrentUser, db: DbSession,
    project_id: Annotated[int, PathParam(ge=1)],
    combo_id: Annotated[int, PathParam(ge=1)],
) -> None:
    await _load_project(db, user, project_id, write=True)
    combo = await db.get(AccountCombo, combo_id)
    if combo is None or combo.project_id != project_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "account_combo_not_found",
                    "message": f"账户组合不存在: {combo_id}"})
    try:
        await combo_svc.delete_combo(db, combo)  # in-use 复核与删除同事务
    except combo_svc.ComboError as e:
        await db.rollback()
        raise _combo_error(e) from None
    await db.commit()
    await _audit(db, user, "account_combo.delete", combo,
           {"revision": combo.revision})
