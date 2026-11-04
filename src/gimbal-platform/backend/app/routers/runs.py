"""POST /api/runs — trigger a Scenario run (V3 composer).

Thin wrapper around :func:`app.services.run_dispatcher.dispatch_run`
(which creates the Execution row and spawns the per-(dataset × row)
fan-out: compose → Plate /convert → case 落盘 → ``gimbal run launch``
子进程执行).

认证(webhook v4 §3.1):``principal_or_user`` 分流 —— JWT 行为不变;
``Bearer gtk_…`` 访问令牌进个人(personal)/平台(platform)模式。
判定链:① 认证(deps)→ ② M1 不带配方 → ③ 方案物化 → ④ 场景前提
(个人 = can_run_scenario;平台 = 公共 + 只读闸 + 非临时调用)→
⑤ 令牌范围(别名集 ⊆ 范围别名 ∧ 凭证集 ⊆ 范围凭证,缺项分类)→
⑥ 追溯计算(resolvedServices / builtinAuths / outOfScope)→ 派发。

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
from ..services import access_token as at
from ..services import run_dispatcher, scenario_store
from ..services.access_token import Principal


router = APIRouter(prefix="/runs", tags=["runs"])


DbSession = Annotated[AsyncSession, Depends(get_db)]
PrincipalIn = Annotated[Principal, Depends(principal_or_user)]


# M1(修复方案 2026-11-01 §1):入站调用**只能选择平台上已有的配方,
# 不能携带配方** —— 服务地址/凭证别名/数据集/注入条目一律由服务端按
# 运行方案读取(方案由场景属主在平台维护,是可信来源)。否则
# serviceBindings.url 可以改写被测地址、把注入的凭证发到任意主机。
# v4 口径不变(§3.1 ②);graph 为 JWT 专属(D20)—— 令牌带 graph 由
# 本清单一并拒(422)。
_INBOUND_FORBIDDEN_FIELDS = (
    ("service_bindings", "serviceBindings"),
    ("data_set_ids", "dataSetIds"),
    ("data_set_selection", "dataSetSelection"),
    ("injection_entry_ids", "injectionEntryIds"),
    ("graph", "graph"),
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
                "message": ("令牌调用不能携带执行配方,以下字段由服务端按"
                            "运行方案读取(graph 为 JWT 专属): "
                            + "、".join(offenders)),
                "fields": offenders,
            })


async def _apply_scheme_recipe(
    db: AsyncSession, scen, body: RunRequest,
) -> None:
    """M1:按方案覆盖请求配方(令牌分支专用,见模块注释)。

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


async def _record_inbound_activity(
    db: AsyncSession, principal: Principal, resp: RunResponse,
    *, body: RunRequest, scen=None,
) -> None:
    """令牌触发写一条时间线事件(§7.3):actor = 令牌属主(个人令牌);
    平台令牌**不上个人轴**(D23 —— 平台身份的感知走审计面板与平台
    令牌详情「最近调用」)。JWT 调用 no-op(与 audit.record_inbound
    同口径)。best-effort,失败不阻断业务。"""
    if not principal.is_token or principal.token.kind == at.PLATFORM_KIND:
        return
    from ..services import activity as activity_svc
    detail: dict = {
        "fn": "adhoc" if body.steps is not None else "scenario",
        "execution_id": resp.execution_id, "run_id": resp.run_id,
        "scenario_id": scen.scenario_id if scen is not None else None,
        "scenario_name": scen.name if scen is not None else None,
        "client_ref": body.client_ref,
        "identity_mode": principal.identity_mode,
        "token_id": principal.token_id,
        "token_name": principal.token.name,
    }
    if body.steps is not None:
        # 临时调用:全量请求信息(与审计同源)
        detail["steps"] = body.steps
        detail["release"] = body.release
    await activity_svc.record(
        db, actor_id=principal.user.id, kind=activity_svc.KIND_INBOUND_RUN,
        resource_type="inbound", resource_id=str(principal.token_id),
        detail=detail)


def _deny_token_scope(missing: "list[at.ScopeMissing]") -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "code": at.ERR_RESOURCE_NOT_ALLOWED,
            "message": ("超出令牌授权范围:" + at._missing_summary(missing)
                        + ";" + at.missing_hint(missing)),
            "missing": [{"kind": m.kind, "name": m.name, "deleted": m.deleted}
                        for m in missing],
        })


def _scope_missing_detail(missing: "list[at.ScopeMissing]",
                          **extra) -> dict:
    """§7.2 ``inbound.denied`` 的范围拒绝 detail(拒绝原因与缺项;
    令牌只记 hint 由 record_inbound 资源列承担)。"""
    return {
        "reason": at.ERR_RESOURCE_NOT_ALLOWED,
        "missing": [{"kind": m.kind, "name": m.name, "deleted": m.deleted}
                    for m in missing],
        **extra,
    }


def _builtin_auths(scen) -> list[str]:
    """场景内置认证的用户名列表(§7.1:不含密码)。"""
    from ..services.run_prepare import built_in_users
    return sorted(str(k) for k in built_in_users(scen.payload))


