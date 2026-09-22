"""场景库「筛选分组」—— 把一组搜索/筛选条件存成有名字的入口,点一下还原。

落库位置 = ``user_prefs``(与通知按 type 开关同表 ``(user_id, key)`` 复合
主键),每桶一行 JSON 列表:换设备 / 清浏览器数据都不丢,且不需要新表、
新迁移。分组是**条件快照**不是场景实体 —— 场景本体不受影响,删分组不动
任何场景数据。

写操作按单条粒度(create / delete)而不是整表覆盖:两个标签页各自读到的
列表早晚过期,整表 PUT 会把另一页刚存的分组冲掉。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models import UserPref

router = APIRouter(
    prefix="/scenario-filter-groups", tags=["scenario-filter-groups"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

#: 分桶 = 场景库的两个列表页;条件在 mine/public 之间不互用(可见范围不同)。
Bucket = Literal["mine", "public"]

_PREF_KEY = "scenario_filter_groups"
MAX_GROUPS = 30
_MAX_FILTER_BYTES = 8 * 1024


def _pref_key(bucket: str) -> str:
    return f"{_PREF_KEY}.{bucket}"


class GroupOut(BaseModel):
    id: str
    name: str
    q: str = ""
    filters: dict[str, Any] = Field(default_factory=dict)
    # 落库是 aware ISO(带 offset):前端 new Date() 才不会把 UTC 读成本地
    created_at: str = Field(default="", alias="createdAt")

    model_config = {"populate_by_name": True}


class GroupListOut(BaseModel):
    items: list[GroupOut]


class GroupIn(BaseModel):
    bucket: Bucket
    name: str = Field(min_length=1, max_length=30)
    q: str = Field(default="", max_length=200)
    #: 前端 utils/filters.ts 的 ScenarioFilters —— 对本层是不透明 JSON,
    #  只做体积护栏,不校验字段(校验会把后端焊死在前端的筛选形态上)。
    filters: dict[str, Any] = Field(default_factory=dict)


def _to_group(raw: Any) -> dict[str, Any]:
    """读侧整形:脏键/缺键不炸列表(与前端读侧 sanitize 同思路)。"""
    g = raw if isinstance(raw, dict) else {}
    filters = g.get("filters")
    return {
        "id": str(g.get("id") or ""),
        "name": str(g.get("name") or ""),
        "q": str(g.get("q") or ""),
        "filters": filters if isinstance(filters, dict) else {},
        "created_at": str(g.get("created_at") or ""),
    }


async def _read(db: AsyncSession, user_id: int, bucket: str):
    pref = (await db.execute(
        select(UserPref).where(
            UserPref.user_id == user_id, UserPref.key == _pref_key(bucket))
    )).scalar_one_or_none()
    raw = (pref.value or {}).get("groups") if pref else None
    groups = [_to_group(g) for g in raw] if isinstance(raw, list) else []
    return pref, groups


async def _write(db: AsyncSession, user_id: int, bucket: str,
                 pref: UserPref | None, groups: list[dict[str, Any]]) -> None:
    # 整对象重新赋值(SQLAlchemy 不追踪 JSON 列的原地改动)
    value = {"groups": groups}
    if pref is None:
        db.add(UserPref(user_id=user_id, key=_pref_key(bucket), value=value))
    else:
        pref.value = value
    await db.commit()


@router.get("", response_model=GroupListOut)
async def list_groups(
    user: CurrentUser, db: DbSession, bucket: Bucket = "mine",
) -> GroupListOut:
    _, groups = await _read(db, user.id, bucket)
    return GroupListOut(items=[GroupOut(**g) for g in groups])


@router.post("", response_model=GroupOut)
async def create_group(
    user: CurrentUser, db: DbSession, body: GroupIn,
) -> GroupOut:
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=422,
            detail={"code": "empty_name", "message": "分组名不能只有空格"})
    if len(json.dumps(body.filters, ensure_ascii=False).encode()) > _MAX_FILTER_BYTES:
        raise HTTPException(
            status_code=422,
            detail={"code": "filters_too_large",
                    "message": f"筛选条件超过 {_MAX_FILTER_BYTES // 1024}KB"})

    pref, groups = await _read(db, user.id, body.bucket)
    idx = next((i for i, g in enumerate(groups) if g["name"] == name), -1)
    if idx < 0 and len(groups) >= MAX_GROUPS:
        raise HTTPException(
            status_code=409,
            detail={"code": "group_limit",
                    "message": f"分组上限 {MAX_GROUPS} 个 —— 先删一个再存"})
    item = {
        # 同名覆盖沿用原 id:高亮/展开态跟着新条件走,而不是断在旧 id 上
        "id": groups[idx]["id"] if idx >= 0 else f"g-{uuid4().hex[:10]}",
        "name": name,
        "q": body.q.strip(),
        "filters": body.filters,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if idx >= 0:
        groups[idx] = item
    else:
        groups.append(item)
    await _write(db, user.id, body.bucket, pref, groups)
    return GroupOut(**item)


@router.delete("/{bucket}/{group_id}")
async def delete_group(
    user: CurrentUser, db: DbSession, bucket: Bucket, group_id: str,
) -> dict:
    pref, groups = await _read(db, user.id, bucket)
    kept = [g for g in groups if g["id"] != group_id]
    if len(kept) == len(groups):
        raise HTTPException(
            status_code=404,
            detail={"code": "group_not_found", "message": "分组不存在"})
    await _write(db, user.id, bucket, pref, kept)
    return {"removed": group_id}
