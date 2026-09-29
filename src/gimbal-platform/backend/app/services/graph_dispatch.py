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

from ..core.config import settings
from ..models.composer_scenario import ComposerScenario
from . import plate_client, scenario_store
from .carry_injection import build_carry_context
from .run_injection import compose_injection_scenario
from . import service_aliases
from . import carry_store
from .gimbal_launcher import launch
from .run_materialize import materialize_run_copy, referenced_services
from .scenario_store import steps_from_payload


async def resolve_graph_units(
    db: AsyncSession, units: list[dict], owner_id: int,
) -> list[dict]:
    """编排单元(ref)→ 物化后的 gimbal 场景 dict 列表。

    单元规格:{ref, scenarioId, dataSetIds?, injectionEntryIds?,
    serviceBindings?, nRuns?, repeat?, needs?, shared?, inputs?}。
    """
    resolved: list[dict] = []
    for u in units:
        scen = await scenario_store.get_row(db, u["scenarioId"])
        if scen is None:
            raise GraphDispatchError(
                f"unit {u['ref']!r}: scenario not found: {u['scenarioId']}")
        payload = dict(scen.payload or {})
        # 行值合入 + 注入条目(单场景链同款 compose,无数据集 = 基线)
        from .run_dispatcher import _compose_scenario  # 复用行合入
        composed = _compose_scenario(payload, {})
        entries = u.get("injectionEntryIds") or []
        if entries:
            # 注入条目 patch 在 payload.assertion_registry 里取;编排页
            # 单元粒度注入沿用同一通道
            registry = (composed.get("assertion_registry") or {}).get(
                "entries") or []
            for eid in entries:
                entry = next((e for e in registry if e.get("id") == eid), None)
                if entry is not None:
                    composed = compose_injection_scenario(composed, entry)
        resolved.append({
            "unit": u,
            "scenario_row": scen,
            "composed": composed,
        })
    return resolved


class GraphDispatchError(Exception):
    """编排物化失败(场景缺失/convert 拒绝);路由层 → 4xx。"""


async def materialize_graph(
    db: AsyncSession,
    owner_id: int,
    graph_req: dict,
) -> dict:
    """GraphRunRequest dict → gimbal SuiteGraph dict(不执行)。

    graph_req:{mode, units:[{ref,scenarioId,...}], before?, after?,
    parallel?, gates?, checks?, nRuns?}。
    """
    from .run_dispatcher import _resolve_exec_auths, _built_in_users

    mode = graph_req.get("mode") or "aggregate"
    if mode not in ("aggregate", "compose", "fanout", "chain"):
        raise GraphDispatchError(f"unknown mode: {mode!r}")

    all_units = [
        *graph_req.get("before", []),
        *graph_req["units"],
        *graph_req.get("after", []),
    ]
    resolved = await resolve_graph_units(db, all_units, owner_id)

    # 认证与绑定物化(graph 级一次;单元绑定合并到全域)
    auth_aliases: list[str] = sorted({
        alias
        for u in all_units
        for alias in (u.get("serviceBindings") or {}).values()
        if alias and isinstance(alias, str)
    })
    exec_auths = (await _resolve_exec_auths(db, owner_id, auth_aliases)
                  if auth_aliases else [])
    alias_urls: dict = {}
    try:
        alias_urls = await service_aliases.base_urls_for(
            db, _all_referenced_services(resolved))
    except Exception:  # noqa: BLE001
        alias_urls = {}

    unit_payloads: dict[str, dict] = {}
    for r in resolved:
        composed = r["composed"]
        # plate convert(gimbal 形态)
        convert = await plate_client.convert(composed)
        converted = (convert.get("converted") or {})
        bindings = r["unit"].get("serviceBindings") or {}
        merged_bindings = {**(graph_req.get("serviceBindings") or {}),
                           **bindings}
        materialized = materialize_run_copy(
            converted,
            service_bindings=merged_bindings,
            resolved_auths=exec_auths,
            built_in_users=_built_in_users(composed),
            # graph 不做 carry 注入;须显式 None —— 空 dict 会经
            # materialize 的 ``is not None`` 判定进 _apply_carry,在
            # step 引用了 service 时炸 AttributeError(dict 无
            # service_bindings 属性;对账基准扩充实测抓到)
            carry_context=None,
            alias_base_urls=alias_urls,
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
    return graph


def _all_referenced_services(resolved: list[dict]) -> list[str]:
    out: set[str] = set()
    for r in resolved:
        for st in steps_from_payload(r["composed"]):
            svc = (st.get("call") or {}).get("service")
            if svc:
                out.add(svc)
    return sorted(out)


async def execute_graph(
    db_factory, execution_id: int, run_dir: Path, graph: dict,
    *, on_event=None, on_log=None, chain: str = "legacy",
) -> dict:
    """物化好的 SuiteGraph → 落盘 case.json → 单 spawn 执行;返回
    LaunchResult(行状态由事件投影 —— 与 _fanout 的 P2-04 同语义)。

    C12/C13：``chain="server"`` 走执行器 server 实例（POST /runs +
    SSE 消费）；legacy 走 run launch 子进程（stdout jsonl）。
    """
    case_dir = run_dir / "case-graph"
    case_dir.mkdir(parents=True, exist_ok=True)
    case_path = case_dir / "case.json"
    case_path.write_text(_json_dumps(graph), encoding="utf-8")
    n_runs = 1    # graph 内单元已带 policy_kwargs;spawn 级乘法不叠
    if chain == "server":
        from .gimbal_server_session import ServerSession
        ss = ServerSession()
        await ss.start(engine_log_path=case_dir / "engine.log", cwd=run_dir)
        try:
            return await ss.run_case(
                case_path, n_runs=n_runs, on_event=on_event)
        finally:
            await ss.close()
    return await launch(
        case_path,
        report_dir=case_dir / "reports",
        cwd=case_dir,
        engine_log_path=case_dir / "engine.log",
        on_event=on_event,
        on_log=on_log,
        n_runs=n_runs,
    )


def _json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=1, default=str)