async def _post_adhoc_run(
    principal: Principal, db: AsyncSession, body: RunRequest,
) -> RunResponse:
    """P3 临时调用分支:身份闸 → 配方字段禁令 → :func:`adhoc_run.
    prepare_adhoc` → :func:`run_dispatcher.dispatch_target`(kind='adhoc',
    占位 id)。全部校验在建执行行之前,不通过即 4xx。

    v4:临时调用仅**个人令牌**(§3.1 ④ / D20);平台令牌与 JWT 均 403
    ``adhoc_personal_token_only``。"""
    from ..services import adhoc_run, plate_client, run_prepare

    if not principal.is_token or principal.token.kind != at.PERSONAL_KIND:
        raise HTTPException(
            status_code=403,
            detail={"code": at.ERR_ADHOC_PERSONAL_ONLY,
                    "message": "临时调用只对个人访问令牌开放"})
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
    # ⑤ 令牌范围:别名集 = steps[].service;凭证集 = 别名表凭证默认
    used = await at.used_sets_for_adhoc(db, body.steps)
    missing = await at.check_scope(db, principal.token,
                                   principal.user.id, used)
    if missing:
        from ..services import audit as _audit
        await _audit.record_inbound(
            db, principal, "inbound.denied",
            detail=_scope_missing_detail(
                missing, fn="adhoc",
                endpoints=[str(dict(st).get("endpoint"))
                           for st in body.steps]))
        raise _deny_token_scope(missing)
    target = run_dispatcher.RunTarget(
        scenario_id=run_prepare.adhoc_placeholder_id(run_id),
        payload=payload, kind="adhoc")
    # §7.1 追溯:临时调用地址全部经别名(③层);无内置认证、无范围外目标
    from ..services import service_aliases as sa_svc
    alias_urls = await sa_svc.base_urls_for(db, used.aliases)
    trace = {
        "resolvedServices": {
            svc: {"url": alias_urls.get(svc), "source": "alias", "alias": svc}
            for svc in used.aliases},
        "builtinAuths": [],
        "token": {"id": principal.token.id, "name": principal.token.name,
                  "kind": principal.token.kind},
        "outOfScope": {"targets": [], "builtinAuths": [],
                       "strategyEntries": []},
    }
    try:
        resp = await run_dispatcher.dispatch_target(
            db, principal.user.id, body, target, run_id=run_id,
            token=principal.token, trace=trace)
    except run_dispatcher.NotFound as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except run_dispatcher.Conflict as e:
        raise HTTPException(status_code=409, detail={"code": e.code, "message": e.message, **e.extra})
    from ..services import audit as audit_svc
    await audit_svc.record_inbound(db, principal, "inbound.run", detail={
        "fn": "adhoc",
        # G4 增强:临时调用记**全量请求信息**(steps 原样 + 版本覆盖)
        # ——端点串只是索引,取证需要调用方到底发了什么。
        "steps": body.steps,
        "release": body.release,
        "endpoints": [str(dict(st).get("endpoint")) for st in body.steps],
        "execution": resp.execution_id, "run_id": resp.run_id,
        "client_ref": body.client_ref,
        "scope_aliases": used.aliases,
        "scope_auths": used.auths,
        # §7.2 resolvedServices 摘要(临时调用全走别名 ③层,§7.1)
        "resolvedServices": trace["resolvedServices"]})
    await _record_inbound_activity(db, principal, resp, body=body)
    return resp


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def post_run(
    principal: PrincipalIn,
    db: DbSession,
    body: RunRequest,
) -> RunResponse:
    user = principal.user
    if body.callback_path is not None \
            and not at.valid_callback_path(body.callback_path):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "callback_path_invalid",
                "message": "callbackPath 必须是以 / 开头的路径段(不含协议与主机)",
            })
    if principal.is_token:
        # M1:先拒「携带配方」(不依赖场景/方案,尽早失败;graph 一并拒,
        # D20:令牌请求带 graph 一律 422)
        _reject_inbound_recipe(body)
    # P3 临时调用:scenarioId 与 steps 二选一
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
            raise run_dispatcher.NotFound(
                "scenario_not_found", f"scenario not found: {body.scenario_id}"
            )
        used: "at.ScopeSets | None" = None
        if principal.is_token:
            # M1:配方一律取服务端方案(方案由场景属主维护,可信来源)
            await _apply_scheme_recipe(db, scen, body)
        if principal.is_token and principal.token.kind == at.PLATFORM_KIND:
            # ④ 平台模式场景前提(D9):只认公共场景(令牌与 JWT 同一
            # 判定,v3 的「别名属主自己的场景」豁免随承载别名一起退役);
            # 执行区间只读(is_scenario_read_only);临时调用非个人令牌
            # 已在上方 403。graph 已被 M1 的 422 先拒。
            if (getattr(scen, "visibility", None) or "private") != "public":
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "platform_scope_denied",
                        "message": "平台模式只能执行公共场景;该场景不在允许范围",
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
            # ④ 个人模式(JWT 或个人令牌):ensure_owner → can_run_scenario
            # (属主 ∨ admin ∨ 引用,§7.6;public 不开执行 —— 公共资源跑需
            # 先 fork,不变量 7)。
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
            if body.graph is not None:
                # graph 链 unit 授权(§8.2):请求侧逐个过属主闸。rerun
                # 不重放 graph,此处即唯一入口(令牌路径已被 M1 拒)。
                seen_unit_ids: set[str] = set()
                for unit in [
                    *body.graph.units,
                    *body.graph.before,
                    *body.graph.after,
                ]:
                    if unit.scenario_id in seen_unit_ids:
                        continue
                    seen_unit_ids.add(unit.scenario_id)
                    unit_scen = await scenario_store.get_row(
                        db, unit.scenario_id)
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
        if principal.is_token:
            # ⑤ 令牌范围:别名集 ⊆ 范围别名 ∧ 凭证集 ⊆ 范围凭证
            # (场景执行面:方案绑定 + 场景定义;§3.2)
            from ..services.scenario_store import definition_from_payload
            extra_nodes = _injection_nodes(scen, body)
            definition = definition_from_payload(scen.payload)
            used = await at.used_sets_for_definition(
                db, definition,
                {k: {"authAlias": b.auth_alias, "url": b.url}
                 for k, b in (body.service_bindings or {}).items()},
                extra_scan_nodes=extra_nodes)
            missing = await at.check_scope(
                db, principal.token, user.id, used)
            if missing:
                from ..services import audit as _audit
                await _audit.record_inbound(
                    db, principal, "inbound.denied",
                    detail=_scope_missing_detail(
                        missing, fn="scenario",
                        scenario_id=scen.scenario_id,
                        scheme_id=body.scheme_id))
                raise _deny_token_scope(missing)
        # ⑥ 追溯计算(§7.1):resolvedServices / builtinAuths / outOfScope
        # —— JWT 执行同样写前两者;令牌另带 token 快照
        trace = await _build_trace(db, scen, body, principal, used)
        resp = await run_dispatcher.dispatch_run(
            db,
            user_id=user.id,
            req=body,
            preloaded_scenario=scen,  # 已为归属检查加载,不再二次查询
            token=principal.token if principal.is_token else None,
            trace=trace,
        )
    except run_dispatcher.NotFound as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except run_dispatcher.Conflict as e:
        raise HTTPException(status_code=409, detail={"code": e.code, "message": e.message, **e.extra})
    from ..services import audit as audit_svc
    if principal.is_token:
        # §7.2 inbound.run:资源列 = access_token/令牌 id(最近调用面);
        # detail 带范围与目标摘要 + outOfScope 标记面
        await audit_svc.record_inbound(db, principal, "inbound.run", detail={
            "fn": "scenario", "scenario_id": scen.scenario_id,
            "scenario_name": scen.name,
            "execution": resp.execution_id, "run_id": resp.run_id,
            "client_ref": body.client_ref,
            "scheme_id": body.scheme_id,
            "scope_aliases": used.aliases if used else [],
            "scope_auths": used.auths if used else [],
            # §7.2 resolvedServices 摘要(与 config_json §7.1 同源)
            "resolvedServices": trace["resolvedServices"],
            "outOfScope": used.out_of_scope if used else {},
        })
    await _record_inbound_activity(db, principal, resp, body=body,
                                   scen=scen)
    return resp


