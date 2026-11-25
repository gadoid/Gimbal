"""账户组合 API(账户组合设计方案 §5,定稿 05)。

组合 = 服务 → 已登记身份条目的引用集(``payload.entries``,一条一
服务):跨场景复用的**基础默认**身份映射层。场景经
``POST /api/scenarios/{sid}/account-combo`` 绑定(引用语义,改动传播);
``definition.config.accountCombo`` 为**服务端托管键** —— 整稿 PUT 恒剥
保留存量,唯一写通道 = 绑定端点(scenario_store 侧单点,§4.2)。

两个 scope 同构(``exec_configs`` 的 (scope, scope_id) 维度先例,无 FK):
* ``user`` —— 个人面:全员可建、属主单判;
* ``project`` —— 项目面:读 = 成员任一角色,写 = WRITER_ROLES
  (**按成员关系判,平台 Admin 不旁路** —— §5.3 范围矩阵,同 zone
  D1 语义);公共项目不建组合(422,不把环境与凭证引用发布成公共
  模板)。

范围矩阵(v1 硬同区,§5.3):个人组合仅绑本人私有场景;项目组合仅绑
同一普通项目场景(跨项目双成员也拒);公共场景不绑(发布恒剥)。
跨 scope 绑定 → 422 ``account_combo_scope_mismatch``。

条目校验分层(§3.2/§6.3):**全量校验只在保存面** —— 创建/PATCH 逐条
过 ``validate_binding_aliases``(别名存在 ∧ 同基础服务,复用既有码族
``binding_alias_unknown`` / ``binding_alias_mismatch``),形状/重复服务
→ 422 ``account_combo_entry_invalid``;执行/预检只按引用服务校验
(批 2 接入)。``revision`` 仅条目变化 +1(元数据只动 updated_at+审计)。

``scenario_combo_router`` 挂 ``/scenarios/{id}/account-combo`` 两端点,
必须先于 scenarios 的 ``/{scenario_id}`` catch-all 注册(main.py 注记)。
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Integer, cast, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models import AccountCombo
from ..models.composer_scenario import ComposerScenario
from ..models.project import Project, ProjectMember
from ..models.user import User
from ..services import audit as audit_svc
from ..services.scenario_store import ACCOUNT_COMBO_REF_KEY
from ..services.zone import (
    ProjectCreateDenied, ensure_can_create_in_project, my_project_roles,
    public_project_id,
)

router = APIRouter(prefix="/account-combos", tags=["account-combos"])
# 场景侧绑定/读取通道:static 后缀 account-combo,须先于 scenarios
# catch-all 注册(同 data_sets.create_router 先例)。
scenario_combo_router = APIRouter(prefix="/scenarios", tags=["account-combos"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# 引用键长度对齐既有列口径:service 键 = 目录服务名(String(128)),
# alias = service_identities.alias_name(String(128),§8.10 aliases 同域)。
_ServiceName = Annotated[str, Field(min_length=1, max_length=128)]
_AliasName = Annotated[str, Field(min_length=1, max_length=128)]
_Description = Annotated[str, Field(max_length=2048)]


# ── 错误形态 ────────────────────────────────────────────────────

def _combo_not_found(combo_id: int) -> HTTPException:
    """资源端点(/{id} 家族):404(不泄露他人组合存在性)。"""
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={"code": "account_combo_not_found",
                "message": f"账户组合不存在: {combo_id}"})


def _combo_not_found_422(combo_id: int) -> HTTPException:
    """场景侧绑定闸:422(§5.2 同码双态 —— 引用了不存在或不可读的
    组合,face 决定 status)。"""
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"code": "account_combo_not_found",
                "message": f"组合不存在或不可读: {combo_id}"})


def _scope_mismatch(message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"code": "account_combo_scope_mismatch",
                "message": message})


def _entry_invalid(message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"code": "account_combo_entry_invalid",
                "message": message})


def _name_conflict(name: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={"code": "account_combo_name_exists",
                "message": f"账户组合名 '{name}' 已存在"})


# ── body / view 形态 ─────────────────────────────────────────────

class ComboEntry(BaseModel):
    """组合条目:服务键 → 身份条目名(一条一服务,§2.1)。"""
    service: _ServiceName
    alias: _AliasName


class AccountComboCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: _Description = ""
    entries: list[ComboEntry] = Field(default_factory=list, max_length=64)
    isDefault: bool = False
    scope: Literal["user", "project"] = "user"
    projectId: int | None = Field(default=None, ge=1)


class AccountComboUpdate(BaseModel):
    """整体替换式 PATCH。None = 不改;entries 显式给值(含 [])则
    整体替换 —— 替换后逐条过保存面校验,条目有实质变化 revision +1。"""
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: _Description | None = None
    entries: list[ComboEntry] | None = Field(default=None, max_length=64)


class AccountComboView(BaseModel):
    id: int
    scope: str
    scopeId: int
    name: str
    description: str = ""
    isDefault: bool
    revision: int
    entries: list[ComboEntry]
    referenceCount: int = 0
    updatedAt: datetime | None = None
    updatedByName: str | None = None


class AccountComboProjectGroup(BaseModel):
    projectId: int
    projectName: str
    items: list[AccountComboView]


class AccountComboListOut(BaseModel):
    personal: list[AccountComboView]
    projects: list[AccountComboProjectGroup]


class ComboBindIn(BaseModel):
    comboId: int | None = Field(default=None, ge=1)


# ── 保存面条目校验(§3.2 校验职责分层:全量校验只在保存面)────

def _check_entry_shape(entries: list[ComboEntry]) -> None:
    seen: set[str] = set()
    for e in entries:
        if e.service in seen:
            raise _entry_invalid(
                f"服务 {e.service!r} 在组合内重复 —— 一条一服务")
        seen.add(e.service)


async def _validate_entries(
    db: AsyncSession, entries: list[ComboEntry]
) -> None:
    """条目逐条过 validate_binding_aliases(复用既有码族,§4.1);
    形状/重复在 pydantic + _check_entry_shape 拦。"""
    _check_entry_shape(entries)
    from ..services.service_aliases import (
        BindingAliasInvalid, validate_binding_aliases)
    try:
        await validate_binding_aliases(
            db, {e.service: {"alias": e.alias} for e in entries})
    except BindingAliasInvalid as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": e.code, "message": e.message,
                    "service": e.service, "alias": e.alias}) from None


def _payload_entries(entries: list[ComboEntry]) -> dict:
    return {"entries": [e.model_dump() for e in entries]}


# ── 引用计数 / in-use 清单(definition.config.accountCombo 引用)──

def _combo_ref_column():
    """``payload->definition->config->accountCombo`` 的 int 投影
    (JSONB 路径;storage 单点 = scenario_store 托管键写入)。"""
    return cast(
        ComposerScenario.payload["definition"]["config"]["accountCombo"]
        .as_string(), Integer)


async def _reference_counts(db: AsyncSession, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    ref = _combo_ref_column()
    rows = (await db.execute(
        select(ref, func.count()).where(ref.in_(ids)).group_by(ref)
    )).all()
    return {int(k): int(v) for k, v in rows}


async def _referencing_scenarios(
    db: AsyncSession, combo_id: int, *, limit: int = 20
) -> list[dict]:
    ref = _combo_ref_column()
    rows = (await db.execute(
        select(ComposerScenario.scenario_id, ComposerScenario.name)
        .where(ref == combo_id)
        .order_by(ComposerScenario.id).limit(limit)
    )).all()
    return [{"scenarioId": sid, "name": name or sid} for sid, name in rows]


# ── 访问门(§5.3 范围矩阵:按成员关系判,Admin 不旁路)──────────

async def _access(
    db: AsyncSession, combo_id: int, user, *, write: bool
) -> AccountCombo:
    """读:user 行 = 本人 ∨ project 行 = 成员任一角色;写:user 行 =
    本人 ∨ project 行 = WRITER_ROLES。完全不可见 → 404(不泄露存在性,
    同 D1:项目对象权限只看项目角色,平台 Admin 不旁路)。"""
    row = await db.get(AccountCombo, combo_id)
    if row is None:
        raise _combo_not_found(combo_id)
    if row.scope == "user":
        if row.scope_id != user.id:
            raise _combo_not_found(combo_id)
        return row
    role = (await my_project_roles(db, user.id)).get(row.scope_id)
    if role is None:
        raise _combo_not_found(combo_id)
    if write and role not in ProjectMember.WRITER_ROLES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "project_role_readonly",
                    "message": "项目用户只能读和执行项目内容,不能修改账户"
                               "组合"})
    return row


async def _combo_readable_for_bind(db: AsyncSession, combo: AccountCombo,
                                   user) -> bool:
    """绑定闸的可读判定(§5.2 场景侧 422 双态的「不可读」半边):
    个人组合仅属主可读;项目组合成员任一角色可读。"""
    if combo.scope == "user":
        return combo.scope_id == user.id
    return combo.scope_id in await my_project_roles(db, user.id)


async def _audit(db, user, action: str, combo: AccountCombo,
                detail: dict) -> None:
    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action=action, resource_type="account_combo",
        resource_id=str(combo.id), resource_name=combo.name, detail=detail)


# ── 组合资源端点 ─────────────────────────────────────────────────

async def _view_rows(
    db: AsyncSession, rows: list[AccountCombo]
) -> list[AccountComboView]:
    """行 → 视图(引用计数 + updatedByName 一次聚合,不在循环内打库)。"""
    counts = await _reference_counts(db, [r.id for r in rows])
    uids = {r.updated_by_id for r in rows if r.updated_by_id}
    users = (await db.execute(
        select(User.id, User.display_name, User.username)
        .where(User.id.in_(uids)))).all() if uids else []
    names = {uid: (dn or un) for uid, dn, un in users}
    return [
        AccountComboView(
            id=r.id, scope=r.scope, scopeId=r.scope_id, name=r.name,
            description=r.description or "", isDefault=r.is_default,
            revision=r.revision,
            entries=[ComboEntry(**e) for e in (r.payload or {}).get(
                "entries", [])],
            referenceCount=counts.get(r.id, 0),
            updatedAt=r.updated_at,
            updatedByName=names.get(r.updated_by_id))
        for r in rows
    ]


@router.get("", response_model=AccountComboListOut)
async def list_account_combos(
    user: CurrentUser, db: DbSession,
    projectId: Annotated[int | None, Query(ge=1)] = None,
) -> Any:
    """按 scope 分组返回可见组合(个人 = 本人;项目 = 我所在的普通
    项目,成员任一角色)。``?projectId=`` 只看该项目(非成员 → 404 不
    泄露)。含引用计数,供编辑/删除前差异确认(§5.1)。"""
    my_roles = await my_project_roles(db, user.id)
    if projectId is not None and projectId not in my_roles:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"project not found: {projectId}")
    scope_ids = [projectId] if projectId is not None else list(my_roles)
    proj_names = dict((await db.execute(
        select(Project.id, Project.name).where(Project.id.in_(scope_ids))
    )).all()) if scope_ids else {}
    out = AccountComboListOut(personal=[], projects=[])
    if projectId is None:
        rows = (await db.execute(
            select(AccountCombo).where(
                AccountCombo.scope == "user",
                AccountCombo.scope_id == user.id)
            .order_by(AccountCombo.is_default.desc(),
                      AccountCombo.name.asc())
        )).scalars().all()
        out.personal = await _view_rows(db, list(rows))
    for pid in sorted(scope_ids):
        rows = (await db.execute(
            select(AccountCombo).where(
                AccountCombo.scope == "project",
                AccountCombo.scope_id == pid)
            .order_by(AccountCombo.is_default.desc(),
                      AccountCombo.name.asc())
        )).scalars().all()
        out.projects.append(AccountComboProjectGroup(
            projectId=pid, projectName=proj_names.get(pid, str(pid)),
            items=await _view_rows(db, list(rows))))
    return out


@router.post("", response_model=AccountComboView,
             status_code=status.HTTP_201_CREATED)
async def create_account_combo(
    body: AccountComboCreate, user: CurrentUser, db: DbSession
) -> AccountComboView:
    if body.scope == "project":
        # 项目内新建门单源(404 不泄露 / 公共项目 422 / 非成员 404 /
        # 只读角色 403 —— §5.3 Admin 不旁路同款语义)
        try:
            await ensure_can_create_in_project(db, user.id, body.projectId)
        except ProjectCreateDenied as e:
            raise HTTPException(
                e.status, detail={"code": e.code, "message": e.message})
        scope, scope_id = "project", body.projectId
    else:
        scope, scope_id = "user", user.id
    await _validate_entries(db, body.entries)
    if body.isDefault:
        await _clear_default(db, scope, scope_id)
    row = AccountCombo(
        scope=scope, scope_id=scope_id, name=body.name,
        description=body.description, is_default=body.isDefault,
        payload=_payload_entries(body.entries),
        updated_by_id=user.id)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _name_conflict(body.name) from e
    await db.refresh(row)
    await _audit(db, user, "account_combo.write", row, {
        "op": "create", "scope": scope, "scopeId": scope_id,
        "entries": len(body.entries)})
    return (await _view_rows(db, [row]))[0]


@router.get("/{combo_id}", response_model=AccountComboView)
async def get_account_combo(
    combo_id: int, user: CurrentUser, db: DbSession
) -> AccountComboView:
    row = await _access(db, combo_id, user, write=False)
    return (await _view_rows(db, [row]))[0]


@router.patch("/{combo_id}", response_model=AccountComboView)
async def patch_account_combo(
    combo_id: int, body: AccountComboUpdate,
    user: CurrentUser, db: DbSession,
) -> AccountComboView:
    """改名/描述/条目。条目显式给定才校验+替换;**仅条目有实质变化
    ``revision`` +1**(元数据只动 updated_at + 审计,§4.1)。"""
    row = await _access(db, combo_id, user, write=True)
    entries_changed = False
    if body.entries is not None:
        await _validate_entries(db, body.entries)
        old = (row.payload or {}).get("entries") or []
        new = [e.model_dump() for e in body.entries]
        if new != old:
            row.payload = {**(row.payload or {}), "entries": new}
            row.revision = (row.revision or 1) + 1
            entries_changed = True
    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    row.updated_by_id = user.id
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _name_conflict(body.name or row.name) from e
    await db.refresh(row)
    await _audit(db, user, "account_combo.write", row, {
        "op": "update", "entriesChanged": entries_changed,
        **({"revisionBumpedTo": row.revision} if entries_changed else {})})
    return (await _view_rows(db, [row]))[0]


async def _clear_default(db: AsyncSession, scope: str, scope_id: int) -> None:
    await db.execute(update(AccountCombo).where(
        AccountCombo.scope == scope, AccountCombo.scope_id == scope_id,
        AccountCombo.is_default.is_(True),
    ).values(is_default=False))


@router.post("/{combo_id}/set-default", response_model=AccountComboView)
async def set_default_account_combo(
    combo_id: int, user: CurrentUser, db: DbSession
) -> AccountComboView:
    """置为默认(语义 = 「推荐默认」:新建场景预选,不静默自动写入,
    §4.1)。原子切换:同事务先清旧默认再置新;partial unique 兜并发。"""
    row = await _access(db, combo_id, user, write=True)
    await _clear_default(db, row.scope, row.scope_id)
    row.is_default = True
    row.updated_by_id = user.id
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "default account combo changed concurrently; retry") from e
    await db.refresh(row)
    await _audit(db, user, "account_combo.write", row, {"op": "set_default"})
    return (await _view_rows(db, [row]))[0]


@router.delete("/{combo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_combo(
    combo_id: int, user: CurrentUser, db: DbSession
) -> None:
    """被引用时 409 拒删(in-use 复核与删除同事务,§5.1)—— 不静默
    悬空;不解绑不给删。"""
    row = await _access(db, combo_id, user, write=True)
    refs = await _referencing_scenarios(db, row.id)
    if refs:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "account_combo_in_use",
                    "message": "组合仍被场景引用,请先在场景内解除绑定",
                    "scenarios": refs})
    name_snapshot = row.name
    await db.delete(row)
    await db.commit()
    await _audit(db, user, "account_combo.write", row, {
        "op": "delete", "name": name_snapshot})


# ── 场景侧绑定/读取通道(服务端托管键的唯一写入口,§4.2)──────

def _bound_combo_id(row: ComposerScenario) -> int | None:
    cfg = ((row.payload or {}).get("definition") or {}).get("config")
    if not isinstance(cfg, dict):
        return None
    v = cfg.get(ACCOUNT_COMBO_REF_KEY)
    return v if isinstance(v, int) else None


async def _bind_view(db: AsyncSession, combo: AccountCombo) -> dict:
    return {"comboId": combo.id, "name": combo.name, "scope": combo.scope,
            "revision": combo.revision,
            "entries": (combo.payload or {}).get("entries", [])}


@scenario_combo_router.get("/{scenario_id}/account-combo")
async def get_scenario_combo(
    scenario_id: str, user: CurrentUser, db: DbSession
) -> dict:
    """读取通道(表 B scenario.read):返回当前绑定(comboId + 名称/
    revision/条目摘要)—— 编排器重载恢复显示(§5.1)。组合行已被并发
    删除(删除有 in-use 闸,仅竞态可达)→ comboMissing 标注。"""
    from .scenarios import _load_row, _require_reader_async

    row = await _load_row(db, scenario_id)
    await _require_reader_async(db, user, row)
    combo_id = _bound_combo_id(row)
    if combo_id is None:
        return {"comboId": None}
    combo = await db.get(AccountCombo, combo_id)
    if combo is None:
        return {"comboId": combo_id, "comboMissing": True}
    return await _bind_view(db, combo)


@scenario_combo_router.post("/{scenario_id}/account-combo")
async def bind_scenario_combo(
    scenario_id: str, body: ComboBindIn,
    user: CurrentUser, db: DbSession,
) -> dict:
    """v1 唯一应用入口 = 编排器(§8.1):``{comboId: int | null}``,
    null = 解绑;一步改引用,不动方案绑定与步骤(§5.1)。门 = 场景
    写闸 ∧ 组合可读 ∧ **同区**(§5.3 范围矩阵)。"""
    from .scenarios import _load_row, _require_owner

    row = await _load_row(db, scenario_id)
    await _require_owner(db, user, row)
    payload = dict(row.payload or {})
    definition = dict(payload.get("definition") or {})
    cfg = dict(definition.get("config") or {})
    if body.comboId is None:
        # 解绑:仅摘引用;覆盖服务自然回落方案绑定/步骤直引(§8.1
        # 解除提示的「哪些服务仍有覆盖」由前端按生效预览展示)
        had = cfg.pop(ACCOUNT_COMBO_REF_KEY, None)
        if had is None:
            return {"comboId": None}
        definition["config"] = cfg
        payload["definition"] = definition
        row.payload = payload  # JSON 列需整体赋值触发变更
        await db.commit()
        await audit_svc.record(
            db, actor_id=user.id,
            actor_name=user.display_name or user.username,
            action="account_combo.bind", resource_type="scenario",
            resource_id=scenario_id,
            detail={"op": "unbind", "comboId": had})
        return {"comboId": None}
    combo = await db.get(AccountCombo, body.comboId)
    if (combo is None
            or not await _combo_readable_for_bind(db, combo, user)):
        raise _combo_not_found_422(body.comboId)
    # v1 硬同区(§5.3):个人组合仅本人私有场景;项目组合仅同项目
    # 场景;公共项目场景不绑(发布恒剥,此处防御)。
    if combo.scope == "user":
        if row.project_id is not None:
            raise _scope_mismatch(
                "个人组合只能绑定本人私有场景(v1 硬同区)")
        if row.owner_id != combo.scope_id:
            raise _scope_mismatch(
                "个人组合只能绑定本人私有场景(v1 硬同区)")
    else:
        if row.project_id != combo.scope_id:
            raise _scope_mismatch(
                "项目组合只能绑定同一项目的场景(v1 硬同区)")
    pub = await public_project_id(db)
    if row.project_id is not None and row.project_id == pub:
        raise _scope_mismatch("公共场景不绑定账户组合")
    cfg[ACCOUNT_COMBO_REF_KEY] = combo.id
    definition["config"] = cfg
    payload["definition"] = definition
    row.payload = payload
    await db.commit()
    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="account_combo.bind", resource_type="scenario",
        resource_id=scenario_id,
        detail={"op": "bind", "comboId": combo.id,
                "comboName": combo.name, "comboRevision": combo.revision})
    return await _bind_view(db, combo)
