"""执行配置 API(执行配置与运行方案分层-设计方案 §4/§10 步①⑧)。

两个 scope 同构:
* ``user`` —— 个人面:全员可建、owner 隔离(跨 owner 一律 404,常量池
  同款口径);
* ``project``(⑧ 组级批次)—— 项目变体:读 = 项目成员,写 = 项目管理
  员 ∨ Admin+(与 carry 项目层同门,复用 ``carry._resolve_scope``);
  公共项目不可建(409,同项目凭证裁定)。项目 scope 在链路里只
  携带 **carry 覆盖**(项目区链位:场景显式 > 显式选定个人 > 项目默认
  配置 > 项目层 > 公共项目层);bindings 字段在模型上保留但链路
  无位,暂不消费。

零凭证值零地址值(§4):载荷只存引用键 —— bindings(身份面→条目)与
carryOverrides(业务参数值内联,null=显式注入 JSON null,与 carry_store
语义同型)。

默认配置:每 (scope, scope_id) 至多一行(部分唯一索引),POST
/{id}/default 原子切换;删除默认行不级联转移(链回落下一位)。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models import ExecConfig
from ..models.project import Project

router = APIRouter(prefix="/exec-configs", tags=["exec-configs"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# 引用键长度对齐既有列口径:别名全名 String(128)、条目名 String(64)、
# carry 字段 String(255);carry 值 Text(不限,业务参数)。
# 条目名域订正(2026-11-19):条目名 = service_identities.alias_name
# String(128) —— bindings 值(换用条目名)与 §8.10 aliases 同域;
# 旧「条目名 String(64)」系退役 slot 列口径。
_AliasName = Annotated[str, Field(min_length=1, max_length=128)]
_SlotName = Annotated[str, Field(min_length=1, max_length=128)]
_CarryField = Annotated[str, Field(min_length=1, max_length=255)]
# 配置级元信息(v7):说明/标签 —— 帮助在列表里快速识别/选择配置。
# 存 payload 顶层(JSON 列零迁移);上限对齐 scenario_composer 的
# description(2048)/ tags(32 × 20)。
_Description = Annotated[str, Field(max_length=2048)]
_Tag = Annotated[str, Field(min_length=1, max_length=20)]


def _dedupe_tags(v: list[str]) -> list[str]:
    """strip / 去空 / 截断 20 / 去重(同 scenario_composer._clean_tags 口径)。"""
    out: list[str] = []
    seen: set[str] = set()
    for t in v:
        t = (t or "").strip()
        if not t:
            continue
        t = t[:20]
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


class SystemSubConfig(BaseModel):
    """按系统的子配置(§4:多系统混合编排下每组配置的组成单元)。"""

    service: str = Field(..., min_length=1, max_length=128,
                         description="目录服务名(分组键)")
    # §8.10(2026-11-19):圈定本配置采用的调用身份条目(声明侧)。管理
    # 范围语义 —— 圈定配置页就绪度/拨测/凭证引导的展示范围,**执行链
    # 不消费**(services/exec_config._flatten 只取 bindings/carryOverrides,
    # 场景声明条目仍按原链解析)。存量行缺键 → default [] = 未圈定,
    # 前端按 bindings 声明键推导展示。
    aliases: list[_SlotName] = Field(
        default_factory=list, max_length=64,
        description="本配置采用的调用身份条目名(声明侧;管理范围,执行链不消费)")
    bindings: dict[_AliasName, _SlotName] = Field(
        default_factory=dict, max_length=64,
        description="{身份面(别名全名): 条目名} —— 覆盖条目解析序的配置层")
    carryOverrides: dict[_CarryField, str | None] = Field(
        default_factory=dict, max_length=64,
        description="{字段: 值} —— 该系统在此业务过程下带的参数;"
                    " null = 显式注入 JSON null")


class ExecConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    # 配置级元信息(v7):说明 + 标签(列表识别信息,执行链不消费)
    description: _Description = ""
    tags: list[_Tag] = Field(default_factory=list, max_length=32)
    # §8.2(2026-11-17):environmentId 链位退役 —— 字段删除,旧客户端
    # 多发该键被 pydantic 静默忽略
    systems: list[SystemSubConfig] = Field(default_factory=list,
                                           max_length=64)
    isDefault: bool = False
    # ⑧:project scope(项目变体);projectId 与 scope=project 成对
    scope: Literal["user", "project"] = "user"
    projectId: int | None = Field(default=None, ge=1,
                                  alias="projectId")

    @field_validator("tags", mode="before")
    @classmethod
    def _clean_tags(cls, v: list[str]) -> list[str]:
        return _dedupe_tags(v)


class ExecConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    # None = 不改;""/[] = 显式清空(与 systems 的「整体替换式」同读法)
    description: _Description | None = None
    tags: list[_Tag] | None = None
    systems: list[SystemSubConfig] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _clean_tags(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _dedupe_tags(v)


class ExecConfigCopyIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class ExecConfigView(BaseModel):
    id: int
    name: str
    isDefault: bool
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    systems: list[SystemSubConfig]
    scope: str = "user"


def _view(row: ExecConfig) -> ExecConfigView:
    payload = row.payload or {}
    return ExecConfigView(
        id=row.id, name=row.name, isDefault=row.is_default,
        description=payload.get("description") or "",
        tags=payload.get("tags") or [],
        systems=payload.get("systems") or [],
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
    if body.isDefault:
        await _clear_default(db, scope, scope_id)
    row = ExecConfig(
        scope=scope, scope_id=scope_id,
        name=body.name, is_default=body.isDefault,
        payload={
            "systems": [s.model_dump() for s in body.systems],
            "description": body.description,
            "tags": body.tags,
        },
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
    """整体替换式 PATCH。默认切换不在此面 —— POST /{id}/default
    原子切换。"""
    row = await _access(db, config_id, user, write=True)
    if body.name is not None:
        row.name = body.name
    # payload 合并式更新(v7):只传 systems 的旧客户端不得抹掉说明/标签;
    # description/tags 显式给值(含 ""/[])则覆盖,None = 保持。
    payload = dict(row.payload or {})
    if body.systems is not None:
        payload["systems"] = [s.model_dump() for s in body.systems]
    if body.description is not None:
        payload["description"] = body.description
    if body.tags is not None:
        payload["tags"] = body.tags
    if body.systems is not None or body.description is not None \
            or body.tags is not None:
        row.payload = payload  # 整体赋值(JSON 列需赋值触发变更)
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
    """置为默认(user scope = carry 个人默认;project scope = 项目区
    carry 链的项目配置层)。原子切换:同一事务先清旧默认再置新;部分
    唯一索引兜并发(撞索引 → 409)。"""
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
