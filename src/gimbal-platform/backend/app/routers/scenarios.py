"""Scenario endpoints (V3 composer).

Path layout (per docs/PLATFORM-SCENARIO-COMPOSER-API.md §4.1–4.7):

* ``POST /api/scenarios/preview-plate``  — Plate ``/convert`` preview
* ``POST /api/scenarios``                 — create
* ``GET  /api/scenarios?q&system&module&priority`` — list
* ``POST /api/scenarios/{id}/star``       — toggle star
* ``GET  /api/scenarios/{id}``            — detail
* ``PUT  /api/scenarios/{id}``            — replace
* ``DELETE /api/scenarios/{id}``          — cascade

**Order matters** (FastAPI matches top-to-bottom).  Static suffixes
(``preview-plate`` / ``/{id}/star``) must precede the catch-all
``/{scenario_id}`` routes, or the ``:path`` converter would capture
their suffix and the static handler would never fire.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import (
    PreviewPlateError,
    PreviewPlateResponse,
    Scenario,
    ScenarioDraft,
    StarIn,
)
from ..services import plate_client, scenario_store
from ..services.marks_store import stars
from sqlalchemy import select


router = APIRouter(prefix="/scenarios", tags=["scenarios"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


# ── helpers ────────────────────────────────────────────────────────
async def _load_row(
    db: AsyncSession, scenario_id: str
) -> ComposerScenario:
    res = await db.execute(
        select(ComposerScenario).where(
            ComposerScenario.scenario_id == scenario_id
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"scenario_not_found: {scenario_id}"
        )
    return row


def _require_owner(user: CurrentUser, row: ComposerScenario) -> None:
    owner_name = row.owner or ""
    user_name = user.display_name or user.username
    # An empty owner (legacy / migrated / plate-synced rows) means "locked":
    # nobody except an admin may modify it. This matches cases_composer's
    # semantics — previously an empty owner made the scenario writable by
    # ANY member.
    if not user.is_admin and user_name != owner_name:
        raise HTTPException(
            status_code=403,
            detail="not_owner: only the scenario's owner (or admin) can modify it",
        )


def _draft_to_full_scenario_dict(
    draft: ScenarioDraft, owner: str
) -> dict:
    """Build a plate-valid Scenario dict from the platform container.

    definition is already plate-shaped (it's the authoritative structure);
    this only fills plate-required defaults that the platform UI doesn't
    collect. orchestration / caseMeta are platform-only and never sent.

    Defaults filled:
    * kind:"scenario"
    * scenarioId (top-level, mirror from definition.meta if absent)
    * meta.createTime (plate requires it; UI doesn't collect → now())
    * meta.requirementRef (plate requires list; UI doesn't collect → [])
    * meta.owner (from authenticated user, if definition left it empty)
    """
    payload = {k: v for k, v in draft.definition.items()}

    payload.setdefault("kind", "scenario")

    meta = payload.setdefault("meta", {})
    if not meta.get("createTime"):
        meta["createTime"] = datetime.utcnow().isoformat() + "Z"
    meta.setdefault("requirementRef", [])
    if owner and not meta.get("owner"):
        meta["owner"] = owner

    payload.setdefault("scenarioId", meta.get("scenarioId", ""))

    return payload


# ── 1) POST /preview-plate (static — must precede /{scenario_id}) ──
@router.post(
    "/preview-plate", response_model=PreviewPlateResponse
)
async def preview_plate(
    user: CurrentUser, db: DbSession, body: ScenarioDraft
) -> PreviewPlateResponse:
    """Forward the draft to Plate's ``/convert`` and return the verdict.

    Does NOT persist anything — the draft is treated as ephemeral so the
    user can preview before saving.  The converted payload (Plate
    /convert 的归一化结果) 也一并返回,前端导出按钮直接用它作为
    "GIMBAL 可执行" 的场景 JSON/YAML。
    """
    scenario_dict = _draft_to_full_scenario_dict(
        body, owner=user.display_name or user.username
    )
    try:
        data = await plate_client.convert(scenario_dict)
    except plate_client.PlateUnavailableError as e:
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_unavailable", "message": e.message},
        )
    except plate_client.PlateRejectedError as e:
        # The upstream 4xx is a verdict on the *client's draft*, not a
        # gateway failure — surface it as 422 (input rejected) instead of
        # 502 so operators don't chase a phantom Plate outage.
        raise HTTPException(
            status_code=422,
            detail={
                "code": "plate_rejected",
                "message": e.message,
                "errors": list(e.errors or []),
            },
        )
    # Plate returns ``{consumer, converted}`` on success.  Treat any
    # ``errors[]`` inside ``converted`` as field-level issues.  We pass
    # the full ``converted`` dict back so the frontend can use it as the
    # canonical "gimbal-executable" structure for export.
    converted = (data or {}).get("converted") or {}
    inner_errors = converted.get("errors") or []
    return PreviewPlateResponse(
        ok=True,
        errors=[PreviewPlateError(**e) for e in inner_errors if isinstance(e, dict)],
        converted=converted if isinstance(converted, dict) else None,
    )


# ── 2) POST / (create) ─────────────────────────────────────────────
@router.post("", response_model=Scenario, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    user: CurrentUser, db: DbSession, body: ScenarioDraft
) -> Scenario:
    owner = user.display_name or user.username
    try:
        return await scenario_store.create(db, body, owner=owner)
    except ValueError as e:
        msg = str(e)
        code = msg.split(":", 1)[0]
        if code == "scenario_id_exists":
            raise HTTPException(status_code=409, detail=msg)
        # Pydantic validation errors already translated to 422 by FastAPI.
        raise HTTPException(status_code=400, detail=msg)


# ── 3) GET / (list) ────────────────────────────────────────────────
@router.get("", response_model=list[Scenario])
async def list_scenarios(
    user: CurrentUser,
    db: DbSession,
    q: str | None = None,
    system: str | None = None,
    module: str | None = None,
    priority: int | None = None,
) -> list[Scenario]:
    return await scenario_store.list_scenarios(
        db,
        q=q,
        system=system,
        module=module,
        priority=priority,
        user_id=user.id,
    )


# ── 4) POST /{id}/star (static suffix — before /{id}) ──────────────
@router.post(
    "/{scenario_id}/star", status_code=status.HTTP_204_NO_CONTENT
)
async def star_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str, body: StarIn
) -> None:
    # Verify the scenario exists (404 instead of silently no-op).
    await _load_row(db, scenario_id)
    stars.set_mark(user.id, scenario_id, body.starred)


# ── 5) GET /{id} ───────────────────────────────────────────────────
@router.get("/{scenario_id}", response_model=Scenario)
async def get_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> Scenario:
    try:
        return await scenario_store.get(db, scenario_id, user_id=user.id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).split(": ", 1)[-1])


# ── 5.1) GET /{id}/draft — 返回完整 ScenarioDraft (含 config/resource) ───
# 用于"从场景库行级导出已保存场景":普通 GET 不带 config/resource 因为
# 列表场景里这份数据量大;draft 是按需调用的。
@router.get("/{scenario_id}/draft", response_model=ScenarioDraft)
async def get_scenario_draft(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> ScenarioDraft:
    row = await _load_row(db, scenario_id)
    payload = row.payload or {}
    try:
        return ScenarioDraft.model_validate(payload)
    except Exception as e:  # noqa: BLE001
        # 内部错误信息只记到日志,对外只暴露最小可读描述
        logger.exception(
            "get_scenario_draft: scenario_id=%s payload corrupted", scenario_id,
        )
        raise HTTPException(
            status_code=500,
            detail="draft_corrupt: 存储的 ScenarioDraft 与 schema 不一致",
        )


# ── 6) PUT /{id} ───────────────────────────────────────────────────
@router.put("/{scenario_id}", response_model=Scenario)
async def put_scenario(
    user: CurrentUser,
    db: DbSession,
    scenario_id: str,
    body: ScenarioDraft,
) -> Scenario:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        return await scenario_store.update(
            db,
            scenario_id,
            body,
            user_id=user.id,
            new_owner=user.display_name or user.username,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).split(": ", 1)[-1])
    except ValueError as e:
        msg = str(e)
        code = msg.split(":", 1)[0]
        if code == "scenario_id_changed":
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)


# ── 7) DELETE /{id} ────────────────────────────────────────────────
@router.delete(
    "/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> None:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        await scenario_store.delete(db, scenario_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).split(": ", 1)[-1])
