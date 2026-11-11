"""执行配置 API(执行配置与运行方案分层-设计方案 §4/§10 步①)。

个人数据(决策 8 终局):全员可建、owner 隔离 —— 跨 owner 一律 404
(常量池同款口径)。v1 只落 ``user`` scope 行(project 随组级批次 ⑧,
模型已同构);列表/详情/写面均以 ``(scope='user', scope_id=本人)``
为界。零凭证值零地址值(§4):载荷只存引用键 —— bindings(身份面→
槽位)与 carryOverrides(业务参数值内联,null=显式注入 JSON null,
与 carry_store 语义同型)。

链路消费(步②接入,本步只立数据面与管理面):envId 占环境链位
②/④;bindings 覆盖槽位解析序的配置层;carry 覆盖在私有区生效、
项目区默认不吃显式吃(决策 9)。

默认配置:每 scope 至多一行(部分唯一索引),POST /{id}/default
原子切换;删除默认行不级联转移(链回落旧偏好/平台默认,§7)。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models import Environment, ExecConfig

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


def _view(row: ExecConfig) -> ExecConfigView:
    systems = (row.payload or {}).get("systems") or []
    return ExecConfigView(
        id=row.id, name=row.name, isDefault=row.is_default,
        environmentId=row.environment_id, systems=systems)


async def _get_owned(
    db: AsyncSession, config_id: int, user_id: int
) -> ExecConfig:
    row = await db.get(ExecConfig, config_id)
    if row is None or row.scope != "user" or row.scope_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"exec config not found: {config_id}")
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


async def _clear_default(db: AsyncSession, user_id: int) -> None:
    await db.execute(update(ExecConfig).where(
        ExecConfig.scope == "user", ExecConfig.scope_id == user_id,
        ExecConfig.is_default.is_(True),
    ).values(is_default=False))


@router.get("", response_model=list[ExecConfigView])
async def list_exec_configs(user: CurrentUser, db: DbSession) -> Any:
    """本人的执行配置(默认在前,其余按名序)。"""
    rows = (await db.execute(
        select(ExecConfig).where(
            ExecConfig.scope == "user", ExecConfig.scope_id == user.id)
        .order_by(ExecConfig.is_default.desc(), ExecConfig.name.asc())
    )).scalars().all()
    return [_view(r) for r in rows]


@router.post("", response_model=ExecConfigView, status_code=status.HTTP_201_CREATED)
async def create_exec_config(
    body: ExecConfigCreate, user: CurrentUser, db: DbSession
) -> ExecConfigView:
    await _check_env(db, body.environmentId)
    if body.isDefault:
        await _clear_default(db, user.id)
    row = ExecConfig(
        scope="user", scope_id=user.id,
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
    return _view(await _get_owned(db, config_id, user.id))


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
    row = await _get_owned(db, config_id, user.id)
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
    """置为默认(环境链位④载体 + carry 个人默认)。原子切换:同一事务
    先清旧默认再置新;部分唯一索引兜并发(撞索引 → 409)。"""
    row = await _get_owned(db, config_id, user.id)
    await _clear_default(db, user.id)
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
    复用的通道,决策 7 代价的补偿)。副本恒非默认。"""
    src = await _get_owned(db, config_id, user.id)
    row = ExecConfig(
        scope="user", scope_id=user.id,
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
    row = await _get_owned(db, config_id, user.id)
    await db.delete(row)
    await db.commit()
