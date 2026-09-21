"""服务画像聚合器(服务画像方案 §5.3)— P1:热力网格半边(线索板半边随后续切片)。

数据四路,全部来自既有资产(方案 §5.1;P1 零外部依赖):

* 瓦片清单 — plate 轻量列表(EndpointView 自带 method/path/service,
  ``gimbal_plate/http/views.py:142``),网格不需要逐端点打 /full;
* 槽② 用例覆盖 — 倒排索引 distinct scenario(**含锚点行**:零字段
  锚点步同样算覆盖,2026-09-20 硬化);
* 槽③ 最近执行 — 引用场景的 executions,平台视角(**不做 owner 过滤**,
  与执行历史页的个人视图口径不同,方案 §2.4);终态规则「failed > 0 →
  failed」来自 dispatcher(`run_dispatcher.py:1157`),done 即全行通过;
  running/queued 按上一次完成态显示,canceled 同灰;
* 槽④ 适配告警 — ``adaptation_batches.endpoint_id`` 名下存在
  ``status ∈ {pending, conflict}`` 的 op(conflict 同样未落定,计入)。

fail-soft(§2.4):plate 不可达只影响瓦片清单 → 空清单 + plateReachable
=False,覆盖/执行/告警三类信号照算(基于 refs 面),页面给降级横幅
而非白屏;信号沿用 ``carry_drift`` 的既有先例。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.timeutil import iso_naive_utc
from ..models.adaptation_batch import AdaptationBatch
from ..models.adaptation_op import AdaptationOp
from ..models.board_card import BoardCard
from ..models.composer_scenario import ComposerScenario
from ..models.execution import Execution
from ..models.scenario_endpoint_ref import ScenarioEndpointRef
from .adaptation_service import _plate_list_endpoints
from .plate_client import PlateUnavailableError, get_endpoint_full

# 槽③的终态映射:done=全过(pass)/ failed=有失败行(fail);
# canceled → None(灰,§2.4「canceled 同灰」);running/queued 非终态,跳过。
_VERDICT = {"done": "pass", "failed": "fail"}

# P1 的象限就绪态(方案 §3.1/§5.5):测试象限完整,其余占位;
# P2 reference dim / P3 table+topology dim 落地后逐个翻 'ok'。
_QUADRANTS_P1 = {
    "requirement": "unavailable", "data": "unavailable",
    "topology": "unavailable", "test": "ok",
}


async def _latest_terminals(
    db: AsyncSession, scenario_ids: list[str]
) -> dict[str, Execution]:
    """每场景「最近一次完成态」的 Execution 行(平台视角,跨 owner)。

    按时间倒序扫,首个终态胜出;running/queued 跳过(§2.4「进行中按
    上一次完成态」);只有非终态 → 该场景无条目(= 灰)。grid 的槽③与
    board 的执行节点/trails 共用这一个口径。
    """
    if not scenario_ids:
        return {}
    rows = (await db.execute(
        select(Execution)
        .where(Execution.scenario_id.in_(scenario_ids))
        .order_by(Execution.created_at.desc(), Execution.id.desc())
    )).scalars().all()
    latest: dict[str, Execution] = {}
    for ex in rows:
        if ex.scenario_id in latest or ex.status in ("running", "queued"):
            continue
        latest[ex.scenario_id] = ex
    return latest


async def grid(db: AsyncSession, service: str) -> dict[str, Any]:
    """服务级热力网格(方案 §2):一屏全接口 + 四格信号 + 统计条。"""
    # ── 瓦片清单:plate 轻量列表(不可达 → 降级,不抛)─────────────
    reachable = True
    try:
        items = await _plate_list_endpoints()
    except PlateUnavailableError:
        items, reachable = [], False
    svc_items = [it for it in items if it.get("service") == service and it.get("id")]
    endpoint_ids = [str(it["id"]) for it in svc_items]

    # ── 槽②覆盖:refs distinct (endpoint, scenario),锚点行天然在内 ──
    scenarios_by_ep: dict[str, set[str]] = {}
    if endpoint_ids:
        rows = (await db.execute(
            select(ScenarioEndpointRef.endpoint_id, ScenarioEndpointRef.scenario_id)
            .where(ScenarioEndpointRef.endpoint_id.in_(endpoint_ids))
            .distinct()
        )).all()
        for ep_id, sid in rows:
            scenarios_by_ep.setdefault(ep_id, set()).add(sid)

    # ── 槽③最近执行:引用场景的最新完成态(平台视角,跨 owner)─────
    all_scenarios = sorted({s for ss in scenarios_by_ep.values() for s in ss})
    latest = {
        sid: (_VERDICT.get(ex.status), ex.finished_at or ex.created_at)
        for sid, ex in (await _latest_terminals(db, all_scenarios)).items()
    }

    # ── 槽④告警:该服务名下有未落定 op 的 endpoint ────────────────
    alarm_eps: set[str] = set()
    if endpoint_ids:
        alarm_eps = set((await db.execute(
            select(AdaptationBatch.endpoint_id).distinct()
            .join(AdaptationOp, AdaptationOp.batch_id == AdaptationBatch.batch_id)
            .where(AdaptationBatch.endpoint_id.in_(endpoint_ids),
                   AdaptationOp.status.in_(("pending", "conflict")))
        )).scalars())

    endpoints: list[dict[str, Any]] = []
    stats = {"total": len(svc_items), "noCases": 0, "hasAlarm": 0, "neverRun": 0}
    for it in svc_items:
        ep_id = str(it["id"])
        covered = scenarios_by_ep.get(ep_id) or set()
        # 槽③:引用场景各自的最近完成态里取最新的那一次(§2.4 聚合口径)
        best: tuple[str | None, Any] | None = None
        for sid in covered:
            v = latest.get(sid)
            if v is not None and (best is None or v[1] > best[1]):
                best = v
        alarm = ep_id in alarm_eps
        endpoints.append({
            "id": ep_id,
            "method": str(it.get("method") or ""),
            "path": str(it.get("path") or ""),
            "name": str(it.get("name") or ""),
            "signals": {
                "req": None,
                "cases": bool(covered),
                "lastRun": best[0] if best else None,
                "alarm": alarm,
            },
            "caseCount": len(covered),
            "lastRunAt": iso_naive_utc(best[1] if best is not None else None),
        })
        if not covered:
            stats["noCases"] += 1
        if alarm:
            stats["hasAlarm"] += 1
        if best is None or best[0] is None:
            stats["neverRun"] += 1

    return {
        "service": service,
        "endpoints": endpoints,
        "stats": stats,
        "plateReachable": reachable,
    }


# ─── 接口级线索板(方案 §3;P1:测试象限完整,其余象限占位)────────
async def board(
    db: AsyncSession, endpoint_id: str, *, user_id: int, expand: str | None = None,
) -> dict[str, Any]:
    """接口级线索板:主体 + 测试象限(场景/执行/适配)+ 自建卡 + trails。

    node id 约定(前端连线与 localStorage 拖拽坐标都靠它稳定):
    ``ep:{endpoint_id}`` 主体 / ``sc:{scenario_id}`` / ``ex:{execution_id}`` /
    ``ad:{batch_id}`` / ``card:{id}`` / ``ep2:{endpoint_id}``(expand 二度)。
    """
    subject_id = f"ep:{endpoint_id}"

    # ── 主体:三档降级(/full 缓存 → 轻量列表 → 裸 id),板子不断中心 ──
    full = await get_endpoint_full(endpoint_id)
    item = full.item if full is not None else None
    method = path = name = version = ""
    field_count = 0
    if item is not None:
        api = item.get("api") if isinstance(item.get("api"), dict) else {}
        method = str(api.get("method") or "")
        path = str(api.get("path") or "")
        name = str(item.get("name") or "")
        version = str(item.get("version") or "")
        request = item.get("request") if isinstance(item.get("request"), dict) else {}
        decls = request.get("declarations")
        field_count = len(decls) if isinstance(decls, list) else 0
    else:
        try:
            items = await _plate_list_endpoints()
        except PlateUnavailableError:
            items = []
        lit = next((it for it in items if str(it.get("id", "")) == endpoint_id), None)
        if lit is not None:
            method = str(lit.get("method") or "")
            path = str(lit.get("path") or "")
            name = str(lit.get("name") or "")

    nodes: list[dict[str, Any]] = [{
        "id": subject_id, "kind": "endpoint", "quadrant": None,
        "label": f"{method} {path}".strip() or endpoint_id,
        "meta": {"endpointId": endpoint_id, "name": name, "version": version,
                 "fieldCount": field_count, "degraded": item is None},
    }]
    edges: list[dict[str, Any]] = []

    # ── 测试象限:引用场景(含锚点行)→ 最新完成态执行;未落定批次 ──
    ref_scenarios = sorted({sid for (sid,) in (await db.execute(
        select(ScenarioEndpointRef.scenario_id).where(
            ScenarioEndpointRef.endpoint_id == endpoint_id).distinct()
    )).all()})
    scen_rows = {r.scenario_id: r for r in (await db.execute(
        select(ComposerScenario)
        .where(ComposerScenario.scenario_id.in_(ref_scenarios))
    )).scalars().all()} if ref_scenarios else {}
    latest = await _latest_terminals(db, ref_scenarios)

    unhandled: dict[str, dict[str, Any]] = {}
    rows = (await db.execute(
        select(AdaptationBatch, AdaptationOp.status)
        .join(AdaptationOp, AdaptationOp.batch_id == AdaptationBatch.batch_id)
        .where(AdaptationBatch.endpoint_id == endpoint_id,
               AdaptationOp.status.in_(("pending", "conflict")))
    )).all()
    for batch, _op_status in rows:
        entry = unhandled.setdefault(batch.batch_id, {"batch": batch, "ops": 0})
        entry["ops"] += 1

    trails: list[dict[str, Any]] = []

    # 适配节点(未落定批次;测试象限——告警链的起点都在 Platform 痕迹里)
    for i, (bid, entry) in enumerate(sorted(unhandled.items())):
        batch = entry["batch"]
        nodes.append({
            "id": f"ad:{bid}", "kind": "adaptation", "quadrant": "test",
            "label": f"适配事件 {bid}",
            "meta": {"fromVersion": batch.from_version, "toVersion": batch.to_version,
                     "openOps": entry["ops"]},
        })
        edges.append({"from": subject_id, "to": f"ad:{bid}", "kind": "contains"})

    # 场景 + 执行节点(执行只出「最新完成态」那一行,§2.4 口径)
    scen_index: dict[str, int] = {}
    for i, sid in enumerate(ref_scenarios):
        scen_index[sid] = i
        row = scen_rows.get(sid)
        meta_name = ""
        if row is not None and isinstance(row.payload, dict):
            m = row.payload.get("meta")
            meta_name = str(m.get("name") or "") if isinstance(m, dict) else ""
        nodes.append({
            "id": f"sc:{sid}", "kind": "scenario", "quadrant": "test",
            "label": meta_name or sid,
            "meta": {"scenarioId": sid, "name": meta_name,
                     "exists": row is not None},
        })
        edges.append({"from": subject_id, "to": f"sc:{sid}", "kind": "contains"})

        ex = latest.get(sid)
        if ex is not None:
            nodes.append({
                "id": f"ex:{ex.id}", "kind": "execution", "quadrant": "test",
                "label": f"#{ex.id} {ex.status}",
                "meta": {"executionId": ex.id, "status": ex.status,
                         "passed": ex.passed, "failed": ex.failed,
                         "totalRuns": ex.total_runs,
                         "finishedAt": iso_naive_utc(ex.finished_at or ex.created_at)},
            })
            edges.append({"from": f"sc:{sid}", "to": f"ex:{ex.id}", "kind": "ran"})
            # trails(方案 §3.2):未落定批次 → 主体 → 场景 → 最近执行为失败
            if _VERDICT.get(ex.status) == "fail":
                for bid in unhandled:
                    trails.append({
                        "kind": "risk",
                        "path": [f"ad:{bid}", subject_id, f"sc:{sid}", f"ex:{ex.id}"],
                    })

    # ── 自建卡(§3.3):root 槽位 + 各象限卡;虚线连到被注解节点 ────
    cards = (await db.execute(
        select(BoardCard)
        .where(BoardCard.subject_kind == "endpoint",
               BoardCard.subject_id == endpoint_id)
        .order_by(BoardCard.is_root.desc(), BoardCard.id)
    )).scalars().all()
    card_node_ids: set[str] = set()
    for card in cards:
        node_id = f"card:{card.id}"
        card_node_ids.add(node_id)
        nodes.append({
            "id": node_id, "kind": "card", "quadrant": card.quadrant,
            "label": card.body.strip().splitlines()[0][:40] if card.body.strip() else "(空卡)",
            "meta": {"cardId": card.id, "body": card.body,
                     "isRoot": card.is_root, "quadrant": card.quadrant,
                     "annotatesNodeId": card.annotates_node_id,
                     "authorId": card.author_id, "mine": card.author_id == user_id},
        })
        if card.is_root:
            edges.append({"from": subject_id, "to": node_id, "kind": "contains"})
        if card.annotates_node_id:
            edges.append({"from": node_id, "to": card.annotates_node_id,
                          "kind": "annotates"})

    # ── expand:二度关联(P1 支持场景节点 → 它引用的其他接口)────────
    if expand and expand.startswith("sc:") and expand in {n["id"] for n in nodes}:
        sid = expand[3:]
        sibling_ids = sorted({eid for (eid,) in (await db.execute(
            select(ScenarioEndpointRef.endpoint_id).where(
                ScenarioEndpointRef.scenario_id == sid).distinct()
        )).all() if eid != endpoint_id})[:12]  # 防巨图:先封顶 12
        if sibling_ids:
            try:
                items = await _plate_list_endpoints()
            except PlateUnavailableError:
                items = []
            by_id = {str(it.get("id", "")): it for it in items}
            for eid in sibling_ids:
                lit = by_id.get(eid, {})
                nodes.append({
                    "id": f"ep2:{eid}", "kind": "endpoint", "quadrant": "test",
                    "label": f"{lit.get('method', '')} {lit.get('path', eid)}".strip(),
                    "meta": {"endpointId": eid, "expanded": True},
                })
                edges.append({"from": expand, "to": f"ep2:{eid}", "kind": "refs"})

    return {
        "subject": {
            "id": endpoint_id, "method": method, "path": path, "name": name,
            "version": version, "fieldCount": field_count,
            "degraded": item is None,
        },
        "nodes": nodes,
        "edges": edges,
        "trails": trails,
        "quadrants": _QUADRANTS_P1,
    }
