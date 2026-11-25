"""账户组合资源 API(设计方案 v4 §5)。

组合 = 服务 → 已登记身份条目的引用集。运行方案通过自身 payload 的
``accountComboId`` 绑定组合;本 router 只管理组合资源,不再提供场景级
绑定端点。引用计数、删除清单均按方案统计。

个人组合仅属主可读可写;项目组合成员可读、WRITER_ROLES 可写,平台
Admin 不旁路。公共项目不创建组合。条目全量校验只在组合保存面,
``revision`` 仅条目变化时递增。
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models import (
    AccountCombo, Deployment, Environment, Service, ServiceIdentity,
    SystemEnvInstance,
)
from ..models.composer_run_scheme import ComposerRunScheme
from ..models.composer_scenario import ComposerScenario
from ..models.project import Project, ProjectMember
from ..models.user import User
from ..services import audit as audit_svc
from ..services.env_chain import EnvMixed, resolve_execution_tag
from ..services.run_prepare import pick_bindings_full
from ..services.zone import (
    ProjectCreateDenied, ensure_can_create_in_project, my_project_roles,
)

router = APIRouter(prefix="/account-combos", tags=["account-combos"])

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


class AccountComboSchemeRef(BaseModel):
    comboId: int
    schemeId: str
    schemeName: str
    scenarioId: str
    scenarioName: str


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
    schemes: list[AccountComboSchemeRef] = Field(default_factory=list)
    updatedAt: datetime | None = None
    updatedByName: str | None = None


class AccountComboProjectGroup(BaseModel):
    projectId: int
    projectName: str
    items: list[AccountComboView]


class AccountComboListOut(BaseModel):
    personal: list[AccountComboView]
    projects: list[AccountComboProjectGroup]


class ComboReadinessEntry(BaseModel):
    service: str
    alias: str
    baseService: str
    system: str | None = None
    identityEnvId: int | None = None
    refMode: str
    refUsername: str | None = None
    poolStatus: Literal["ok", "missing", "ambiguous"]
    accountId: int | None = None
    accountUsername: str | None = None
    accountEnvId: int | None = None
    envMismatch: bool = False


class ComboAddressRow(BaseModel):
    service: str
    envId: int
    envName: str
    baseUrl: str = ""
    loginUrl: str = ""
    deploymentId: int | None = None
    resolved: bool = False


class AccountComboReadiness(BaseModel):
    credentialSource: Literal["personal", "project"]
    projectId: int | None = None
    poolName: str
    canProbeCredentials: bool
    environmentId: int | None = None
    environmentName: str | None = None
    environmentSource: str | None = None
    envError: str | None = None
    ready: bool
    entries: list[ComboReadinessEntry]
    addresses: list[ComboAddressRow]


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


# ── 引用计数 / in-use 清单(方案 payload.accountComboId)────────────

async def _scheme_references(
    db: AsyncSession, *, combo_ids: set[int] | None = None,
) -> list[dict]:
    rows = (await db.execute(
        select(ComposerRunScheme, ComposerScenario.scenario_id,
               ComposerScenario.name)
        .join(ComposerScenario,
              ComposerScenario.scenario_id == ComposerRunScheme.scenario_id)
        .order_by(ComposerScenario.id, ComposerRunScheme.id)
    )).all()
    out: list[dict] = []
    for scheme, scenario_id, scenario_name in rows:
        combo_id = (scheme.payload or {}).get("accountComboId")
        if not isinstance(combo_id, int):
            continue
        if combo_ids is not None and combo_id not in combo_ids:
            continue
        out.append({
            "comboId": combo_id,
            "schemeId": scheme.scheme_id,
            "schemeName": scheme.name,
            "scenarioId": scenario_id,
            "scenarioName": scenario_name or scenario_id,
        })
    return out


async def _referencing_schemes(
    db: AsyncSession, combo_id: int,
) -> list[dict]:
    return [ref for ref in await _scheme_references(db)
            if ref["comboId"] == combo_id]


# ── 访问门(§5.3 范围矩阵:按成员关系判,Admin 不旁路)──────────

async def _access(
    db: AsyncSession, combo_id: int, user, *, write: bool
) -> AccountCombo:
    """读:user 行 = 本人 ∨ project 行 = 成员任一角色;写:user 行 =
    本人 ∨ project 行 = WRITER_ROLES。完全不可见 → 404(不泄露存在性,
    同 D1:项目对象权限只看项目角色,平台 Admin 不旁路)。"""
    stmt = select(AccountCombo).where(AccountCombo.id == combo_id)
    if write:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
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


async def _audit(db, user, action: str, combo: AccountCombo,
                detail: dict) -> None:
    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action=action, resource_type="account_combo",
        resource_id=str(combo.id), resource_name=combo.name, detail=detail)


async def _revive_after_combo_fix(
    row: AccountCombo | None = None, *, project_id: int | None = None,
    user_id: int | None = None,
) -> None:
    """组合修复/重绑 → 暂停集成实例 best-effort 复活(§6.3,同
    missing_credential 族既有暂停/复活模式):复活 = idle + 下拍重试,
    实例若仍缺凭证,预检自会再暂停 —— 与凭证补齐复活同语义;失败不
    阻断写面。传组合行时按 scope 定维(个人 → 属主,项目 → 项目池
    实例);重绑面传场景所在区。"""
    from loguru import logger

    if row is not None:
        if row.scope == "project":
            project_id = row.scope_id
        else:
            user_id = row.scope_id
    try:
        from ..services.integration_runner import revive_paused_instances
        await revive_paused_instances(
            user_id=user_id, project_id=project_id)
    except Exception as e:  # noqa: BLE001 — 复活是增强,失败不阻断写面
        logger.warning("account_combos: 组合修复复活集成实例失败: {}", e)


# ── 组合资源端点 ─────────────────────────────────────────────────

async def _view_rows(
    db: AsyncSession, rows: list[AccountCombo]
) -> list[AccountComboView]:
    """行 → 视图(引用计数/清单 + updatedByName 一次聚合,不在循环内打库)。"""
    refs = await _scheme_references(db, combo_ids={r.id for r in rows})
    by_combo: dict[int, list[dict]] = {}
    for ref in refs:
        by_combo.setdefault(ref["comboId"], []).append(ref)
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
            referenceCount=len(by_combo.get(r.id, [])),
            schemes=by_combo.get(r.id, []),
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


@router.get("/{combo_id}/readiness", response_model=AccountComboReadiness)
async def get_account_combo_readiness(
    combo_id: int, user: CurrentUser, db: DbSession,
    credential_source: Literal["personal", "project"] | None = None,
) -> AccountComboReadiness:
    """按执行人/项目池上下文诊断组合;凭证裁决复用执行单源。"""
    row = await _access(db, combo_id, user, write=False)
    source = credential_source or (
        "project" if row.scope == "project" else "personal")
    project_id = row.scope_id if row.scope == "project" else None
    if source == "project" and project_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "account_combo_scope_mismatch",
                    "message": "个人组合没有项目凭证池,只能按当前用户个人池诊断"})
    entries = [ComboEntry(**e) for e in (row.payload or {}).get(
        "entries", [])]
    aliases = [e.alias for e in entries]
    identity_rows = (await db.execute(
        select(ServiceIdentity).where(
            ServiceIdentity.alias_name.in_(aliases)))).scalars().all() \
        if aliases else []
    identities = {i.alias_name: i for i in identity_rows}
    systems = dict((await db.execute(
        select(Service.name, Service.system).where(
            Service.name.in_({i.base_service for i in identities.values()}))
    )).all()) if identities else {}
    picked, missing, ambiguous = await pick_bindings_full(
        db, user.id, aliases,
        cred_project_id=project_id if source == "project" else None)
    picked_by_alias = {p.slot: p for p in picked}
    missing_set, ambiguous_set = set(missing), set(ambiguous)
    role = (await my_project_roles(db, user.id)).get(project_id) \
        if project_id is not None else None
    can_probe = source == "personal" or role in ProjectMember.WRITER_ROLES

    env_error = None
    try:
        env = await resolve_execution_tag(
            db, identity_names=aliases, project_id=project_id)
    except EnvMixed as e:
        env, env_error = None, str(e)
    env_names = dict((await db.execute(select(Environment.id, Environment.name)))
                     .all())

    readiness_entries: list[ComboReadinessEntry] = []
    for entry in entries:
        ident = identities.get(entry.alias)
        base = ident.base_service if ident else entry.service
        system = systems.get(base)
        account = picked_by_alias.get(entry.alias)
        pool_status = ("ambiguous" if entry.alias in ambiguous_set else
                       "missing" if entry.alias in missing_set else
                       "ok" if account else "missing")
        readiness_entries.append(ComboReadinessEntry(
            service=entry.service, alias=entry.alias, baseService=base,
            system=system, identityEnvId=ident.env_id if ident else None,
            refMode=ident.ref_mode if ident else "",
            refUsername=ident.ref_username if ident else None,
            poolStatus=pool_status,
            accountId=account.account_id if account else None,
            accountUsername=(account.account_username
                             if account and (source == "personal" or can_probe)
                             else "••••" if account else None),
            accountEnvId=account.env_id if account else None,
            envMismatch=bool(account and ident
                             and account.env_id != ident.env_id)))

    bases = {r.baseService for r in readiness_entries}
    known_systems = {r.system for r in readiness_entries if r.system}
    deployments = (await db.execute(select(Deployment).where(
        Deployment.base_service.in_(bases)))).scalars().all() if bases else []
    instances = (await db.execute(select(SystemEnvInstance).where(
        SystemEnvInstance.system.in_(known_systems)))).scalars().all() \
        if known_systems else []
    dep_by_key = {(d.base_service, d.env_id): d for d in deployments}
    instance_by_key = {(i.system, i.env_id): i for i in instances}
    addresses: list[ComboAddressRow] = []
    resolved_services: set[str] = set()
    for item in readiness_entries:
        env_ids = {d.env_id for d in deployments
                   if d.base_service == item.baseService}
        if item.system:
            env_ids.update(i.env_id for i in instances
                           if i.system == item.system)
        for env_id in sorted(env_ids):
            dep = dep_by_key.get((item.baseService, env_id))
            instance = instance_by_key.get((item.system, env_id))
            resolved = bool(env and env.env_id == env_id and dep)
            if resolved:
                resolved_services.add(item.service)
            addresses.append(ComboAddressRow(
                service=item.service, envId=env_id,
                envName=env_names.get(env_id, f"环境 #{env_id}"),
                baseUrl=dep.base_url if dep else "",
                loginUrl=instance.login_url if instance else "",
                deploymentId=dep.id if dep else None, resolved=resolved))
    ready = bool(readiness_entries) and not env_error and all(
        r.poolStatus == "ok" for r in readiness_entries) and \
        resolved_services == {r.service for r in readiness_entries}
    project_name = (await db.execute(select(Project.name).where(
        Project.id == project_id))).scalar() if project_id is not None else None
    return AccountComboReadiness(
        credentialSource=source, projectId=project_id,
        poolName=(project_name or f"项目 #{project_id}") if project_id
        else (user.display_name or user.username),
        canProbeCredentials=can_probe,
        environmentId=env.env_id if env else None,
        environmentName=env_names.get(env.env_id) if env and env.env_id else None,
        environmentSource=env.source if env else None,
        envError=env_error, ready=ready, entries=readiness_entries,
        addresses=addresses)


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
    if entries_changed:
        # 条目修复 → 该组合名下暂停实例复活(§6.3;触发面 = 组合治理
        # 写,凭证补齐先例的对称半边)
        await _revive_after_combo_fix(row)
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
    """置为默认(语义 = 「推荐默认」:新建/另存方案预选,不静默自动
    写入,§4.1)。原子切换:同事务先清旧默认再置新;partial unique 兜并发。"""
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
    refs = await _referencing_schemes(db, row.id)
    if refs:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "account_combo_in_use",
                    "message": "组合仍被运行方案引用,请先在方案内解除绑定",
                    "schemes": refs})
    name_snapshot = row.name
    await db.delete(row)
    await db.commit()
    await _audit(db, user, "account_combo.write", row, {
        "op": "delete", "name": name_snapshot})
