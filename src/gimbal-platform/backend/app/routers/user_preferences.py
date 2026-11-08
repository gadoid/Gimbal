"""用户偏好读写 —— 前端 localStorage 存档的服务端落点(换设备不丢)。

形状 = 一人一键一行整值 JSON(见 ``models.permission.UserPref``:复合主键
``(user_id, key)``,无行 id 无时间戳,写即整值覆盖)。所以这里只有两只:

* ``GET /me/preferences`` 一次回全部白名单键 —— 前端登录后就要拿到,
  好让工作台布局/常驻席/配色在首帧就位,而不是等每个页面各自拉一次;
* ``PUT /me/preferences/{key}`` 单键覆盖写(前端防抖后发,一次一个键)。

值本身是前端专有形态(卡片 id、色板 ``var(--avatar-N)`` 名),后端只校
**形状与体积**:校字段就得把卡片注册表抄一份到后端,发版必漂。

2026-11-05 前端评审 P1-2:所有白名单模型改 ``extra="forbid"`` —— 此前
便签条目以驼峰 ``createdAt``/``doneAt`` 提交,与字段名 ``created_at``
不一致被**静默丢弃**(存成空串/None,前端的 7 天自动清理因此永不触发);
拒收未知字段后,这类漂移会直接 422,不再无声吞数据。``NoteItem`` 同时
补 camelCase 别名双向兼容(读旧存档仍认下划线)。
"""
from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import (AliasChoices, BaseModel, ConfigDict, Field, StrictInt,
                      StringConstraints, ValidationError)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models import UserPref

