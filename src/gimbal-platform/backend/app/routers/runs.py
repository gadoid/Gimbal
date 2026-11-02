"""POST /api/runs — trigger a Scenario run (V3 composer).

Thin wrapper around :func:`app.services.run_dispatcher.dispatch_run`
(which creates the Execution row and spawns the per-(dataset × row)
fan-out: compose → Plate /convert → case 落盘 → ``gimbal run launch``
子进程执行).

The former Case layer was dissolved — the run recipe (dataSetIds /
serviceBindings / runOptions) lives entirely in
``RunRequest``; the dispatcher materializes it into ``config_json``
(injectedAuths = 模板扫描 ∪ serviceBindings 绑定).  The former ``env``
field was retired (D2) — stale env keys from old clients are silently
ignored (pydantic extra=ignore).

认证(webhook 设计 v3 P1 §4.4):``principal_or_user`` 分流 —— JWT
行为不变;``Bearer gic_…`` 入站凭证进个人(grant)/平台(无 grant)
模式。平台模式不做属主闸,改为执行区间只读闸(``is_scenario_read_
only``,D6:只放行 GET/HEAD/OPTIONS 或 query_safe);个人模式以 grant
用户过原有属主闸(§4.3)。

Error mapping (per the agreed run-failure semantics):
* scenario / data_set missing → 404
* empty dataSetIds is legal (D12 baseline run: one implicit empty
  override row — direct-fill values + shared-var defaults)
* plate / launcher 故障 mid-fan-out → the Execution row is marked
  ``status='failed'`` and the JSONL log records the error, but the
  response is **201 with runId** (so the UI can navigate to
  ``/executions`` and see what happened).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import principal_or_user
from ..schemas.scenario_composer import (
    DataSetSelection, RunOptions, RunRequest, RunResponse, ServiceBinding,
)
from ..services import run_dispatcher, scenario_store
from ..services.inbound_identity import Principal, valid_callback_path


router = APIRouter(prefix="/runs", tags=["runs"])


DbSession = Annotated[AsyncSession, Depends(get_db)]
PrincipalIn = Annotated[Principal, Depends(principal_or_user)]


# M1(修复方案 2026-11-01 §1):入站调用**只能选择平台上已有的配方,
# 不能携带配方** —— 服务地址/凭证别名/数据集/注入条目一律由服务端按
# 运行方案读取(方案由场景属主在平台维护,是可信来源)。否则
# serviceBindings.url 可以改写被测地址、把注入的凭证发到任意主机
# (实测 201 且绑定原样到达 fanout)。
_INBOUND_FORBIDDEN_FIELDS = (
    ("service_bindings", "serviceBindings"),
    ("data_set_ids", "dataSetIds"),
    ("data_set_selection", "dataSetSelection"),
    ("injection_entry_ids", "injectionEntryIds"),
)
# runOptions 只开放 stepTo(截断执行,无地址/凭证语义);其余键任何
# 非缺省值都拒 —— 尤其 nRuns/parallel(资源面)与 debug(强制 server 链)。
_INBOUND_OPTIONS_DENIED = (
    ("debug", "runOptions.debug"),
    ("step_from", "runOptions.stepFrom"),
    ("subscribe", "runOptions.subscribe"),
)


def _reject_inbound_recipe(body: RunRequest) -> None:
    offenders: list[str] = [
        label for attr, label in _INBOUND_FORBIDDEN_FIELDS
        if getattr(body, attr)
    ]
    if body.graph is not None:
        offenders.append("graph")
    opts = body.run_options
    if opts is not None:
        offenders.extend(
            label for attr, label in _INBOUND_OPTIONS_DENIED
            if getattr(opts, attr) is not None)
        if int(opts.n_runs or 1) != 1:
            offenders.append("runOptions.nRuns")
        if int(opts.parallel or 1) != 1:
            offenders.append("runOptions.parallel")
    if offenders:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "inbound_field_not_allowed",
                "message": ("入站调用不能携带执行配方,以下字段由服务端按"
                            "运行方案读取: " + "、".join(offenders)),
                "fields": offenders,
            })


async def _apply_scheme_recipe(
    db: AsyncSession, scen, body: RunRequest,
) -> None:
    """M1:按方案覆盖请求配方(入站分支专用,见模块注释)。

    - ``schemeId`` 显式给出:必须属于本场景,否则 422 ``scheme_not_owned``
      (调用方给了错的 id 就明确拒绝 —— 静默回落默认方案会跑错配方);
    - 未给:默认方案(``scheme_store.resolve_for_run`` 同一实现,与集成
      链的选择段不漂移),无方案 = 空配方(基线执行口径);
    - 覆盖 serviceBindings / dataSetIds / dataSetSelection /
      injectionEntryIds,runOptions 以方案 options 为底、仅用请求的
      ``stepTo`` 覆盖;``schemeId`` / ``schemeName`` 写方案真值(溯源)。
    """
    from ..services import scheme_store

    scheme = None
    if body.scheme_id:
        try:
            scheme = await scheme_store.get_row(
                db, scen.scenario_id, body.scheme_id)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "scheme_not_owned",
                    "message": f"执行方案不存在或不属于该场景: {body.scheme_id}",
                }) from None
    else:
        scheme = await scheme_store.resolve_for_run(
            db, scen.scenario_id, None)
    payload = (scheme.payload if scheme is not None else {}) or {}
    body.service_bindings = {
        k: ServiceBinding(**v)
        for k, v in (payload.get("serviceBindings") or {}).items()
        if isinstance(v, dict)
    }
    body.data_set_ids = [str(x) for x in (payload.get("dataSetIds") or [])]
    body.data_set_selection = [
        DataSetSelection(**s)
        for s in (payload.get("dataSetSelection") or [])
        if isinstance(s, dict)
    ]
    body.injection_entry_ids = [
        str(x) for x in (payload.get("injectionEntryIds") or [])]
    opts = {
        k: v for k, v in (payload.get("options") or {}).items()
        if k in RunOptions.model_fields
    }
    requested_step_to = (body.run_options.step_to
                         if body.run_options is not None else None)
    if requested_step_to is not None:
        opts["step_to"] = requested_step_to
    body.run_options = RunOptions(**opts) if opts else None
    body.scheme_id = scheme.scheme_id if scheme is not None else None
    body.scheme_name = scheme.name if scheme is not None else None


async def _post_adhoc_run(
    principal: Principal, db: AsyncSession, body: RunRequest,
) -> RunResponse:
    """P3 临时调用分支(设计 2026-11-02 §四):身份闸 → 配方字段禁令 →
    :func:`adhoc_run.prepare_adhoc`(结构 / 别名 / 地址 / 版本 / 组装 /
    干跑 convert)→ :func:`run_dispatcher.dispatch_target`(kind='adhoc',
    占位 id)。全部校验在建执行行之前,不通过即 4xx。
    """
    from ..services import adhoc_run, plate_client, run_prepare

    # §四.1 身份:只对入站个人模式(带 grant)开放 —— 平台模式(P3-D1)
    # 与 JWT(P3-D7,前端无入口,不开未设计的调用面)都 403。
    if not principal.inbound:
        raise HTTPException(
            status_code=403,
            detail={"code": "adhoc_inbound_only",
                    "message": "临时调用只对入站调用方(gic_ + grant)开放"})
    if principal.grant_id is None or principal.identity_mode != "personal":
        raise HTTPException(
            status_code=403,
            detail={"code": "adhoc_requires_grant",
                    "message": "临时调用要求个人模式:请携带用户签发给该"
                               "别名的 grant(X-Gimbal-Grant)"})
    # §三:除 steps / release / clientRef / callbackPath 外的配方字段一律拒
    offenders = adhoc_run.recipe_fields_present(body)
    if offenders:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "adhoc_field_not_allowed",
                "message": "临时调用不接受以下字段(没有数据集/注入/编排/"
                           "方案/runOptions 语义): " + "、".join(offenders),
                "fields": offenders,
            })
    run_id = run_dispatcher.new_run_id()   # 占位 id 先于派发用到
    try:
        payload = await adhoc_run.prepare_adhoc(db, body, run_id=run_id)
    except adhoc_run.AdhocRejected as e:
        raise HTTPException(
            status_code=e.status,
            detail={"code": e.code, "message": e.message, **e.extra}) from None
    except plate_client.PlateUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "plate_unavailable",
                    "message": f"临时调用派发前校验需要 plate: {e}"}) from None
    target = run_dispatcher.RunTarget(
        scenario_id=run_prepare.adhoc_placeholder_id(run_id),
        payload=payload, kind="adhoc")
    try:
        resp = await run_dispatcher.dispatch_target(
            db, principal.user.id, body, target, run_id=run_id,
            caller_alias=principal.caller_alias, grant_id=principal.grant_id,
            identity_mode=principal.identity_mode)
    except run_dispatcher.NotFound as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except run_dispatcher.Conflict as e:
        raise HTTPException(status_code=409, detail={"code": e.code, "message": e.message, **e.extra})
    from ..services import audit as audit_svc
    await audit_svc.record_inbound(db, principal, "inbound.run", detail={
        "fn": "adhoc",
        "endpoints": [str(dict(st).get("endpoint")) for st in body.steps],
        "execution": resp.execution_id, "run_id": resp.run_id,
        "client_ref": body.client_ref})
    return resp


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def post_run(
    principal: PrincipalIn,
    db: DbSession,
    body: RunRequest,
) -> RunResponse:
    user = principal.user
    if body.callback_path is not None \
            and not valid_callback_path(body.callback_path):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "callback_path_invalid",
                "message": "callbackPath 必须是以 / 开头的路径段(不含协议与主机)",
            })
    if principal.inbound:
        # M1:先拒「携带配方」(不依赖场景/方案,尽早失败)
        _reject_inbound_recipe(body)
    # P3 临时调用(设计 2026-11-02 §三):scenarioId 与 steps 二选一
    if (body.scenario_id is None) == (body.steps is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "run_target_ambiguous",
                "message": "scenarioId 与 steps 必须且只能提供一个",
            })
    if body.steps is not None:
        return await _post_adhoc_run(principal, db, body)
    # Access check (mirrors V1 executions create / composer ownership):
    # dispatching a run has real side effects (subprocesses hitting the
    # bound services), so it must not be open to every member —
    # only the scenario's owner (or an admin) may run it.
    try:
        scen = await scenario_store.get_row(db, body.scenario_id)
        if scen is None:
            # Same dict-detail (code/message) contract as every other
            # run-path 404 — via the shared NotFound translation below.
            raise run_dispatcher.NotFound(
                "scenario_not_found", f"scenario not found: {body.scenario_id}"
            )
        if principal.inbound:
            # M1:配方一律取服务端方案(方案由场景属主维护,可信来源)
            await _apply_scheme_recipe(db, scen, body)
        if principal.identity_mode == "platform":
            # M2(修复方案 §2.1,拍板 A):平台模式的场景范围 —— 公共
            # 场景,或别名属主自己的场景;他人私有场景 403(此前平台
            # 模式可跑任何人的私有场景)。团队共享别名(owner 为空)只
            # 能用公共场景。只看属主与可见性,不看分享引用(引用授权
            # 给人,不延伸到平台身份)。
            from ..models.service_alias import ServiceAlias
            from ..services.inbound_identity import platform_scope_ok
            alias = await db.get(ServiceAlias, principal.caller_alias)
            if not platform_scope_ok(
                    scen, alias.owner_user_id if alias is not None else None):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "platform_scope_denied",
                        "message": ("平台模式只能执行公共场景,或经由别名"
                                    "属主自己的场景;该场景不在允许范围"),
                    })
            # 平台模式(D6):无属主闸,凭证取 __platform__ 池 —— 前提是
            # 执行区间只读(is_scenario_read_only,与集成链同一实现)。
            # graph 编排本期限定 JWT/个人模式:多单元逐个过只读闸的
            # 覆盖面本链未接,先整体拒绝(fail-closed,§4.3;入站 graph
            # 通常已被 M1 的 422 先拒,此处是纵深防御)。
            if body.graph is not None:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "graph_not_supported_for_platform",
                        "message": "平台模式(入站无 grant)暂不支持编排执行,"
                                   "请使用持久化场景或携带 grant",
                    })
            from ..services import plate_client
            from ..services.integration_runner import is_scenario_read_only
            try:
                ok, offenders = await is_scenario_read_only(scen.payload)
            except plate_client.PlateUnavailableError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "plate_unavailable",
                        "message": "只读检查未通过: plate 不可达(平台模式"
                                   "执行需要 plate 契约元数据)",
                    }) from None
            if not ok:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "not_read_only",
                        "message": ("平台模式要求全部步骤为只读"
                                    f"(GET/HEAD/OPTIONS 或已标 query_safe): "
                                    f"{'、'.join(offenders)}"),
                    })
        else:
            # §8.2:ensure_owner → can_run_scenario(属主 ∨ admin ∨ 引用,
            # §7.6;public 不开执行 —— 公共资源跑需先 fork,不变量 7)。
            from ._ownership import can_run_scenario
            if not await can_run_scenario(
                    db, user, scenario_id=scen.scenario_id,
                    owner_id=scen.owner_id):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "not_owner",
                        "message": ("only the scenario's owner (or admin, or a "
                                    "share reference) can run this scenario"),
                    })
            # graph 链 unit 授权(必修缺口,《Suite成员层、引用分享与浏览镜头-
            # 设计方案》§8.2):unit 与 before/after 括号场景此前只在 worker 侧
            # 物化时查存在性、无归属检查——任何登录用户都能经编排跑他人
            # 私有场景。请求侧逐个过属主闸(与顶层同款 = 属主 ∨ admin,403
            # not_owner;不存在 → 404 不泄露)。rerun 不重放 graph(config 重放
            # 构造无 graph 字段),此处即唯一入口。
            if body.graph is not None:
                seen_unit_ids: set[str] = set()
                for unit in [
                    *body.graph.units,
                    *body.graph.before,
                    *body.graph.after,
                ]:
                    if unit.scenario_id in seen_unit_ids:
                        continue
                    seen_unit_ids.add(unit.scenario_id)
                    unit_scen = await scenario_store.get_row(db, unit.scenario_id)
                    if unit_scen is None:
                        raise run_dispatcher.NotFound(
                            "scenario_not_found",
                            f"scenario not found: {unit.scenario_id}",
                        )
                    if not await can_run_scenario(
                        db, user, scenario_id=unit_scen.scenario_id,
                        owner_id=unit_scen.owner_id):
                        raise HTTPException(
                            status_code=403,
                            detail={
                                "code": "not_owner",
                                "message": (
                                    "only the scenario's owner (or admin, or a "
                                    "share reference) can run graph unit: "
                                    f"{unit.scenario_id}"
                                ),
                            })
        resp = await run_dispatcher.dispatch_run(
            db,
            user_id=user.id,
            req=body,
            preloaded_scenario=scen,  # 已为归属检查加载,不再二次查询
            caller_alias=principal.caller_alias,
            grant_id=principal.grant_id,
            identity_mode=principal.identity_mode,
        )
    except run_dispatcher.NotFound as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except run_dispatcher.Conflict as e:
        raise HTTPException(status_code=409, detail={"code": e.code, "message": e.message, **e.extra})
    from ..services import audit as audit_svc
    await audit_svc.record_inbound(db, principal, "inbound.run", detail={
        "fn": "scenario", "scenario_id": scen.scenario_id,
        "execution": resp.execution_id, "run_id": resp.run_id,
        "client_ref": body.client_ref})
    return resp
