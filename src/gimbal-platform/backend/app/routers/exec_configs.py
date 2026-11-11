"""执行配置 API(执行配置与运行方案分层-设计方案 §4/§10 步①⑧)。

两个 scope 同构:
* ``user`` —— 个人面:全员可建、owner 隔离(跨 owner 一律 404,常量池
  同款口径);
* ``project``(⑧ 组级批次)—— 项目变体:读 = 项目成员,写 = 项目管理
  员 ∨ Admin+(与 carry 项目层同门,复用 ``carry._resolve_scope``);
  公共项目不可建(409,同项目凭证裁定)。项目 scope 在 v1 链路里只
  携带 **carry 覆盖**(项目区链位:场景显式 > 显式选定个人 > 项目默认
  配置 > 项目层 > 公共项目层);env/bindings 字段在模型上保留但链路
  无位,暂不消费(§5 环境链/绑定链无项目配置位)。

零凭证值零地址值(§4):载荷只存引用键 —— bindings(身份面→槽位)与
carryOverrides(业务参数值内联,null=显式注入 JSON null,与 carry_store
语义同型)。

默认配置:每 (scope, scope_id) 至多一行(部分唯一索引),POST
/{id}/default 原子切换;删除默认行不级联转移(链回落下一位)。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models import Environment, ExecConfig
from ..models.project import Project

router = APIRouter(prefix="/exec-configs", tags=["exec-configs"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# 引用键长度对齐既有列口径:别名全名 String(128)、槽位名 String(64)、
# carry 字段 String(255);carry 值 Text(不限,业务参数)。
_AliasName = Annotated[str, Field(min_length=1, max_length=128)]
_SlotName = Annotated[str, Field(min_length=1, max_length=64)]
_CarryField = Annotated[str, Field(min_length=1, max_length=255)]


class SystemSubConfig(BaseModel):
    """按系统的子配置(§4:多系统混合编排下每组配置的组成单元)。"""

    service: str = Field(..., min_length=1, max_length=128,
                         description="目录服务名(分组键)")
    bindings: dict[_AliasName, _SlotName] = Field(
        default_factory=dict, max_length=64,
        description="{身份面(别名全名): 槽位名} —— 覆盖槽位解析序的配置层")
    carryOverrides: dict[_CarryField, str | None] = Field(
        default_factory=dict, max_length=64,
        description="{字段: 值} —— 该系统在此业务过程下带的参数;"
                    " null = 显式注入 JSON null")


class ExecConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    environmentId: int | None = None
    systems: list[SystemSubConfig] = Field(default_factory=list,
                                           max_length=64)
    isDefault: bool = False
    # ⑧:project scope(项目变体);projectId 与 scope=project 成对
    scope: Literal["user", "project"] = "user"
    projectId: int | None = Field(default=None, ge=1,
                                  alias="projectId")


class ExecConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    environmentId: int | None = None
    systems: list[SystemSubConfig] | None = None


class ExecConfigCopyIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class ExecConfigView(BaseModel):
    id: int
    name: str
    isDefault: bool
    environmentId: int | None
    systems: list[SystemSubConfig]
    scope: str = "user"


def _view(row: ExecConfig) -> ExecConfigView:
    systems = (row.payload or {}).get("systems") or []
    return ExecConfigView(
        id=row.id, name=row.name, isDefault=row.is_default,
        environmentId=row.environment_id, systems=systems,
        scope=row.scope)


async def _project_gate(db: AsyncSession, user, project_id: int | None,
                        *, write: bool) -> int:
    """project scope 门:读 = 成员,写 = 项目管理员 ∨ Admin+(复用 carry
    的 ``_resolve_scope`` 同一口径);公共项目拒建(同项目凭证裁定)。"""
    from .carry import _resolve_scope

    if project_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "project_id_required",
                    "message": "scope=project 需要 projectId"})
    kind = (await db.execute(select(Project.kind).where(
        Project.id == project_id))).scalar()
    if kind == "public":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "public_project_no_exec_configs",
                    "message": "公共项目不设项目执行配置(carry 全局默认"
                               "已在公共项目「配置」页签)"})
    sc = await _resolve_scope(db, user, "project", project_id, write=write)
    return sc[1]


async def _access(db: AsyncSession, config_id: int, user,
                  *, write: bool) -> ExecConfig:
    """读 = 本人 ∨ 项目成员;写 = 本人(own row)∨ 项目管理员。"""
    row = await db.get(ExecConfig, config_id)
    if row is None or row.scope == "user" and row.scope_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"exec config not found: {config_id}")
    if row.scope == "project":
        await _project_gate(db, user, row.scope_id, write=write)
    return row


async def _check_env(db: AsyncSession, env_id: int | None) -> None:
    if env_id is not None and await db.get(Environment, env_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "environment_not_found",
                    "message": f"environment not found: {env_id}"})


def _name_conflict(name: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={"code": "exec_config_name_exists",
                "message": f"执行配置名 '{name}' 已存在"})


async def _clear_default(db: AsyncSession,
                         scope: str, scope_id: int) -> None:
    await db.execute(update(ExecConfig).where(
        ExecConfig.scope == scope, ExecConfig.scope_id == scope_id,
        ExecConfig.is_default.is_(True),
    ).values(is_default=False))


@router.get("", response_model=list[ExecConfigView])
async def list_exec_configs(
    user: CurrentUser, db: DbSession,
    projectId: Annotated[int | None, Query(ge=1)] = None,
) -> Any:
    """本人的执行配置(缺省);``?projectId=`` → 该项目的项目变体
    (读 = 项目成员;默认在前,其余按名序)。"""
    if projectId is not None:
        pid = await _project_gate(db, user, projectId, write=False)
        where = (ExecConfig.scope == "project",
                 ExecConfig.scope_id == pid)
    else:
        where = (ExecConfig.scope == "user", ExecConfig.scope_id == user.id)
    rows = (await db.execute(
        select(ExecConfig).where(*where)
        .order_by(ExecConfig.is_default.desc(), ExecConfig.name.asc())
    )).scalars().all()
    return [_view(r) for r in rows]


@router.post("", response_model=ExecConfigView, status_code=status.HTTP_201_CREATED)
async def create_exec_config(
    body: ExecConfigCreate, user: CurrentUser, db: DbSession
) -> ExecConfigView:
    if body.scope == "project":
        pid = await _project_gate(db, user, body.projectId, write=True)
        scope, scope_id = "project", pid
    else:
        scope, scope_id = "user", user.id
    await _check_env(db, body.environmentId)
    if body.isDefault:
        await _clear_default(db, scope, scope_id)
    row = ExecConfig(
        scope=scope, scope_id=scope_id,
        name=body.name, is_default=body.isDefault,
        environment_id=body.environmentId,
        payload={"systems": [s.model_dump() for s in body.systems]},
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _name_conflict(body.name) from e
    await db.refresh(row)
    return _view(row)


@router.get("/{config_id}", response_model=ExecConfigView)
async def get_exec_config(
    config_id: int, user: CurrentUser, db: DbSession
) -> ExecConfigView:
    return _view(await _access(db, config_id, user, write=False))


@router.patch("/{config_id}", response_model=ExecConfigView)
async def patch_exec_config(
    config_id: int,
    body: ExecConfigUpdate,
    user: CurrentUser,
    db: DbSession,
) -> ExecConfigView:
    """整体替换式 PATCH;``environmentId`` 用 model_fields_set 区分
    「未提供」与「显式置空(不设置环境)」(projects 同款)。默认切换
    不在此面 —— POST /{id}/default 原子切换。"""
    row = await _access(db, config_id, user, write=True)
    if "environmentId" in body.model_fields_set:
        await _check_env(db, body.environmentId)
        row.environment_id = body.environmentId
    if body.name is not None:
        row.name = body.name
    if body.systems is not None:
        row.payload = {"systems": [s.model_dump() for s in body.systems]}
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _name_conflict(body.name or row.name) from e
    await db.refresh(row)
    return _view(row)


@router.post("/{config_id}/default", response_model=ExecConfigView)
async def set_default_exec_config(
    config_id: int, user: CurrentUser, db: DbSession
) -> ExecConfigView:
    """置为默认(user scope = 环境链位④载体 + carry 个人默认;project
    scope = 项目区 carry 链的项目配置层)。原子切换:同一事务先清旧默认
    再置新;部分唯一索引兜并发(撞索引 → 409)。"""
    row = await _access(db, config_id, user, write=True)
    await _clear_default(db, row.scope, row.scope_id)
    row.is_default = True
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "default exec config changed concurrently; retry") from e
    await db.refresh(row)
    return _view(row)


@router.post("/{config_id}/copy", response_model=ExecConfigView,
             status_code=status.HTTP_201_CREATED)
async def copy_exec_config(
    config_id: int,
    body: ExecConfigCopyIn,
    user: CurrentUser,
    db: DbSession,
) -> ExecConfigView:
    """复制为新命名配置(§4「新建可自现有配置复制」—— 跨配置字段
    复用的通道,决策 7 代价的补偿)。副本恒非默认、同 scope。"""
    src = await _access(db, config_id, user, write=True)
    row = ExecConfig(
        scope=src.scope, scope_id=src.scope_id,
        name=body.name, is_default=False,
        environment_id=src.environment_id,
        # 深拷贝:JSON 列不共享可变对象(改源不牵连副本)
        payload=deepcopy(src.payload) or {"systems": []},
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _name_conflict(body.name) from e
    await db.refresh(row)
    return _view(row)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exec_config(
    config_id: int, user: CurrentUser, db: DbSession
) -> None:
    row = await _access(db, config_id, user, write=True)
    await db.delete(row)
    await db.commit()


@router.get("/{config_id}/drift")
async def exec_config_drift(
    config_id: int, user: CurrentUser, db: DbSession
) -> dict:
    """③ 关联枢纽:配置 carryOverrides vs plate carry 面的 diff。

    与 ``carry_store.carry_drift`` 同口径的轻量版 —— 键域 = **本配置
    覆盖的字段**(不是整张值表):``orphaned`` = 覆盖了但面已没有
    (配置漂移,应删改);``uncovered`` = 面上有而配置未覆盖(按层序
    合成的部分,提示可覆盖面)。plate 不可达 → ``plateReachable=
    False``,调用方先看信号再渲染(不可达 ≠ 全漂移)。"""
    from ..services.adaptation_service import (
        _plate_full_endpoint, _plate_list_endpoints)
    from ..services.field_state_resolution import carry_face
    from ..services.plate_client import PlateUnavailableError

    row = await _access(db, config_id, user, write=False)
    face_by_service: dict[str, set[str]] = {}
    reachable = True
    try:
        for item in await _plate_list_endpoints():
            svc = item.get("service")
            eid = item.get("id")
            if not svc or not eid:
                continue
            full = await _plate_full_endpoint(eid)
            if full is None:
                continue
            decls = ((full.get("request") or {}).get("declarations")) or []
            face_by_service.setdefault(svc, set()).update(carry_face(decls))
    except PlateUnavailableError:
        reachable = False

    out: list[dict] = []
    systems = (row.payload or {}).get("systems") or []
    seen: set[str] = set()
    for s in systems:
        if not isinstance(s, dict):
            continue
        svc = str(s.get("service") or "")
        if not svc or svc in seen:
            continue
        seen.add(svc)
        overridden = set((s.get("carryOverrides") or {}).keys())
        face = face_by_service.get(svc, set())
        out.append({
            "service": svc,
            "orphaned": sorted(overridden - face),
            "uncovered": sorted(face - overridden),
        })
    return {"services": out, "plateReachable": reachable}
