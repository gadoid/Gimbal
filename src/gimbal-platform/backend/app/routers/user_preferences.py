"""用户偏好读写 —— 前端 localStorage 存档的服务端落点(换设备不丢)。

形状 = 一人一键一行整值 JSON(见 ``models.permission.UserPref``:复合主键
``(user_id, key)``,无行 id 无时间戳,写即整值覆盖)。所以这里只有两只:

* ``GET /me/preferences`` 一次回全部白名单键 —— 前端登录后就要拿到,
  好让工作台布局/常驻席/配色在首帧就位,而不是等每个页面各自拉一次;
* ``PUT /me/preferences/{key}`` 单键覆盖写(前端防抖后发,一次一个键)。

值本身是前端专有形态(卡片 id、色板 ``var(--avatar-N)`` 名),后端只校
**形状与体积**:校字段就得把卡片注册表抄一份到后端,发版必漂。
"""
from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints, ValidationError
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

    order: list[_IdStr] = Field(default_factory=list, max_length=64)
    sizes: dict[_IdStr, Literal["S", "M", "L"]] = Field(default_factory=dict)


class FollowsPinned(BaseModel):
    """关注页常驻席。空数组是**有效值**(= 用户把常驻全部取消),
    与"从没存过"由 GET 是否回这个键来区分。"""

    ids: list[_IdStr] = Field(default_factory=list, max_length=20)


class TimelineColors(BaseModel):
    execution: _IdStr = ""
    scenario: _IdStr = ""
    adaptation: _IdStr = ""


#: 白名单 = 键 → 校验模型。不在表里的键一律拒读拒写,免得这张表变成
#: 谁都能塞的杂物间(体积/形态都没人管)。
_MODELS: dict[str, type[BaseModel]] = {
    "workbench.layout": WorkbenchLayout,
    "follows.pinned": FollowsPinned,
    "timeline.colors": TimelineColors,
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
    payload = clean.model_dump()
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