router = APIRouter(prefix="/me/preferences", tags=["me-preferences"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_MAX_VALUE_BYTES = 16 * 1024

_IdStr = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class WorkbenchLayout(BaseModel):
    """启用卡有序列表 + 每卡尺寸。``order`` 里的 id 是不是真存在的卡由
    前端注册表判(读侧静默过滤),这里只管形状。"""

    model_config = ConfigDict(extra="forbid")

    order: list[_IdStr] = Field(default_factory=list, max_length=64)
    sizes: dict[_IdStr, Literal["S", "M", "L"]] = Field(default_factory=dict)


class FollowsPinned(BaseModel):
    """关注页常驻席。空数组是**有效值**(= 用户把常驻全部取消),
    与"从没存过"由 GET 是否回这个键来区分。"""

    ids: list[_IdStr] = Field(default_factory=list, max_length=20)

    model_config = ConfigDict(extra="forbid")


class TimelineColors(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: _IdStr = ""
    scenario: _IdStr = ""
    adaptation: _IdStr = ""


class PagerSizes(BaseModel):
    """各列表页「每页行数」(2026-09-23 分页批次)。键 = 页面标识 slug
    (前端定,如 ``scenarios-mine``/``auths``),值 = 1..500;整值覆盖。"""

    model_config = ConfigDict(extra="forbid")

    sizes: dict[_IdStr, Annotated[StrictInt, Field(ge=1, le=500)]] = Field(
        default_factory=dict, max_length=64)


class IdentityCardPref(BaseModel):
    """工作台身份卡自定义(webhook v4 §4.3/D17):常驻统计 ≤ 4、告警按
    类开关、快捷入口 ≤ 4。id 合法性由前端注册表判(后端不抄一份卡表,
    与本模块「只校形状」的口径一致);与通知开关互不影响。"""

    model_config = ConfigDict(extra="forbid")

    stats: list[_IdStr] = Field(default_factory=list, max_length=4)
    alerts: dict[_IdStr, bool] = Field(default_factory=dict, max_length=16)
    shortcuts: list[_IdStr] = Field(default_factory=list, max_length=4)


class NoteItem(BaseModel):
    """便签条目(D18:便签是工作台注册卡,不进身份卡)。

    前端用驼峰 ``createdAt``/``doneAt``(2026-11-05 评审 P1-2:此前无别名
    也无 forbid,驼峰被静默丢弃 → 存量里 created_at 是空串、done_at 是
    None,「已完成 7 天清理」永不触发)。别名双向兼容:读旧存档仍认
    下划线,出入都以驼峰为准。"""

    model_config = ConfigDict(extra="forbid")

    id: _IdStr
    text: str = Field(min_length=1, max_length=200)
    done: bool = False
    # 入参认驼峰(前端形态)与下划线(修复前的存量档),出参恒驼峰
    created_at: str = Field(
        default="", max_length=32,
        validation_alias=AliasChoices("created_at", "createdAt"),
        serialization_alias="createdAt")
    done_at: str | None = Field(
        default=None, max_length=32,
        validation_alias=AliasChoices("done_at", "doneAt"),
        serialization_alias="doneAt")


class NotesPref(BaseModel):
    """便签卡数据(webhook v4 §4.3):整值覆盖,后写为准(多设备并发
    的取舍见方案 §11 第 5 条);≤ 20 条,已完成 7 天后由前端清理。"""

    model_config = ConfigDict(extra="forbid")

    items: list[NoteItem] = Field(default_factory=list, max_length=20)


class RunEnvironmentPref(BaseModel):
    """S2.2 环境链第四位(个人偏好):``environmentId`` 空 = 不设置。"""
    model_config = ConfigDict(extra="forbid")

    environmentId: int | None = Field(default=None, ge=1)


#: 白名单 = 键 → 校验模型。不在表里的键一律拒读拒写,免得这张表变成
#: 谁都能塞的杂物间(体积/形态都没人管)。
_MODELS: dict[str, type[BaseModel]] = {
    "workbench.layout": WorkbenchLayout,
    "follows.pinned": FollowsPinned,
    "timeline.colors": TimelineColors,
    "pager.sizes": PagerSizes,
    "identity.card": IdentityCardPref,
    "notes": NotesPref,
    "run.environment": RunEnvironmentPref,
}


class PrefOut(BaseModel):
    key: str
    value: dict[str, Any]


class PrefMapOut(BaseModel):
    items: dict[str, dict[str, Any]]


class PrefIn(BaseModel):
    value: Any


async def _row(db: AsyncSession, user_id: int, key: str) -> UserPref | None:
    return (await db.execute(
        select(UserPref).where(
            UserPref.user_id == user_id, UserPref.key == key)
    )).scalar_one_or_none()


@router.get("", response_model=PrefMapOut)
async def get_preferences(user: CurrentUser, db: DbSession) -> PrefMapOut:
    rows = (await db.execute(
        select(UserPref).where(
            UserPref.user_id == user.id, UserPref.key.in_(list(_MODELS)))
    )).scalars().all()
    return PrefMapOut(items={r.key: (r.value or {}) for r in rows})


@router.put("/{key}", response_model=PrefOut)
async def put_preference(
    key: str, body: PrefIn, user: CurrentUser, db: DbSession,
) -> PrefOut:
    model = _MODELS.get(key)
    if model is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "unknown_pref_key",
                    "message": f"不支持的偏好键 ∈ {sorted(_MODELS)}"})
    try:
        clean = model.model_validate(body.value)
    except ValidationError as e:
        first = e.errors()[0] if e.errors() else {}
        raise HTTPException(
            status_code=422,
            detail={"code": "bad_pref_value",
                    "message": f"{'.'.join(str(x) for x in first.get('loc', []))}: "
                               f"{first.get('msg', '形态不符')}"}) from e
    if isinstance(clean, RunEnvironmentPref) and clean.environmentId:
        from ..models.environment import Environment
        if await db.get(Environment, clean.environmentId) is None:
            raise HTTPException(
                status_code=422,
                detail={"code": "environment_not_found",
                        "message": f"environment not found: "
                                   f"{clean.environmentId}"})
    # by_alias:NoteItem 等以驼峰出入(与前端 TS 类型同名);无别名的
    # 模型 by_alias 为恒等,统一走这一条出口。
    payload = clean.model_dump(by_alias=True)
    if len(json.dumps(payload, ensure_ascii=False).encode()) > _MAX_VALUE_BYTES:
        raise HTTPException(
            status_code=422,
            detail={"code": "pref_too_large",
                    "message": f"偏好值超过 {_MAX_VALUE_BYTES // 1024}KB"})

    pref = await _row(db, user.id, key)
    if pref is None:
        db.add(UserPref(user_id=user.id, key=key, value=payload))
    else:
        pref.value = payload   # 整值替换(JSON 列的原地改动不被追踪)
    await db.commit()
    return PrefOut(key=key, value=payload)
