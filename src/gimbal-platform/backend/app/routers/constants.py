"""Constants-pool API —— per-user 常量池条目 CRUD(常量池设计 2026-08-26)。

条目两型互斥: literal(value 字面值)/ generator(spec 含 kind)。后端不
校验 generator 参数合法性 —— 目录描述符驱动前端表单校验,引擎 preprocess
fail-fast 兜底。409 用字典 detail(与 auth_sessions 纯字符串不同):
前端按 ``detail.code == "constant_name_exists"`` 提示。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models import ConstantEntry
from ..schemas.constants import (
    ConstantEntryCreateIn,
    ConstantEntryOut,
    ConstantEntryPatchIn,
    is_literal_primitive,
)

router = APIRouter(prefix="/constants", tags=["constants"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_owned(
    session: AsyncSession, entry_id: int, owner_id: int
) -> ConstantEntry:
    entry = await session.get(ConstantEntry, entry_id)
    if entry is None or entry.owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"constant not found: {entry_id}",
        )
    return entry


def _validate_patch(entry: ConstantEntry, payload: ConstantEntryPatchIn) -> None:
    """PATCH 载荷按行的 entry_kind 校验(依赖 DB 行,schema 层做不了)。"""
    if payload.value is not None:
        if entry.entry_kind != "literal":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="generator 条目不接受 value",
            )
        if not is_literal_primitive(payload.value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="value 必须是 str/int/float/bool",
            )
    if payload.spec is not None:
        if entry.entry_kind != "generator":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="literal 条目不接受 spec",
            )
        if not (
            isinstance(payload.spec.get("kind"), str) and payload.spec["kind"]
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="spec 必须含非空字符串 kind",
            )


@router.get("", response_model=list[ConstantEntryOut])
async def list_constants(
    user: CurrentUser, session: DbSession
) -> list[ConstantEntry]:
    rows = await session.scalars(
        select(ConstantEntry)
        .where(ConstantEntry.owner_id == user.id)
        .order_by(ConstantEntry.name.asc())
    )
    return list(rows)


@router.post("", response_model=ConstantEntryOut, status_code=status.HTTP_201_CREATED)
async def create_constant(
    payload: ConstantEntryCreateIn, user: CurrentUser, session: DbSession
) -> ConstantEntry:
    entry = ConstantEntry(
        owner_id=user.id,
        name=payload.name,
        description=payload.description,
        entry_kind=payload.entry_kind,
        value=payload.value,
        spec=payload.spec,
    )
    session.add(entry)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "constant_name_exists",
                "message": f"常量名 '{payload.name}' 已存在",
            },
        ) from e
    await session.refresh(entry)
    return entry


@router.get("/{entry_id}", response_model=ConstantEntryOut)
async def get_constant(
    entry_id: int, user: CurrentUser, session: DbSession
) -> ConstantEntry:
    return await _get_owned(session, entry_id, user.id)


@router.patch("/{entry_id}", response_model=ConstantEntryOut)
async def patch_constant(
    entry_id: int,
    payload: ConstantEntryPatchIn,
    user: CurrentUser,
    session: DbSession,
) -> ConstantEntry:
    entry = await _get_owned(session, entry_id, user.id)
    _validate_patch(entry, payload)
    if payload.description is not None:
        entry.description = payload.description
    if payload.value is not None:
        entry.value = payload.value
    if payload.spec is not None:
        entry.spec = payload.spec
    await session.commit()
    await session.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_constant(
    entry_id: int, user: CurrentUser, session: DbSession
) -> None:
    entry = await _get_owned(session, entry_id, user.id)
    await session.delete(entry)
    await session.commit()
