"""执行配置 API(执行配置与运行方案分层-设计方案 §4/§10 步①⑧;
v2.10 §5/§11.2 单表显式互斥 FK 形状)。

两个归属同构(DTO 保持 ``scope``/``projectId`` 形状,落库映射到
``principal_id``/``project_id`` 真实 FK 列):
* ``user`` —— 个人面:全员可建、owner 隔离(跨 owner 一律 404,常量池
  同款口径);
* ``project``(⑧ 组级批次)—— 项目变体:读 = 项目成员,写 = 项目管理
  员 ∨ Admin+;私有空间 = 属主可写(§7:私有 项目 ExecConfig 开)、
  他人 404;公共项目不可建(409,同项目凭证裁定)。

单选语义(§11.2,执行链):显式选定本人的个人配置或当前项目的项目
配置;未显式 = 项目默认行;**个人默认仅交互预选,不参与后端自动
解析**。默认配置每侧至多一行(部分唯一索引),POST /{id}/default
原子切换;个人默认行照常可维护(供 UI 预选),删除默认行不级联转移。

零凭证值零地址值(§4):载荷只存引用键 —— bindings(身份面→条目)与
carryOverrides(业务参数值内联,null=显式注入 JSON null,与 carry_store
语义同型)。
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
# 条目名域:条目名 = service_identities.alias_name
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
    # §8.10 圈定即承诺(执行链消费):圈定本配置采用的调用身份条目(声明侧)。**非空 = 白名单
    # 生效**:派发/预检时换用后取用集 ⊄ 圈定集 → 409 identity_not_circled
    # (precheck_hard_gate 同一道门;行级 @slot 绑定同码);空 = 未圈定,
    # 存量兼容(等同白名单关闭)。生效行 = §11.2 单选(显式本人/项目行
    # > 项目默认行;个人默认不参与后端解析);令牌/graph/adhoc 不吃
    # 执行配置,天然不圈。重跑按首发快照照查。
    aliases: list[_SlotName] = Field(
        default_factory=list, max_length=64,
        description="本配置采用的调用身份条目名(圈定即承诺:非空 = "
                    "执行白名单生效,取用集须 ⊆ 圈定集,否则 409;"
                    "空 = 未圈定不校验)")
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
    # environmentId 链位退役(ADR-0003 #21,§8.2)—— 字段删除,旧客户端
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
        scope="user" if row.principal_id is not None else "project")


async def _project_gate(db: AsyncSession, user, project_id: int | None,
                        *, write: bool) -> int:
    """project 归属门:读 = 可见(成员/私有属主),写 = 项目管理员 ∨
    Admin+(普通项目,与 carry 项目层同门)/ 私有空间属主(§7:私有
    项目 ExecConfig 开 —— 容器配置可隔离同一用户的多个空间);公共
    项目拒建(同项目凭证裁定);归档项目拒写(R3-6 同面)。"""
    from ..models.project import ProjectMember
    from ..services.project_access import can_view_project
    from ._ownership import has_capability

    if project_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "project_id_required",
                    "message": "scope=project 需要 projectId"})
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail={"code": "not_found",
                                    "message": "project not found"})
    if proj.kind == "public":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "public_project_no_exec_configs",
                    "message": "公共项目不设项目执行配置(carry 全局默认"
                               "已在公共项目「配置」页签)"})
    if not await can_view_project(db, user.id, proj):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail={"code": "not_found",
                                    "message": "project not found"})
    if proj.kind == "private":
        # 私有空间:属主即容器治理面;他人不可见已由 can_view_project 拦
        if proj.owner_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                detail={"code": "not_found",
                                        "message": "project not found"})
    elif write and not has_capability(user, "ops.write"):
        role = (await db.execute(select(ProjectMember.role).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id))).scalar_one_or_none()
        if role is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                detail={"code": "not_found",
                                        "message": "project not found"})
        if role != "admin":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={"code": "not_project_admin",
                        "message": "项目执行配置由项目管理员维护"})
    # 归档闸(§13.1 生命周期冻结):先归属/角色后 active —— 不可见恒
    # 404,归档态不作存在性探针(r5-2.2 同拍,与项目凭证管理门一致)
    if write and proj.status != Project.STATUS_ACTIVE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "project_not_active",
                    "message": f"项目状态为 {proj.status},"
                               "归档起禁止执行配置管理写(§13.1)"})
    return project_id


async def _access(db: AsyncSession, config_id: int, user,
                  *, write: bool) -> ExecConfig:
    """读 = 本人 ∨ 项目可见(成员/私有属主);写 = 本人(own row)∨
    项目管理员/私有属主。"""
    row = await db.get(ExecConfig, config_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"exec config not found: {config_id}")
    if row.principal_id is not None:
        if row.principal_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                f"exec config not found: {config_id}")
    else:
        await _project_gate(db, user, row.project_id, write=write)
    return row


def _name_conflict(name: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={"code": "exec_config_name_exists",
                "message": f"执行配置名 '{name}' 已存在"})


def _integrity_conflict(e: IntegrityError, name: str) -> HTTPException:
    """按约束名分派(account_integrity_conflict 同款):默认位部分唯一
    索引(uq_exec_configs_{principal,project}_default)的**并发竞争**
    与真撞名分开报 —— 调用方可区分「重试」与「改名」。"""
    orig = getattr(e, "orig", None)
    cname = str(getattr(orig, "constraint_name", "")
                or getattr(getattr(orig, "diag", None),
                           "constraint_name", "") or "")
    if ("uq_exec_configs_principal_default" in cname
            or "uq_exec_configs_project_default" in cname):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "exec_config_default_conflict",
                    "message": "并发切换默认执行配置冲突,请重试"})
    return _name_conflict(name)


async def _clear_default(db: AsyncSession,
                         principal_id: int | None,
                         project_id: int | None) -> None:
    """同侧默认原子清位(先清后置,部分唯一索引兜并发)。"""
    if principal_id is not None:
        await db.execute(update(ExecConfig).where(
            ExecConfig.principal_id == principal_id,
            ExecConfig.is_default.is_(True),
        ).values(is_default=False))
    else:
        await db.execute(update(ExecConfig).where(
            ExecConfig.project_id == project_id,
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
        where = (ExecConfig.project_id == pid,)
    else:
        where = (ExecConfig.principal_id == user.id,)
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
        principal_id, project_id = None, pid
    else:
        principal_id, project_id = user.id, None
    # 写面闸:换用目标须存在且同基础服务,
    # 落库前拦(422 口径同 scenarios 的 binding 校验)
    from ..services.service_aliases import (
        BindingAliasInvalid, validate_slot_overrides)
    try:
        await validate_slot_overrides(db, {
            k: v for s in body.systems for k, v in s.bindings.items()})
    except BindingAliasInvalid as e:
        raise HTTPException(status_code=422, detail={
            "code": e.code, "message": e.message,
            "service": e.service, "alias": e.alias})
    if body.isDefault:
        await _clear_default(db, principal_id, project_id)
    row = ExecConfig(
        principal_id=principal_id, project_id=project_id,
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
        raise _integrity_conflict(e, body.name) from e
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
    # TOK-07 写面闸:systems 显式给定才校验(合并式 PATCH,None=保持旧值)
    if body.systems is not None:
        from ..services.service_aliases import (
            BindingAliasInvalid, validate_slot_overrides)
        try:
            await validate_slot_overrides(db, {
                k: v for s in body.systems for k, v in s.bindings.items()})
        except BindingAliasInvalid as e:
            raise HTTPException(status_code=422, detail={
                "code": e.code, "message": e.message,
                "service": e.service, "alias": e.alias})
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
    """置为默认(个人侧 = UI 交互预选位,后端执行链不自动解析 ——
    §11.2「个人默认仅交互预选」;项目侧 = 未显式时的项目默认单选位)。
    原子切换:同一事务先清旧默认再置新;部分唯一索引兜并发(撞索引
    → 409)。"""
    row = await _access(db, config_id, user, write=True)
    await _clear_default(db, row.principal_id, row.project_id)
    row.is_default = True
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "exec_config_default_conflict",
                    "message": "并发切换默认执行配置冲突,请重试"}) from e
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
        principal_id=src.principal_id, project_id=src.project_id,
        name=body.name, is_default=False,
        # 深拷贝:JSON 列不共享可变对象(改源不牵连副本)
        payload=deepcopy(src.payload) or {"systems": []},
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _integrity_conflict(e, body.name) from e
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
    row = await _access(db, config_id, user, write=False)
    # 聚合单源:此前整循环包在一个 try 里 ——
    # plate 抖动一次即误报全量 orphaned;单源内逐项隔离(/full 失败
    # = 该端点面缺席,不阻塞其余),与 carry_store.carry_drift 同源。
    from ..services.carry_store import plate_carry_faces
    face_by_service, _plate_services, reachable = await plate_carry_faces()

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