def _injection_nodes(scen, body: RunRequest) -> "list | None":
    """§3.2 注入条目物化:选中注入条目的值面并入凭证扫描源。"""
    ids = set(body.injection_entry_ids or [])
    if not ids:
        return None
    registry = (scen.payload or {}).get("assertion_registry") or {}
    entries = registry.get("entries") or []
    return [e for e in entries
            if isinstance(e, dict) and e.get("id") in ids]


async def _resolved_services(db, scen, body: RunRequest) -> dict:
    """§7.1 ``resolvedServices``:每个被引用服务的 {url, source, alias?}
    (三层解析只读版,与物化同一裁决)。"""
    from ..services import service_aliases as sa_svc
    from ..services.run_materialize import (
        referenced_services, resolve_service_sources,
    )
    from ..services.scenario_store import definition_from_payload

    definition = definition_from_payload(scen.payload) if scen else {}
    steps = definition.get("steps") or []
    base_urls = await sa_svc.base_urls_for(
        db, referenced_services(steps))
    return resolve_service_sources(
        steps, declared=(definition.get("config") or {}).get("services"),
        bindings={k: {"url": b.url}
                  for k, b in (body.service_bindings or {}).items()},
        alias_base_urls=base_urls)


async def _build_trace(
    db, scen, body: RunRequest, principal: Principal,
    used: "at.ScopeSets | None",
) -> dict:
    """§7.1 执行 config_json 追溯块;dispatch 原样并入 config_json。"""
    trace: dict = {
        "resolvedServices": await _resolved_services(db, scen, body),
        "builtinAuths": _builtin_auths(scen) if scen is not None else [],
    }
    if principal.is_token:
        trace["token"] = {"id": principal.token.id,
                          "name": principal.token.name,
                          "kind": principal.token.kind}
        trace["outOfScope"] = (used.out_of_scope if used
                               else {"targets": [], "builtinAuths": [],
                                     "strategyEntries": []})
    return trace
