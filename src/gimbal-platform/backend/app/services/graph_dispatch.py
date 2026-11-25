"""graph_dispatch.py — C5(P3-05):suite 编排执行链(平台 → 执行器 graph)。

编排页产出 ``GraphRunRequest``(单元 = 平台场景 ref + 数据集/注入/绑定 +
乘法),本服务把它物化成 gimbal ``SuiteGraph``:

  1. 逐单元加载平台场景 → compose(行值合入 vars + 断言条目 patch);
  2. 逐场景经 plate ``/convert`` 得 gimbal 形态(call 步骤、剥平台视图);
  3. ``materialize_run_copy`` 物化 run 副本(users 合并 / services 物化
     /carry 注入 —— 与单场景链同语);
  4. 组装 ``SuiteGraph``(mode/before/after/needs/shared/repeat/
     policy_kwargs/parallel/gates/checks)+ N4 乘法参数;
  5. 落盘 case.json 后 ``gimbal run launch --n-runs/--parallel`` 单
     spawn 执行(乘法/并发全部在执行器;事件流经 _EventIngester 入库,
     台账按单元投影 —— 与 P2 链共用)。

判定门(gates)/横切断言(checks)随 graph 下发,由引擎 N1 消费。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from ..core.config import settings
from ..core import db as db_module
from ..models.composer_scenario import ComposerScenario
from . import plate_client, run_prepare, scenario_store
from .run_injection import compose_injection_scenario
from . import service_aliases
from . import carry_store
from .run_materialize import materialize_run_copy, referenced_services


async def resolve_graph_units(
    db: AsyncSession, units: list[dict], owner_id: int,
) -> list[dict]:
    """编排单元(ref)→ 物化后的 gimbal 场景 dict 列表。

    单元规格:{ref, scenarioId, schemeId?, row?, dataSetIds?,
    injectionEntryIds?, serviceBindings?, nRuns?, repeat?, needs?,
    shared?, inputs?, map?}。

    重构方案约束 5(单行内联):``schemeId``(空 = 默认方案)+ ``row``
    {datasetId, rowIndex}(空 = 裸基线)选定该单元唯一运行的一行;
    方案的服务绑定随行合入(单元级覆盖同名);row 为空 =
    ``compose_scenario(payload, {})`` 裸基线(run_prepare)。
    """
    from .run_prepare import compose_scenario, find_dataset_by_id
    from . import scheme_store

    resolved: list[dict] = []
    for u in units:
        scen = await scenario_store.get_row(db, u["scenarioId"])
        if scen is None:
            raise GraphDispatchError(
                f"unit {u['ref']!r}: scenario not found: {u['scenarioId']}")
        payload = dict(scen.payload or {})

        # ── 约束 5:方案 + 单行选择 ──────────────────────────────
        from .run_params import RAW_SCHEME_ID

        scheme: dict | None = None
        scheme_id = u.get("schemeId")
        row_spec = u.get("row")
        if scheme_id != RAW_SCHEME_ID:
            schemes = await scheme_store.list_schemes(db, u["scenarioId"])
            if scheme_id is not None:
                scheme = next(
                    (s for s in schemes if s.get("schemeId") == scheme_id),
                    None)
                if scheme is None:
                    raise GraphDispatchError(
                        f"unit {u['ref']!r}: scheme not found: {scheme_id}")
            else:
                scheme = next(
                    (s for s in schemes if s.get("isDefault")), None)
        row_dict: dict = {}
        if row_spec:
            ds_id = row_spec.get("datasetId")
            ri = int(row_spec.get("rowIndex", 0))
            ds = await find_dataset_by_id(db, ds_id)
            if ds is None or ds.scenario_id != u["scenarioId"]:
                raise GraphDispatchError(
                    f"unit {u['ref']!r}: dataset not found: {ds_id}")
            rows = list(ds.rows or [])
            if ri < 0 or ri >= len(rows):
                raise GraphDispatchError(
                    f"unit {u['ref']!r}: rowIndex {ri} out of range for "
                    f"{ds_id} (0..{len(rows) - 1})")
            row_dict = rows[ri] or {}
            from .run_prepare import row_binding_refs
            if row_binding_refs(row_dict):
                # M2b Q3:套件编排首版不支持行账号列(凭证全图解析一次)
                raise GraphDispatchError(
                    f"unit {u['ref']!r}: dataset_binding_unsupported —— "
                    "suite 编排暂不支持数据集账号列(@slot.<槽>)")
        if row_dict and scenario_store.is_foreign_viewer(
                owner_id, scen.owner_id):
            # authz W6:跑他人场景(引用/suite 成员)—— 数据集敏感列剥
            # (原件不动;内置凭证由 materialize 处属主规则当空)
            row_dict = scenario_store.strip_sensitive_columns([row_dict])[0]
        composed = compose_scenario(payload, row_dict)

        entries = u.get("injectionEntryIds") or []
        if entries:
            # 注入条目 patch 在 payload.assertion_registry 里取;编排页
            # 单元粒度注入沿用同一通道(重构方案:条目 id 来自 mode_config)
            registry = (composed.get("assertion_registry") or {}).get(
                "entries") or []
            for eid in entries:
                # isinstance 守卫(I-01 存量兜底):非对象条目(junk)在此
                # 会 e.get AttributeError → 500 掀掉整个编排物化。写侧闸
                # (validate_registry_shape)只管新写入;存量行由本过滤
                # 跳过(run_dispatcher 选中段同款)。
                entry = next(
                    (e for e in registry
                     if isinstance(e, dict) and e.get("id") == eid), None)
                if entry is not None:
                    composed = compose_injection_scenario(composed, entry)
        # 账户组合垫底(v4 §3.2 Suite 图面):只取该单元所选方案的组合,
        # raw 不取;图/单元级覆盖自然在上。引用服务 fail-closed 闸在
        # 下方 validate 循环,派发面幂等重垫。
        from . import account_combo as _ac
        combo = await _ac.scheme_combo(db, scheme)
        _combo_b = _ac.pad_bindings({}, combo)
        unit = u
        _scheme_b = (scheme.get("serviceBindings")
                     if scheme and scheme.get("serviceBindings") else None)
        if _scheme_b is not None or _combo_b:
            # 方案的服务绑定随行合入(单元级覆盖同名;存量形态剥离退役字段)
            from ..schemas.scenario_composer import scrub_retired_bindings
            unit = {**u, "serviceBindings": {
                **_combo_b,
                **scrub_retired_bindings(_scheme_b or {}),
                **(u.get("serviceBindings") or {})}}
        resolved.append({
            "unit": unit,
            "scenario_row": scen,
            "combo": combo,
            "composed": composed,
            # 方案不携带环境链位(§8.2):环境解析走标签链单源
        })
    return resolved


def unit_merged_bindings(graph_req: dict, unit: dict) -> dict[str, dict]:
    """单元生效服务绑定 = 图级 ∪ 方案级(resolve_graph_units 已随行合入
    unit)∪ 单元级(后者覆盖同名)—— 凭证清单(run_prepare.graph_auth_
    aliases)与物化(materialize_run_copy)共用同一份,清单/注入面不漂移。
    """
    return {**(graph_req.get("serviceBindings") or {}),
            **(unit.get("serviceBindings") or {})}


async def missing_auth_aliases(
    db: AsyncSession, graph_req: dict, owner_id: int, *,
    cred_project_id: int | None = None,
) -> list[str]:
    """编排的缺槽清单(派发 fail-fast 用):凭证清单与 materialize_graph
    同源(``resolve_graph_units`` → ``graph_auth_aliases`` 逐单元并集),
    再对取用池(``cred_project_id`` 非空 = 项目池,否则发起人个人池)求
    差集。空清单 = 全部可取用。"""
    all_units = [*graph_req.get("before", []), *graph_req["units"],
                 *graph_req.get("after", [])]
    resolved = await resolve_graph_units(db, all_units, owner_id)
    aliases = await run_prepare.graph_auth_aliases(
        db_module.SessionLocal,
        [(r["composed"], unit_merged_bindings(graph_req, r["unit"]))
         for r in resolved])
    if not aliases:
        return [], []
    # §8.3:取用不校验标签 —— 无环境位(取用解析按池资格,不按环境)
    # D3:带回 (missing, ambiguous) 分类,消费方按
    # 类分道报错(歧义 ≠ 未登记)。missing/ambiguous 恒为请求槽位
    # 子集,直接回传。
    _picked, missing, ambiguous = await run_prepare.pick_bindings_full(
        db, owner_id, aliases, cred_project_id=cred_project_id)
    return sorted(missing), sorted(ambiguous)


class GraphDispatchError(Exception):
    """编排物化失败(场景缺失/convert 拒绝);路由层 → 4xx。"""


async def materialize_graph(
    db: AsyncSession,
    owner_id: int,
    graph_req: dict,
    *,
    full: bool = False,
    env: "Any" = None,
    cred_project_id: int | None = None,
) -> dict:
    """GraphRunRequest dict → gimbal SuiteGraph dict(不执行)。

    ``cred_project_id``(S8 收口):非空 = 本次编排选用项目凭证 —— 全图
    凭证从该项目的项目凭证池取用(缺省 = 发起人个人池)。

    graph_req:{mode, units:[{ref,scenarioId,...}], before?, after?,
    parallel?, gates?, checks?, nRuns?}。

    ``full=True`` 返回台账 bundle:
    ``{graph, m2_info, meta_plate, endpoints_used, unanchored_services}``
    —— 版本模型三件套(plate_pins/baseline_*/m2_hash)对 suite 执行
    与单场景同口径。
    """

    mode = graph_req.get("mode") or "aggregate"
    if mode not in ("aggregate", "compose", "fanout", "chain"):
        raise GraphDispatchError(f"unknown mode: {mode!r}")

    all_units = [
        *graph_req.get("before", []),
        *graph_req["units"],
        *graph_req.get("after", []),
    ]
    resolved = await resolve_graph_units(db, all_units, owner_id)

    # RS3 §6.3/R25:同一 Suite 内同一系统版本线必须一致,执行统一到
    # 可用集合交集的最新修订;不一致/无交集 → 拒绝(错误码随
    # GraphDispatchError 面 4xx)。plate 不可用时跳过检查(resolve 内
    # 部已按成员降级,与单场景执行同口径)。
    # r["composed"] 是 compose_scenario 的产物 —— 已解包的 definition
    # 本体,不是容器;check_and_resolve_suite_versions 按容器形状读
    # definition.meta,调用侧须包一层 {"definition": composed}。
    from .suite_version import (
        check_and_resolve_suite_versions,)
    suite_pins: dict[str, str] = {}
    if any(((r["composed"].get("meta") or {}).get("plate"))
           for r in resolved):
        # check_and_resolve 按容器形状读 definition.meta —— 包一层
        try:
            suite_pins = await check_and_resolve_suite_versions(
                [{"definition": r["composed"]} for r in resolved])
        except Exception as exc:  # plate 不可达 → 与单场景一致地失败
            from .plate_client import PlateUnavailableError
            if isinstance(exc, PlateUnavailableError):
                raise
            raise GraphDispatchError(str(exc)) from exc
        for r in resolved:
            meta_plate = (r["composed"].get("meta") or {}).get("plate") or {}
            for sys_, eff in suite_pins.items():
                if sys_ in meta_plate:
                    meta_plate[sys_] = eff

    # 认证与绑定物化(graph 级一次):凭证清单与单场景链/预检
    # 同源 —— run_prepare.graph_auth_aliases **逐单元**走
    # exec_auth_aliases(模板扫描 ${auth.*} ∪ 步骤服务条目(图级
    # +单元+方案合并后的绑定选别名即换槽))再并集。逐单元而非按服务
    # 压平:两个单元给同一服务选不同别名时压平会后写覆盖先写。
    # 选的别名须存在且同基础服务。
    for r in resolved:
        # 账户组合引用服务 fail-closed(§6.3):只校验最终仍由组合供号的
        # 服务;图级/单元级覆盖不连坐,组合行缺失仍无条件拒绝。
        from . import account_combo as _ac
        try:
            await _ac.referenced_combo_gate(
                db, r["combo"],
                referenced_services((r["composed"] or {}).get("steps") or []),
                unit_merged_bindings(graph_req, r["unit"]))
        except _ac.ComboIdentityMissing as e:
            raise GraphDispatchError(
                f"identity_combo_missing: 单元 {r['unit'].get('ref')}: "
                f"{e.message} ({e.detail()})") from None
        try:
            await service_aliases.validate_binding_aliases(
                db, unit_merged_bindings(graph_req, r["unit"]))
        except service_aliases.BindingAliasInvalid as e:
            raise GraphDispatchError(
                f"{e.code}: 单元 {r['unit'].get('ref')}: {e.message}") from None
    auth_aliases = await run_prepare.graph_auth_aliases(
        db_module.SessionLocal,
        [(r["composed"], unit_merged_bindings(graph_req, r["unit"]))
         for r in resolved])
    # §8.2 标签解析逐单元:每单元按**自身
    # 有效身份集合**解析标签(身份 > 该单元场景项目默认 > 平台默认)。
    # 重放快照(``env`` 非空)仍整图
    # 生效 —— 快照就是当次执行的事实。混拼在单元内抛 EnvMixed →
    # GraphDispatchError(派发前拒);查表失败该单元地址降级空表。
    from .env_chain import EnvChoice, EnvMixed, resolve_execution_tag
    from .service_aliases import exec_auth_aliases_of_definition
    unit_urls: dict[str, dict] = {}
    unit_envs: dict[str, int | None] = {}
    for r in resolved:
        ref = r["unit"]["ref"]
        try:
            if env is not None and env.env_id is not None:
                ue: EnvChoice = env          # 重放:快照整图生效
            else:
                _unit_aliases = await exec_auth_aliases_of_definition(
                    db, r["composed"], unit_merged_bindings(graph_req, r["unit"]))
                ue = await resolve_execution_tag(
                    db, identity_names=_unit_aliases,
                    project_id=r["scenario_row"].project_id)
            unit_envs[ref] = ue.env_id
            unit_urls[ref] = await service_aliases.base_urls_for(
                db, _all_referenced_services([r]), env=ue)
        except EnvMixed as e:
            raise GraphDispatchError(
                f"单元 {ref} {e}") from None
        except Exception:  # noqa: BLE001 — 降级必须可见(与 prepare_exec
            # 同位置 warning 口径对齐)
            logger.opt(exception=True).warning(
                "graph_dispatch: 单元 {} 标签/地址解析失败 → "
                "env=None + 空地址表(该单元执行将缺地址)", ref)
            unit_envs[ref] = None
            unit_urls[ref] = {}
    # §8.3:取用不校验标签 —— 无环境位(取用解析按池资格,不按环境)
    exec_auths = (await run_prepare.resolve_exec_auths(
        db_module.SessionLocal, owner_id, auth_aliases,
        cred_project_id=cred_project_id)
        if auth_aliases else [])

    # carry **按单元**构建(carry 上下文按步骤下标索引,不能跨
    # 单元共用);单单元失败降 None 不阻塞。
    # 逐单元 carry 作用域(单元场景项目;私有区单元 → 执行人个人层)
    # §8.9 实例档:逐单元执行标签(env_mixed 已派发前拦,单值)下传
    # 作实例键坐标;绑定选别名 → carry 别名键随之切换
    carry_ctxs = await run_prepare.unit_carry_contexts(
        db_module.SessionLocal, [r["composed"] for r in resolved],
        [{"project_id": r["scenario_row"].project_id,
          "user_id": (owner_id if r["scenario_row"].project_id is None
                      else None),
          "env_id": unit_envs.get(r["unit"]["ref"]),
          "bindings": unit_merged_bindings(graph_req, r["unit"])}
         for r in resolved])

    unit_payloads: dict[str, dict] = {}
    m2_info: dict | None = None
    for i, r in enumerate(resolved):
        composed = r["composed"]
        # plate convert(gimbal 形态)
        convert = await plate_client.convert(composed)
        # M2 §5.1:/convert 响应附带构建身份(全部单元同源,取首个)
        if m2_info is None and convert.get("m2"):
            m2_info = convert["m2"]
        converted = (convert.get("converted") or {})
        # 单元生效绑定(与凭证清单同一份,见 unit_merged_bindings)
        merged_bindings = unit_merged_bindings(graph_req, r["unit"])
        materialized = materialize_run_copy(
            converted,
            resolved_auths=exec_auths,
            # authz 主规则:executor(dispatch 的 owner_id)≠ 单元
            # 属主 ⇒ 内置 users 当空(引用执行不带走作者凭证)。
            # 源取落库容器 payload(与其余执行链同源)—— composed 是
            # 合成后的场景形状,definition_from_payload 解不出 users
            built_in_users=run_prepare.built_in_users(
                r["scenario_row"].payload, executor_id=owner_id,
                scenario_owner_id=r["scenario_row"].owner_id,
                project_id=r["scenario_row"].project_id),
            carry_context=carry_ctxs[i],
            alias_base_urls=unit_urls.get(r["unit"]["ref"], {}),
        )
        unit_payloads[r["unit"]["ref"]] = materialized

    def _decl(u: dict) -> dict:
        d: dict[str, Any] = {
            "ref": u["ref"],
            "scenario": unit_payloads[u["ref"]],
        }
        if u.get("needs"):
            d["needs"] = u["needs"]
        if u.get("shared"):
            d["shared"] = u["shared"]
        if u.get("inputs"):
            d["inputs"] = u["inputs"]
        if u.get("map"):
            # 连线改名(重构方案第 6 处):_decl 手工挑键,须显式写出
            # 才能透到执行器 UnitDecl.map
            d["map"] = u["map"]
        if u.get("repeat"):
            d["repeat"] = u["repeat"]
        policy_kwargs: dict = {}
        if u.get("nRuns") and u["nRuns"] > 1:
            policy_kwargs["n_runs"] = u["nRuns"]
        if policy_kwargs:
            d["policy_kwargs"] = policy_kwargs
        return d

    graph: dict[str, Any] = {
        "kind": "graph",
        "mode": mode,
        "units": [_decl(u) for u in graph_req["units"]],
    }
    if graph_req.get("before"):
        graph["before"] = [_decl(u) for u in graph_req["before"]]
    if graph_req.get("after"):
        graph["after"] = [_decl(u) for u in graph_req["after"]]
    policy: dict = {}
    parallel = graph_req.get("parallel") or 1
    if parallel and parallel > 1:
        policy["parallel"] = parallel
    if graph_req.get("nRuns") and graph_req["nRuns"] > 1:
        # graph 级 nRuns = 逐单元同乘(N4 语义)
        for d in graph["units"]:
            d.setdefault("policy_kwargs", {}).setdefault(
                "n_runs", graph_req["nRuns"])
    if policy:
        graph["policy"] = policy
    if graph_req.get("gates"):
        graph["gates"] = graph_req["gates"]
    if graph_req.get("checks"):
        graph["checks"] = graph_req["checks"]
    # 控制透传(重构方案第 2 处):materialize 是手工挑键组装,control
    # 须显式写进产物 —— 只落 only / to_node(执行器 Control 键为
    # snake_case);fromNode 刻意不透传,错键在拼装侧直接拒绝
    ctrl = graph_req.get("control") or {}
    bad = [k for k in ctrl if k not in ("only", "toNode")]
    if bad:
        raise GraphDispatchError(
            f"control 不支持的字段: {bad}(不透传 fromNode)")
    only = [x for x in (ctrl.get("only") or []) if x]
    to_node = ctrl.get("toNode")
    if only or to_node:
        graph["control"] = {}
        if only:
            graph["control"]["only"] = only
        if to_node:
            graph["control"]["to_node"] = to_node
    if not full:
        return graph
    # 台账输入(与单场景 dispatcher 同口径):成员声明的合并 meta.plate
    # (suite_pins 改写后即生效修订;working 系统保持 working → 判定
    # block=working)+ 锚定接口集 + 无锚服务键集。
    meta_plate: dict[str, str] = {}
    endpoints_used: dict[str, set[str]] = {}
    unanchored_services: list[str] = []
    for r in resolved:
        defn = r["composed"]          # definition 本体(见上方勘误注)
        meta_plate.update((defn.get("meta") or {}).get("plate") or {})
        for step in (defn.get("steps") or []):
            if not isinstance(step, dict):
                continue
            ep_id = step.get("endpoint")
            if ep_id:
                endpoints_used.setdefault(
                    str(ep_id).split(".")[0], set()).add(str(ep_id))
            else:
                call = step.get("call")
                svc = call.get("service") if isinstance(call, dict) else None
                if isinstance(svc, str) and svc:
                    unanchored_services.append(svc)
    return {
        "graph": graph,
        "m2_info": m2_info,
        "meta_plate": meta_plate,
        "endpoints_used": endpoints_used,
        "unanchored_services": unanchored_services,
    }


def _all_referenced_services(resolved: list[dict]) -> list[str]:
    # r["composed"] 是 compose_scenario 产物 = 已解包的 definition 本体,
    # 直接读 steps,勿再过 definition_from_payload(按容器调恒得 [])
    out: set[str] = set()
    for r in resolved:
        steps = (r["composed"] or {}).get("steps") or []
        for st in (x for x in steps if isinstance(x, dict)):
            svc = (st.get("call") or {}).get("service")
            if svc:
                out.add(svc)
    return sorted(out)


async def execute_graph(
    db_factory, execution_id: int, run_dir: Path, graph: dict,
    *, on_event=None, on_log=None, log_counters: dict | None = None,
    m2_info: dict | None = None,
    on_session=None,
) -> dict:
    """物化好的 SuiteGraph → 落盘 case.json → 执行器 server 实例单跑;
    返回 LaunchResult(行状态由事件投影 —— 与 _fanout 同语义)。

    执行器 server 实例(POST /runs + SSE 消费)。``on_session``
    (graph 单元级取消):启动后把 ServerSession 交给调用方,供其在
    取消位置位时下发 ``cancel(scope="unit")``。
    """
    case_dir = run_dir / "case-graph"
    case_dir.mkdir(parents=True, exist_ok=True)
    case_path = case_dir / "case.json"
    case_path.write_text(_json_dumps(graph), encoding="utf-8")
    n_runs = 1    # graph 内单元已带 policy_kwargs;spawn 级乘法不叠
    from .gimbal_server_session import ServerSession
    ss = ServerSession()
    # 日志入库接线(与 cases 链同面):on_log/log_counters 下传后,
    # graph 执行的引擎日志随 execution_events 入库(engine.log 文件
    # 照落)。顺序安全:ss.close() 在本函数 finally 收口
    # (泵排空后才返回),调用方 _fanout_graph 随后 finalize。
    await ss.start(engine_log_path=case_dir / "engine.log", cwd=run_dir,
                   on_log=on_log, log_counters=log_counters)
    if on_session is not None:
        try:
            on_session(ss)
        except Exception:  # noqa: BLE001
            pass
    try:
        return await ss.run_case(
            case_path, n_runs=n_runs, on_event=on_event,
            m2_info=m2_info)
    finally:
        await ss.close()


def _json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=1, default=str)
