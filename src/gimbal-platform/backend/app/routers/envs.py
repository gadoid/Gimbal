"""GET /api/envs — list execution environments (V3 composer).

Static list sourced from ``app/core/envs.yaml`` (bundled) or
``data/envs.yaml`` (override).  See :mod:`app.services.env_store`.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..core.deps import CurrentUser
from ..schemas.scenario_composer import RunEnv
from ..services import env_store


router = APIRouter(prefix="/envs", tags=["envs"])


@router.get("", response_model=list[RunEnv])
async def list_envs(user: CurrentUser) -> list[RunEnv]:
    """Return the parsed env list (all logged-in users may read)."""
    return env_store.list_envs()
