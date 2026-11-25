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
from ..schemas.scenario_composer import RunScheme
from ..services import scheme_store, scenario_store

router = APIRouter(prefix="/scenarios", tags=["run-schemes"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _load_row(db: AsyncSession, scenario_id: str) -> ComposerScenario:
    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise not_found_404("scenario", scenario_id)
    return row


async def _require_owner(db, user: CurrentUser, row: ComposerScenario) -> None:
    """写闸(表 B scenario.write,S1.2 区感知):运行方案随父场景,
    写权 = 父场景 can(write)(owner ∨ 项目成员 ∨ 公共维护者)。"""
    from ._ownership import can, can_read_scenario_row

    if not await can_read_scenario_row(db, user, row):
        raise not_found_404("scenario", row.scenario_id)
    if not await can(db, user, "scenario", "write", row):
        raise HTTPException(
            403,
            detail="not_owner: only the scenario's owner (or a project "
                   "member / maintainer) can manage run schemes")


def _to_payload(s: RunScheme) -> dict:
    return s.model_dump(by_alias=True, mode="json")


async def _require_env(db, body: RunScheme) -> None:
    """写时校验:S6 绑定选的别名须存在且与服务键同基础服务。
    (方案不携带环境链位,ADR-0003 #21 —— environmentId 不再收不再校验。)"""
    from ..services.service_aliases import (BindingAliasInvalid,
                                            validate_binding_aliases)
    try:
        await validate_binding_aliases(db, {
            k: b.model_dump() for k, b in body.service_bindings.items()})
    except BindingAliasInvalid as e:
        raise HTTPException(status_code=422, detail={
            "code": e.code, "message": e.message,
            "service": e.service, "alias": e.alias}) from None


async def _require_combo(db, user, row, combo_id: int | None):
    from ..services.account_combo import (ComboBindingError,
                                           require_combo_bindable)
    try:
        return await require_combo_bindable(db, user, row, combo_id)
    except ComboBindingError as e:
        raise HTTPException(status_code=422, detail=e.detail()) from None


async def _record_combo_binding(
    db, user, row, scheme_id: str, old_id: int | None,
    new_id: int | None, combo,
) -> None:
    if old_id == new_id:
        return
    from ..services import audit as audit_svc

    detail = {"op": "unbind" if new_id is None else "bind",
              "schemeId": scheme_id, "comboId": new_id or old_id}
    if combo is not None:
        detail.update(comboName=combo.name, comboRevision=combo.revision)
    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="account_combo.bind", resource_type="scenario",
        resource_id=row.scenario_id, detail=detail)
    if new_id is not None or old_id is not None:
        from .account_combos import _revive_after_combo_fix
        await _revive_after_combo_fix(
            project_id=row.project_id,
            user_id=row.owner_id if row.project_id is None else None)


@router.get("/{scenario_id}/run-schemes")
async def list_run_schemes(
    user: CurrentUser, db: DbSession, scenario_id: str,
) -> list[dict]:
    row = await _load_row(db, scenario_id)
    # P2 引用闭包(§7.4):读 = 属主/admin/引用者;写端点仍 _require_owner。
    from ._ownership import can_read_scenario_row
    if not await can_read_scenario_row(db, user, row):
        raise not_found_404("scenario", scenario_id)
    # 缺失自动物化默认项(spec §5)— 自愈迁移/钩子漏网的存量场景
    await scheme_store.ensure_default_scheme(db, scenario_id)
    return await scheme_store.list_schemes(db, scenario_id)


@router.post("/{scenario_id}/run-schemes", status_code=201)
async def create_run_scheme(
    user: CurrentUser, db: DbSession, scenario_id: str, body: RunScheme,
) -> dict:
    row = await _load_row(db, scenario_id)
    await _require_owner(db, user, row)
    await _require_env(db, body)
    combo = await _require_combo(db, user, row, body.account_combo_id)
    try:
        created = await scheme_store.create_scheme(db, scenario_id,
            name=body.name, payload=_to_payload(body))
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(status_code=409, detail={
                "code": "run_scheme_name_conflict",
                "message": "方案名场景内唯一(「默认方案」为保留名)"})
        raise
    await _record_combo_binding(
        db, user, row, created["schemeId"], None,
        body.account_combo_id, combo)
    return created


@router.put("/{scenario_id}/run-schemes/{scheme_id}")
async def update_run_scheme(
    user: CurrentUser, db: DbSession, scenario_id: str, scheme_id: str,
    body: RunScheme,
) -> dict:
    row = await _load_row(db, scenario_id)
    await _require_owner(db, user, row)
    await _require_env(db, body)
    combo = await _require_combo(db, user, row, body.account_combo_id)
    try:
        existing = await scheme_store.get_row(db, scenario_id, scheme_id)
        old_id = (existing.payload or {}).get("accountComboId")
        updated = await scheme_store.update_scheme(
            db, scenario_id, scheme_id,
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
    await _record_combo_binding(
        db, user, row, scheme_id, old_id, body.account_combo_id, combo)
    return updated


@router.delete("/{scenario_id}/run-schemes/{scheme_id}", status_code=204)
async def delete_run_scheme(
    user: CurrentUser, db: DbSession, scenario_id: str, scheme_id: str,
) -> Response:
    row = await _load_row(db, scenario_id)
    await _require_owner(db, user, row)
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
