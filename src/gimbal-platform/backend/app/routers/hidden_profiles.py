"""Hidden field profile API (Spec-2 §4.3 C2).

One profile per (user, case_id).  GET returns the saved list of
hidden dot-paths (or empty list if none).  PUT replaces the list.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path as PathParam, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models import HiddenFieldProfile
from ..schemas.hidden_profile import HiddenProfileOut, HiddenProfilePatchIn

router = APIRouter(prefix="/cases", tags=["hidden-profiles"])


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_profile(
    session: AsyncSession, user_id: int, case_id: str
) -> HiddenFieldProfile | None:
    rows = (
        await session.execute(
            select(HiddenFieldProfile).where(
                HiddenFieldProfile.user_id == user_id,
                HiddenFieldProfile.case_id == case_id,
            )
        )
    ).scalars().all()
    return rows[0] if rows else None


@router.get("/{case_id}/hidden", response_model=HiddenProfileOut)
async def get_hidden(
    case_id: Annotated[str, PathParam(min_length=1)],
    user: CurrentUser,
    session: DbSession,
) -> HiddenProfileOut:
    row = await _get_profile(session, user.id, case_id)
    if row is None:
        return HiddenProfileOut(case_id=case_id, hidden_paths=[], scope="case")
    return HiddenProfileOut.model_validate(row)


@router.put("/{case_id}/hidden", response_model=HiddenProfileOut)
async def put_hidden(
    case_id: Annotated[str, PathParam(min_length=1)],
    payload: HiddenProfilePatchIn,
    user: CurrentUser,
    session: DbSession,
) -> HiddenProfileOut:
    row = await _get_profile(session, user.id, case_id)
    if row is None:
        row = HiddenFieldProfile(
            user_id=user.id,
            case_id=case_id,
            hidden_paths=payload.hidden_paths,
            scope=payload.scope,
        )
        session.add(row)
    else:
        row.hidden_paths = payload.hidden_paths
        row.scope = payload.scope
    await session.commit()
    await session.refresh(row)
    return HiddenProfileOut.model_validate(row)