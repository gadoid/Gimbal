"""方案 CRUD 路由(工作台 spec §5)。

独立于 scenarios.py(它有 /{scenario_id} catch-all,必须最后注册);
嵌套路径与 data_sets.create_router 同款先例。悬空引用告警不在此层
重复 —— 工作台前端有死因判定面,dispatch 侧仍有兜底 warn。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.composer_scenario import ComposerScenario
from ._error_mapping import not_found_404
from ._ownership import ensure_owner
from ..schemas.scenario_composer import RunScheme
from ..services import scheme_store, scenario_store

router = APIRouter(prefix="/scenarios", tags=["run-schemes"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _load_row(db: AsyncSession, scenario_id: str) -> ComposerScenario:
    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise not_found_404("scenario", scenario_id)
    return row


def _require_owner(user: CurrentUser, row: ComposerScenario) -> None:
    ensure_owner(
        user, row.owner_id,
        "not_owner: only the scenario's owner (or admin) can manage run schemes",
    )


def _to_payload(s: RunScheme) -> dict:
    return s.model_dump(by_alias=True, mode="json")


@router.get("/{scenario_id}/run-schemes")
async def list_run_schemes(
    user: CurrentUser, db: DbSession, scenario_id: str,
) -> list[dict]:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    # 缺失自动物化默认项(spec §5)— 自愈迁移/钩子漏网的存量场景
    await scheme_store.ensure_default_scheme(db, scenario_id)
    return await scheme_store.list_schemes(db, scenario_id)


@router.post("/{scenario_id}/run-schemes", status_code=201)
async def create_run_scheme(
    user: CurrentUser, db: DbSession, scenario_id: str, body: RunScheme,
) -> dict:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        return await scheme_store.create_scheme(db, scenario_id,
            name=body.name, payload=_to_payload(body))
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(status_code=409, detail={
                "code": "run_scheme_name_conflict",
                "message": "方案名场景内唯一(「默认方案」为保留名)"})
        raise


@router.put("/{scenario_id}/run-schemes/{scheme_id}")
async def update_run_scheme(
    user: CurrentUser, db: DbSession, scenario_id: str, scheme_id: str,
    body: RunScheme,
) -> dict:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        return await scheme_store.update_scheme(db, scenario_id, scheme_id,
            name=body.name, payload=_to_payload(body))
    except KeyError:
        raise HTTPException(status_code=404, detail={
            "code": "run_scheme_not_found",
            "message": f"run scheme {scheme_id} not found"})
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(status_code=409, detail={
                "code": "run_scheme_name_conflict",
                "message": "方案名场景内唯一(「默认方案」为保留名)"})
        raise


@router.delete("/{scenario_id}/run-schemes/{scheme_id}", status_code=204)
async def delete_run_scheme(
    user: CurrentUser, db: DbSession, scenario_id: str, scheme_id: str,
) -> Response:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        await scheme_store.delete_scheme(db, scenario_id, scheme_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={
            "code": "run_scheme_not_found",
            "message": f"run scheme {scheme_id} not found"})
    except ValueError as e:
        if str(e) == "default_protected":
            raise HTTPException(status_code=405, detail={
                "code": "run_scheme_default_protected",
                "message": "默认方案不可删除"})
        raise
    return Response(status_code=204)
