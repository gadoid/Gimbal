"""方案 CRUD 路由(工作台 spec §5;UPC M2:组合绑定显式列 + 修复命令)。

独立于 scenarios.py(它有 /{scenario_id} catch-all,必须最后注册);
嵌套路径与 data_sets.create_router 同款先例。

UPC M2(§16.1/§20.3):

* DTO ``accountComboId`` ↔ ``composer_run_schemes.account_combo_id``
  显式列双向映射(唯一持久化事实,不写入 payload);写面校验经
  ``account_combo.require_combo_bindable``(存在 ∧ 可读 ∧ 同区)。
* DTO 新增 ``repairStatus`` / ``repairReason``(§20.3 授权投影,经
  ``scheme_repair.reasons_for_schemes``)与 ``revision``;内部精确
  原因不直接序列化。
* 修复命令(blocked → ready 的仅有入口,§20.3):
  ``POST .../run-schemes/{scheme_id}/rebind-combo`` 与
  ``POST .../run-schemes/{scheme_id}/confirm-no-combo`` —— 方案写门 +
  expected_revision 原子校验 + 目标组合绑定授权;状态/绑定/revision
  与行级审计同事务(scheme_repair_events)。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.composer_run_scheme import ComposerRunScheme
from ..models.composer_scenario import ComposerScenario
from ._error_mapping import not_found_404
from ..schemas.scenario_composer import RunScheme
from ..services import (account_combo, scenario_store, scheme_repair,
                        scheme_store)

router = APIRouter(prefix="/scenarios", tags=["run-schemes"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _load_row(db: AsyncSession, scenario_id: str) -> ComposerScenario:
    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise not_found_404("scenario", scenario_id)
    return row


async def _require_owner(db, user: CurrentUser, row: ComposerScenario) -> None:
    """写闸(表 B scenario.write,UPC M2:项目关系):运行方案随父场景,
    写权 = 父场景 can(write)(私有空间所有者 ∨ 项目可写成员 ∨ 公共维护者)。"""
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


def _combo_binding_error(e: account_combo.ComboError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": e.code, "message": e.message, **e.detail})


@router.get("/{scenario_id}/run-schemes")
async def list_run_schemes(
    user: CurrentUser, db: DbSession, scenario_id: str,
) -> list[dict]:
    row = await _load_row(db, scenario_id)
    # P2 引用闭包(§7.4):读 = 属主/项目成员/公共读者;写端点仍
    # _require_owner。
    from ._ownership import can_read_scenario_row
    if not await can_read_scenario_row(db, user, row):
        raise not_found_404("scenario", scenario_id)
    # 缺失自动物化默认项(spec §5)— 自愈迁移/钩子漏网的存量场景
    await scheme_store.ensure_default_scheme(db, scenario_id)
    schemes = (await db.execute(
        select(ComposerRunScheme)
        .where(ComposerRunScheme.scenario_id == scenario_id)
        .order_by(ComposerRunScheme.is_default.desc(),
                  ComposerRunScheme.name)
    )).scalars().all()
    reasons = await scheme_repair.reasons_for_schemes(db, user, schemes)
    return [_wire(s, reasons) for s in schemes]


def _wire(s, reasons: dict[str, str | None]) -> dict:
    """方案行 → wire(§9:repairStatus + 投影 repairReason + revision +
    accountComboId 显式列双向映射)。"""
    wire = scheme_store._to_wire(s, repair_reason=reasons.get(s.scheme_id))
    return wire


@router.post("/{scenario_id}/run-schemes", status_code=201)
async def create_run_scheme(
    user: CurrentUser, db: DbSession, scenario_id: str, body: RunScheme,
) -> dict:
    row = await _load_row(db, scenario_id)
    await _require_owner(db, user, row)
    await _require_env(db, body)
    try:
        await account_combo.require_combo_bindable(
            db, user, row, body.account_combo_id)
    except account_combo.ComboError as e:
        raise _combo_binding_error(e) from None
    try:
        return await scheme_store.create_scheme(db, scenario_id,
            name=body.name, payload=_to_payload(body),
            account_combo_id=body.account_combo_id)
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
    await _require_owner(db, user, row)
    await _require_env(db, body)
    try:
        await account_combo.require_combo_bindable(
            db, user, row, body.account_combo_id)
    except account_combo.ComboError as e:
        raise _combo_binding_error(e) from None
    try:
        await scheme_store.update_scheme(
            db, scenario_id, scheme_id,
            name=body.name, payload=_to_payload(body),
            account_combo_id=body.account_combo_id,
            expected_revision=body.expected_revision)
    except KeyError:
        raise HTTPException(status_code=404, detail={
            "code": "run_scheme_not_found",
            "message": f"run scheme {scheme_id} not found"})
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(status_code=409, detail={
                "code": "run_scheme_name_conflict",
                "message": "方案名场景内唯一(「默认方案」为保留名)"})
        if str(e) == "revision_conflict":
            # 评审 P2-14:显式 CAS 落空 —— 方案已被并发修改
            raise HTTPException(status_code=409, detail={
                "code": "scheme_revision_conflict",
                "message": "方案已发生变化(expectedRevision 落空),"
                           "请刷新后重试"})
        if str(e) == "scheme_repair_required":
            # §20.3:普通保存不得改绑 blocked(修复命令是仅有入口)
            raise HTTPException(status_code=409, detail={
                "code": "scheme_repair_required",
                "message": "方案组合依赖待修复,绑定变更须经修复命令"
                           "(rebind-combo / confirm-no-combo)"})
        raise
    scheme = await scheme_store.get_row(db, scenario_id, scheme_id)
    reasons = await scheme_repair.reasons_for_schemes(db, user, [scheme])
    return _wire(scheme, reasons)


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


# ── §20.3 修复命令(blocked → ready 的仅有入口)────────────────────

class RebindComboIn(BaseModel):
    """rebind_combo:指定合法同区组合。目标组合的绑定授权在服务层复核
    (存在 ∧ 可读 ∧ 同区);候选组合错误按 §20.3 脱敏(不可读 = 不存在,
    统一 404/422,不成为存在性探针)。"""

    model_config = ConfigDict(populate_by_name=True)

    combo_id: int = Field(alias="comboId", ge=1)
    expected_revision: int = Field(alias="expectedRevision", ge=1)


class ConfirmNoComboIn(BaseModel):
    """confirm_no_combo:明确确认无组合语义并提供理由(审计留痕)。"""

    model_config = ConfigDict(populate_by_name=True)

    expected_revision: int = Field(alias="expectedRevision", ge=1)
    reason: str = Field(min_length=1, max_length=2048)


def _repair_cmd_error(e: scheme_repair.RepairCommandError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": e.code, "message": e.message})


async def _load_scheme(db, user, scenario_id: str, scheme_id: str):
    """修复命令的统一装载 + 方案写门(§21:scheme.update)。"""
    row = await _load_row(db, scenario_id)
    await _require_owner(db, user, row)
    try:
        scheme = await scheme_store.get_row(db, scenario_id, scheme_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={
            "code": "run_scheme_not_found",
            "message": f"run scheme {scheme_id} not found"}) from None
    return row, scheme


async def _audit_repair(db, user, action: str, scheme_id: str,
                  project_id: int) -> None:
    """修复命令的治理面审计(best-effort;行级同事务审计在
    scheme_repair_events,§20.3 的权威事实源)。"""
    from ..services import audit

    await audit.record(
        db, actor_id=user.id,
        actor_name=getattr(user, "display_name", "") or "",
        action=action, resource_type="run_scheme", resource_id=scheme_id,
        detail={"project_id": project_id})


@router.post("/{scenario_id}/run-schemes/{scheme_id}/rebind-combo")
async def rebind_combo(
    user: CurrentUser, db: DbSession, scenario_id: str, scheme_id: str,
    body: RebindComboIn,
) -> dict:
    _, scheme = await _load_scheme(db, user, scenario_id, scheme_id)
    try:
        await scheme_repair.rebind_combo(
            db, scheme, user=user, combo_id=body.combo_id,
            expected_revision=body.expected_revision)
    except scheme_repair.RepairCommandError as e:
        raise _repair_cmd_error(e) from None
    await db.commit()
    await _audit_repair(db, user, "scheme.repair.rebind_combo",
                  scheme.scheme_id, scheme.project_id)
    reasons = await scheme_repair.reasons_for_schemes(db, user, [scheme])
    return _wire(scheme, reasons)


@router.post("/{scenario_id}/run-schemes/{scheme_id}/confirm-no-combo")
async def confirm_no_combo(
    user: CurrentUser, db: DbSession, scenario_id: str, scheme_id: str,
    body: ConfirmNoComboIn,
) -> dict:
    _, scheme = await _load_scheme(db, user, scenario_id, scheme_id)
    try:
        await scheme_repair.confirm_no_combo(
            db, scheme, user=user,
            expected_revision=body.expected_revision, reason=body.reason)
    except scheme_repair.RepairCommandError as e:
        raise _repair_cmd_error(e) from None
    await db.commit()
    await _audit_repair(db, user, "scheme.repair.confirm_no_combo",
                  scheme.scheme_id, scheme.project_id)
    reasons = await scheme_repair.reasons_for_schemes(db, user, [scheme])
    return _wire(scheme, reasons)
