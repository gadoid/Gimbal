"""变更适配编排:影响查询 / 批次生命周期 / RS4a 新流程服务。

RS3 §5.10:基线戳(catalog_versions)与按端点开批的旧流程已删除,
比较/影响走 plate 差异接口(plate_diff_for_adaptation);批次保留
carry 类与 RS4a 提交语义(存档 → 逐条应用 → 完成/回滚)。
"""
from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.timeutil import ensure_aware
from ..models.adaptation_batch import AdaptationBatch
from ..models.user import User
from ..models.adaptation_op import AdaptationOp
from ..models.adaptation_snapshot import AdaptationSnapshot
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..models.environment import Environment
from ..models.integration_task import IntegrationTask
from ..models.scenario_endpoint_ref import ScenarioEndpointRef
from ..models.suite import Suite
from ..schemas.scenario_composer import DataSetDraft, ScenarioDraft
from . import carry_store, data_set_store, endpoint_ref_index, plate_client, scenario_store
from .scenario_store import definition_from_payload
from .adaptation_ops import (
    ALL_OPS,
    CARRY_OPS,
    DATASET_OPS,
    GLOBAL_OPS,
    STEP_OPS,
    apply_to_definition,
    apply_to_rows,
    check_step_addressable,
    field_match_names,
    rename_in_list,
    spec_has_field_cache,
)
from .plate_client import PlateUnavailableError


# ─── plate 目录拉取(M6 语法路由,信封 {ok, dim, data})──────────
async def _plate_list_endpoints() -> list[dict]:
    """GET /api/endpoint → data.items(轻量视图,自带 version/updated_at)。"""
    client = plate_client.get_client()
    try:
        resp = await client.get("/api/endpoint")
    except httpx.HTTPError as e:
        raise PlateUnavailableError(
            f"plate_unavailable: {type(e).__name__}: {e}"
        ) from e
    if resp.status_code != 200:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}: {resp.text[:200]}"
        )
    items = (resp.json().get("data") or {}).get("items")
    if not isinstance(items, list):
        raise PlateUnavailableError("plate_unavailable: no items in response")
    return [it for it in items if isinstance(it, dict)]


async def _plate_full_endpoint(endpoint_id: str) -> dict | None:
    """GET /api/endpoint/{id}/full → data.item;plate 404 → None(端点已下架)。

    carry 漂移 / carry_store 共用的 /full 拉取口(别处不得另开第二份)。
    """
    client = plate_client.get_client()
    try:
        resp = await client.get(f"/api/endpoint/{endpoint_id}/full")
    except httpx.HTTPError as e:
        raise PlateUnavailableError(
            f"plate_unavailable: {type(e).__name__}: {e}"
        ) from e
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}: {resp.text[:200]}"
        )
    item = (resp.json().get("data") or {}).get("item")
    if not isinstance(item, dict):
        raise PlateUnavailableError("plate_unavailable: no item in response")
    return item


def _utcnow() -> datetime:
    """naive-UTC(SQLite CURRENT_TIMESTAMP 亦为 UTC)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── 检测:目录 diff(spec §5.1)─────────────────────────────────
async def plate_diff_for_adaptation(
    system: str, from_ref: str, to_ref: str,
) -> dict:
    """RS4a（Release v4.4 §4.3/R7）：调 plate 差异接口替代平台自算。

    返回对象级差异 + 变化接口的**变化部位**（service/binding/request/
    responses + path 占位符差异）+ 请求与响应的字段级差异。
    """
    from ..services import plate_client
    client = plate_client.get_client()
    try:
        resp = await client.get(
            f"/api/system/{system}/diff/{from_ref}/{to_ref}", timeout=15.0)
    except Exception as e:
        raise plate_client.PlateUnavailableError(
            f"plate_unavailable: {e}") from e
    if resp.status_code >= 400:
        plate_client._raise_rejected(resp)
    envelope = resp.json()
    if not envelope.get("ok"):
        raise plate_client.PlateRejectedError(
            code="invalid_action",
            message=envelope.get("error", {}).get("message", "diff failed"))
    return envelope.get("data", {}).get("item", {})


async def catalog_diff(db: AsyncSession) -> dict:
    """RS3 §5.10：catalog_diff 已删除——被 plate 差异 + 版本提示取代。"""
    return {"pending": [], "anomalies": [], "total": 0, "checked": 0}


async def impact(
    db: AsyncSession, endpoint_id: str, field_name: str | None = None
) -> list[dict]:
    """endpoint(可选再按 field)→ 受影响清单条目(spec §5.2)。

    直填字段同样命中(索引行按字段键存在,与值是否模板无关);
    via_var 条目按数据集行实际含键(内存列存在性,D5 —— 不建
    dataset_columns 表)配对;无数据集命中时仍出一条 datasetId=None
    (变量默认值通路,D9 基线 = 直填 ∪ vars 扁平值)。

    锚点行(source=anchor,零字段锚点 step 的哨兵行)出 {source: None,
    field: None} 条目 —— 与原全量兜底直扫的产出同形;该直扫已随锚点行
    上线删除(不再 O(全部场景)/次)。字段过滤天然排除锚点行
    (field_name=''≠filter),与旧「带 field 不兜底」行为一致。
    """
    stmt = select(ScenarioEndpointRef).where(
        ScenarioEndpointRef.endpoint_id == endpoint_id
    )
    if field_name:
        stmt = stmt.where(ScenarioEndpointRef.field_name == field_name)
    stmt = stmt.order_by(
        ScenarioEndpointRef.scenario_id, ScenarioEndpointRef.step_index,
        ScenarioEndpointRef.source, ScenarioEndpointRef.field_name,
    )
    refs = (await db.execute(stmt)).scalars().all()
    scenario_ids = sorted({r.scenario_id for r in refs})
    ds_rows = (await db.execute(
        select(ComposerDataSet).where(
            ComposerDataSet.scenario_id.in_(scenario_ids)
        )
    )).scalars().all()
    by_scenario: dict[str, list[ComposerDataSet]] = {}
    for d in ds_rows:
        by_scenario.setdefault(d.scenario_id, []).append(d)

    out: list[dict] = []
    for r in refs:
        is_anchor = r.source == endpoint_ref_index.ANCHOR_SOURCE
        entry = {
            "scenarioId": r.scenario_id, "stepIndex": r.step_index,
            "source": None if is_anchor else r.source,
            "field": None if is_anchor else r.field_name,
            "viaVar": r.via_var,
            "datasetId": None, "datasetColumn": None,
        }
        if not r.via_var:  # 直填
            out.append(entry)
            continue
        entry["datasetColumn"] = r.via_var
        hit_any = False
        for d in by_scenario.get(r.scenario_id, []):
            if any(isinstance(row, dict) and r.via_var in row
                   for row in (d.rows or [])):
                out.append({**entry, "datasetId": d.dataset_id})
                hit_any = True
        if not hit_any:  # 变量默认值通路(vars 扁平值),不挂数据集
            out.append(entry)
    return out


# ─── 索引 vs 目录漂移(只读;2026-09-20)─────────────────────────
async def refs_drift(db: AsyncSession) -> dict:
    """倒排索引 endpoint 面 vs plate 接口清单 diff(结构同 carry_drift)。

    * ``dangling`` — refs 有、plate 目录无(接口改名/下架后的悬空引用行);
    * ``zeroRef``  — plate 有、refs 无(全网无人引用;网格「无覆盖」的
      另一种表述,含锚点行口径);
    * ``plateReachable`` — plate 拉不到时 False 且清单不可信(沿用
      carry_drift 纪律:面视为空 → dangling=全部 refs 面,调用方须先
      看信号再渲染,防把不可达误读成漂移)。
    """
    ref_ids = set((await db.execute(
        select(ScenarioEndpointRef.endpoint_id).distinct()
    )).scalars())
    reachable = True
    try:
        items = await _plate_list_endpoints()
    except PlateUnavailableError:
        items = []
        reachable = False
    plate_ids = {str(i["id"]) for i in items if i.get("id")}
    return {
        "dangling": sorted(ref_ids - plate_ids),
        "zeroRef": sorted(plate_ids - ref_ids),
        "plateReachable": reachable,
    }


# ─── 本批影响面摘要(只读;配套方案 §3.2,2026-09-20)──────────────
async def impact_summary(db: AsyncSession, *, endpoint_ids: list[str]) -> dict:
    """pending 端点集 → 按服务聚合的影响面摘要(适配中心顶部条)。

    * ``endpoint_ids`` 由客户端传入(它刚从 catalog/diff 拿到的 pending
      清单)—— 本函数**不复算 diff**:catalog_diff 有基线落库写副作用,
      挂在 GET 上会把写副作用藏进读路径;
    * 服务归组键 = **端点自身的目录 service**(plate 轻列表自带,唯一
      权威),不扫场景 payload 推服务 —— 更便宜且确定;
    * ``caseCount`` = 该服务 pending 端点经倒排索引命中的 distinct 场景
      数(锚点行含);跨服务的场景在多个服务条各计一次,totals 去重;
    * ``recentFailCount`` = 受影响场景的**最近一次**执行终态为 failed
      的数量。执行记录严格 owner 作用域,此处按**全站口径**跨 owner
      统计(方案 §3.5:同一批变更不能因人而异)—— 只取聚合数,不回
      执行详情/场景标题,不越 visibility 边界;
    * 端点不在 plate 轻列表(下架/传入异常 id)→ 不进任何服务条
      (无 service 可归组),也不计入 totals.changeCount。
    """
    from ..models.execution import Execution, STATUS_FAILED

    totals = {"changeCount": 0, "serviceCount": 0,
              "caseCount": 0, "recentFailCount": 0}
    if not endpoint_ids:
        return {"services": [], "totals": totals}

    items = await _plate_list_endpoints()
    svc_by_eid = {
        str(it.get("id")): str(it.get("service") or "")
        for it in items if it.get("id")
    }
    eids = [e for e in dict.fromkeys(endpoint_ids)
            if svc_by_eid.get(e)]  # 去重 + 只留可归组的

    scen_by_service: dict[str, set[str]] = {}
    if eids:
        rows = (await db.execute(
            select(ScenarioEndpointRef.endpoint_id, ScenarioEndpointRef.scenario_id)
            .where(ScenarioEndpointRef.endpoint_id.in_(eids))
            .distinct()
        )).all()
        for eid, sid in rows:
            scen_by_service.setdefault(svc_by_eid[eid], set()).add(sid)

    # 最近一次执行(跨 owner,按 id 倒序首见即最新)→ failed 终态集
    all_sids = set().union(*scen_by_service.values()) if scen_by_service else set()
    latest_failed: set[str] = set()
    if all_sids:
        exec_rows = (await db.execute(
            select(Execution.scenario_id, Execution.status)
            .where(Execution.scenario_id.in_(all_sids))
            .order_by(Execution.id.desc())
        )).all()
        seen: set[str] = set()
        for sid, st in exec_rows:
            if sid in seen:
                continue
            seen.add(sid)
            if st == STATUS_FAILED:
                latest_failed.add(sid)

    services = []
    for name in sorted(scen_by_service):
        sids = scen_by_service[name]
        services.append({
            "name": name,
            "changeCount": sum(1 for e in eids if svc_by_eid[e] == name),
            "caseCount": len(sids),
            "recentFailCount": len(sids & latest_failed),
        })
    totals = {
        "changeCount": len(eids),
        "serviceCount": len(services),
        "caseCount": len(all_sids),
        "recentFailCount": len(all_sids & latest_failed),
    }
    return {"services": services, "totals": totals}


# ─── 批次生命周期:开批次(spec §5.3)────────────────────────────
async def _get_batch(db: AsyncSession, batch_id: str) -> AdaptationBatch:
    batch = (await db.execute(
        select(AdaptationBatch).where(AdaptationBatch.batch_id == batch_id)
    )).scalar_one_or_none()
    if batch is None:
        raise KeyError(f"batch_not_found: {batch_id}")
    return batch


def _op_out(op: AdaptationOp) -> dict:
    return {
        "id": op.id, "batchId": op.batch_id, "scenarioId": op.scenario_id,
        "datasetId": op.dataset_id, "opType": op.op_type,
        "payload": op.payload or {}, "status": op.status,
        "appliedAt": op.applied_at, "note": op.note,
    }


async def _batch_detail(
    db: AsyncSession, batch_id: str, *, viewer=None
) -> dict:
    """批次详情 dict(camelCase)—— open_batch / get_batch_detail 共用,
    Task 10 的 BatchDetail 响应模型按此形状校验。

    G1 二轮扩展:``viewer``(读侧路由的当前用户)在场时补 op 行的
    scenario/dataset 展示名 —— 活名仅在可读时给出(与台账同口径),
    否则回落**本批快照**(回滚安全网恰是受影响实体的 before 整像,
    含 meta.name / dataset name),最后裸 id。open/apply/rollback 等
    写路径响应不带 viewer → 快照/裸 id 兜底,同样可读。"""
    batch = await _get_batch(db, batch_id)
    ops = (await db.execute(
        select(AdaptationOp).where(AdaptationOp.batch_id == batch_id)
        .order_by(AdaptationOp.id)
    )).scalars().all()
    snapshots = (await db.execute(
        select(AdaptationSnapshot).where(
            AdaptationSnapshot.batch_id == batch_id
        ).order_by(AdaptationSnapshot.id)
    )).scalars().all()
    counts: dict[str, int] = {}
    for op in ops:
        counts[op.status] = counts.get(op.status, 0) + 1

    # G1-E2:endpoint 展示投影(批次开立时刻的形状,不问 plate 现值)
    # RS3 §5.10:catalog_versions 已删除——展示投影不再可用,置空
    ep_name = ep_method = ep_path = ""

    # G1-E1:op 行展示名(活名[可读] → 本批快照 → 裸 id)
    snap_name: dict[str, str] = {}
    for s in snapshots:
        if s.entity_type == "scenario":
            meta = (((s.before_json or {}).get("payload") or {})
                    .get("definition") or {}).get("meta")
            n = str((meta or {}).get("name") or "")
        elif s.entity_type == "dataset":
            n = str((s.before_json or {}).get("name") or "")
        else:
            continue
        if n:
            snap_name.setdefault(f"{s.entity_type}:{s.entity_id}", n)

    sid_live: dict[str, str] = {}
    ds_live: dict[str, str] = {}
    if viewer is not None:
        from .execution_store import scenario_display_map

        sids = sorted({op.scenario_id for op in ops if op.scenario_id})
        disp = await scenario_display_map(db, viewer, sids)
        sid_live = {sid: live for sid, (live, _e) in disp.items() if live}

        from ..models.composer_data_set import ComposerDataSet
        from ..models.composer_scenario import ComposerScenario
        from .scenario_query import visibility_clause

        dsids = sorted({op.dataset_id for op in ops if op.dataset_id})
        if dsids:
            stmt = select(
                ComposerDataSet.dataset_id, ComposerDataSet.name
            ).where(ComposerDataSet.dataset_id.in_(dsids))
            vis = visibility_clause(viewer)
            if vis is not None:
                stmt = stmt.join(
                    ComposerScenario,
                    ComposerScenario.scenario_id
                    == ComposerDataSet.scenario_id,
                ).where(vis)
            ds_live = {d: str(n or "") for d, n in (await db.execute(stmt))
                       .all() if n}

    ops_out = [_op_out(op) for op in ops]
    for out, op in zip(ops_out, ops):
        if op.scenario_id:
            out["scenarioDisplayName"] = (
                sid_live.get(op.scenario_id)
                or snap_name.get(f"scenario:{op.scenario_id}")
                or op.scenario_id)
        if op.dataset_id:
            out["datasetName"] = (
                ds_live.get(op.dataset_id)
                or snap_name.get(f"dataset:{op.dataset_id}")
                or op.dataset_id)

    return {
        "batchId": batch.batch_id, "endpointId": batch.endpoint_id,
        "endpointName": ep_name, "endpointMethod": ep_method,
        "endpointPath": ep_path,
        "fromVersion": batch.from_version, "toVersion": batch.to_version,
        "status": batch.status, "operatorId": batch.operator_id,
        "operatorName": batch.operator_name,
        "createdAt": batch.created_at, "closedAt": batch.closed_at,
        "opCounts": counts,
        "ops": ops_out,
        "snapshots": [
            {"entityType": s.entity_type, "entityId": s.entity_id}
            for s in snapshots
        ],
    }


# ─── 批次生命周期:逐条应用(spec §5.3 / §9 C5)─────────────────
class _OpConflict(ValueError):
    """可预期冲突(C5 寻址失败等)—— 归并进 op 的 conflict 捕获路径。"""


async def apply_op(db: AsyncSession, op_id: int) -> dict:
    """应用一条 pending op;applied 重放幂等返回终态。

    * applied → 原样返回(幂等);
    * conflict/skipped → ValueError("op_not_applicable");
    * 批次非 open/applying → ValueError("batch_not_active");
    * 应用走既有 store(scenario_store/data_set_store)—— 倒排索引同事务
      维护、调色板校验天然生效;
    * store 抛 KeyError/ValueError(实体消失、调色板 422…)→ db.rollback
      后该 op 标 conflict + note,不中断批次其余 op;
    * 首次成功应用 open → applying;无 pending 剩余 → completed + 推进戳
      (plate 拉取失败也推 version,spec_json 留旧自愈)。
    """
    op = (await db.execute(
        select(AdaptationOp).where(AdaptationOp.id == op_id)
    )).scalar_one_or_none()
    if op is None:
        raise KeyError(f"op_not_found: {op_id}")
    if op.status == "applied":
        return _op_out(op)
    if op.status in ("conflict", "skipped"):
        raise ValueError(f"op_not_applicable: op {op_id} is {op.status}")
    batch = await _get_batch(db, op.batch_id)
    if batch.status not in ("open", "applying"):
        raise ValueError(f"batch_not_active: {batch.status}")

    payload = {**(op.payload or {})}
    try:
        if op.op_type in CARRY_OPS:
            await _apply_carry_op(db, op, payload)
        elif op.op_type in DATASET_OPS:
            await _apply_dataset_op(db, op, payload)
        else:  # STEP_OPS + renameVar:场景 definition(renameVar 联动数据集)
            await _apply_scenario_op(db, op, batch, payload)
    except (KeyError, ValueError) as e:
        await db.rollback()
        op = (await db.execute(  # rollback 后 ORM 实例过期,重取
            select(AdaptationOp).where(AdaptationOp.id == op_id)
        )).scalar_one()
        op.status = "conflict"
        op.note = str(e)[:500]
        await db.commit()
        return _op_out(op)

    op.status = "applied"
    op.applied_at = _utcnow()
    op.note = None
    if batch.status == "open":
        batch.status = "applying"
    await _maybe_complete(db, batch)
    await db.commit()
    # 通知接线(P1b,权限方案 §3.2):仅 scenario/dataset 类实体产生
    # 通知 —— carry_binding/carry_default 是全局资产无归属,不通知。
    await _notify_adaptation_applied(db, op, batch)
    return _op_out(op)


async def _notify_adaptation_applied(
    db: AsyncSession, op: AdaptationOp, batch: AdaptationBatch
) -> None:
    """adaptation_applied:受影响 owner 收「你的场景被批次触碰」推送。

    失败只记日志(通知是增强,不是 op 落地的前置)。
    """
    # 实体类型从字段推导:dataset_id 非空 = 数据集类;scenario_id 非空 =
    # 场景类;两者皆空 = carry 类全局资产(无归属,不通知)。
    if op.dataset_id is None and op.scenario_id is None:
        return
    from . import notifications as notify_svc
    try:
        scen_id = op.scenario_id
        if scen_id is None:
            return
        scen = await scenario_store.get_row(db, scen_id)
        if scen is None or scen.owner_id is None:
            return
        entity = op.dataset_id or scen_id
        await notify_svc.create_notification(
            db,
            user_id=scen.owner_id,
            type_="adaptation_applied",
            title=f"适配批次已应用:{batch.endpoint_id}",
            body=f"你的场景 {scen_id}({entity})已被适配批次 {batch.batch_id} 触碰,"
                 f"请留意字段变更(批次由 {batch.operator_name or 'operator'} 处理)。",
            link=f"/adaptations/{batch.batch_id}",
            commit=False,
        )
        await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.opt(exception=True).warning(
            "adaptation: notify applied failed (op {})", op.id)


async def skip_op(db: AsyncSession, op_id: int) -> dict:
    """跳过一条 pending op(逐条确认的"跳过"决策);幂等。

    * skipped → 原样返回(幂等,合并 renameField 后跳过两条源 op 走这里);
    * applied/conflict → ValueError("op_not_applicable");
    * 批次非 open/applying → ValueError("batch_not_active")(防御性,与
      apply_op 对称;正常不变量下 completed/rolled_back 批次无 pending op);
    * 跳过也是决策:无 pending 剩余时同样收敛 completed + 推戳。
    """
    op = (await db.execute(
        select(AdaptationOp).where(AdaptationOp.id == op_id)
    )).scalar_one_or_none()
    if op is None:
        raise KeyError(f"op_not_found: {op_id}")
    if op.status == "skipped":
        return _op_out(op)
    if op.status in ("applied", "conflict"):
        raise ValueError(f"op_not_applicable: op {op_id} is {op.status}")
    batch = await _get_batch(db, op.batch_id)
    if batch.status not in ("open", "applying"):
        raise ValueError(f"batch_not_active: {batch.status}")

    op.status = "skipped"
    op.note = "skipped by operator"
    await _maybe_complete(db, batch)
    await db.commit()
    return _op_out(op)


async def update_op(db: AsyncSession, op_id: int, payload: dict) -> dict:
    """仅 pending 可整包替换 payload(剥 "op" 键)—— mapValue 骨架补值/参数修正。"""
    op = (await db.execute(
        select(AdaptationOp).where(AdaptationOp.id == op_id)
    )).scalar_one_or_none()
    if op is None:
        raise KeyError(f"op_not_found: {op_id}")
    if op.status != "pending":
        raise ValueError(f"op_not_applicable: op {op_id} is {op.status}")

    op.payload = {k: v for k, v in payload.items() if k != "op"}
    await db.commit()
    return _op_out(op)


async def _apply_scenario_op(
    db: AsyncSession, op: AdaptationOp, batch: AdaptationBatch, payload: dict
) -> None:
    row = await scenario_store.get_row(db, op.scenario_id)
    if row is None:
        raise KeyError(f"scenario_not_found: {op.scenario_id}")
    definition = copy.deepcopy(scenario_store.definition_from_payload(row.payload))
    op_view = {"op": op.op_type, **payload}
    if op.op_type in STEP_OPS:
        conflict = check_step_addressable(definition, op_view, batch.endpoint_id)
        if conflict is not None:
            raise _OpConflict(conflict)
    apply_to_definition(definition, op_view)
    await scenario_store.update(db, op.scenario_id, ScenarioDraft(
        definition=definition,
        orchestration=(row.payload or {}).get("orchestration") or {},
        # 注册表透传(spec v2 §3):适配操作不触及该键 — 不带则经 update
        # 重铸回落 default {} 把存量条目静默清空。回滚路径走
        # model_validate(before)(payload 快照),已安全。
        assertion_registry=(row.payload or {}).get("assertion_registry") or {},
    ))
    if op.op_type == "renameVar":
        # 联动:该场景全部数据集列改名(场景先落库 → 调色板已含新键)
        ds_rows = (await db.execute(
            select(ComposerDataSet).where(
                ComposerDataSet.scenario_id == op.scenario_id
            )
        )).scalars().all()
        for d in ds_rows:
            rows = apply_to_rows(copy.deepcopy(d.rows or []), op_view)
            await data_set_store.update(db, d.dataset_id, DataSetDraft(
                name=d.name, description=d.description, rows=rows,
                var_unlocks=rename_in_list(
                    list(d.var_unlocks or []), op_view["from"], op_view["to"]
                ),
            ))


async def _apply_dataset_op(db: AsyncSession, op: AdaptationOp, payload: dict) -> None:
    if not op.dataset_id:
        raise ValueError(f"op_needs_dataset: {op.op_type} requires dataset_id")
    d = await data_set_store.get_row(db, op.dataset_id)
    if d is None:
        raise KeyError(f"data_set_not_found: {op.dataset_id}")
    rows = apply_to_rows(copy.deepcopy(d.rows or []), {"op": op.op_type, **payload})
    await data_set_store.update(db, op.dataset_id, DataSetDraft(
        name=d.name, description=d.description, rows=rows,
        var_unlocks=list(d.var_unlocks or []),
    ))


# ─── carry 值表批(spec §7):开批 / 收敛应用 / before 快照 ─────────
async def _apply_carry_op(db: AsyncSession, op: AdaptationOp,
                          payload: dict) -> None:
    """CARRY_OPS 收敛应用到值表(service 缺省 = 全局默认表)。"""
    service = payload.get("service")
    if op.op_type == "renameCarryPath":
        src, dst = payload["from"], payload["to"]
        if service:
            entries = await carry_store.get_bindings(db, service)
        else:
            entries = await carry_store.get_defaults(db)
        if src not in entries:
            raise KeyError(f"carry_path_not_found: {src}")
        if dst in entries:
            raise ValueError(f"carry_path_conflict: {dst} already present")
        entries[dst] = entries.pop(src)
        if service:
            await carry_store.put_bindings(
                db, service, entries,
                updated_by_id=None, updated_by_name="adaptation")
        else:
            await carry_store.put_defaults(
                db, entries,
                updated_by_id=None, updated_by_name="adaptation")
    elif op.op_type == "addCarryBinding":
        path, value = payload["path"], payload.get("value")
        if service:
            entries = await carry_store.get_bindings(db, service)
            entries[path] = value
            await carry_store.put_bindings(
                db, service, entries,
                updated_by_id=None, updated_by_name="adaptation")
        else:
            entries = await carry_store.get_defaults(db)
            entries[path] = value
            await carry_store.put_defaults(
                db, entries,
                updated_by_id=None, updated_by_name="adaptation")
    else:  # removeCarryBinding
        path = payload["path"]
        if service:
            entries = await carry_store.get_bindings(db, service)
        else:
            entries = await carry_store.get_defaults(db)
        entries.pop(path, None)  # 收敛:缺行 = 已达终态
        if service:
            await carry_store.put_bindings(
                db, service, entries,
                updated_by_id=None, updated_by_name="adaptation")
        else:
            await carry_store.put_defaults(
                db, entries,
                updated_by_id=None, updated_by_name="adaptation")


async def open_carry_batch(db: AsyncSession, *, service: str | None,
                           operator_id: int) -> dict:
    """开 carry 值表批(spec §7):漂移面板勾选生成。无版本语义 ——
    endpoint_id 用 ``carry:{service|global}`` 展示锚,完成不推戳。"""
    batch_id = f"bt-{uuid4().hex[:12]}"
    db.add(AdaptationBatch(
        batch_id=batch_id,
        endpoint_id=f"carry:{service or 'global'}",
        from_version="-", to_version="-",
        status="open", operator_id=operator_id,
    ))
    await _ensure_carry_snapshot(db, batch_id, service)
    await db.commit()
    return await _batch_detail(db, batch_id)


async def _ensure_carry_snapshot(db: AsyncSession, batch_id: str,
                                 service: str | None) -> None:
    entity_type = "carry_binding" if service else "carry_default"
    entity_id = service or "__global__"
    existing = (await db.execute(
        select(AdaptationSnapshot).where(
            AdaptationSnapshot.batch_id == batch_id,
            AdaptationSnapshot.entity_type == entity_type,
            AdaptationSnapshot.entity_id == entity_id,
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return
    rows = (await carry_store.get_bindings(db, service)
            if service else await carry_store.get_defaults(db))
    db.add(AdaptationSnapshot(
        batch_id=batch_id, entity_type=entity_type, entity_id=entity_id,
        before_json={"entries": dict(rows)},
    ))


async def _maybe_complete(db: AsyncSession, batch: AdaptationBatch) -> None:
    """无 pending 剩余 → completed（RS3 §5.10：基线戳机制已删除）。"""
    pending_left = (await db.execute(
        select(AdaptationOp.id).where(
            AdaptationOp.batch_id == batch.batch_id,
            AdaptationOp.status == "pending",
        ).limit(1)
    )).scalar_one_or_none()
    if pending_left is not None:
        return
    batch.status = "completed"
    batch.closed_at = _utcnow()


# ─── 批次生命周期:整批回滚(spec §5.3 乐观冲突)─────────────────
class _RollbackConflict(Exception):
    """回滚乐观冲突:实体被批次外编辑 / 重放失败 / 实体消失。"""


async def rollback_batch(db: AsyncSession, batch_id: str,
                         *, force: bool = False) -> dict:
    """整批回滚:期望态 = before + applied ops 内存重放(收敛幂等 ⇒ 重放可行)。

    场景先于数据集恢复(renameVar 对称序);当前态 ≠ 期望态 → 该实体
    conflict 跳过不盲写;pending ops → skipped;戳不推进。
    """
    batch = await _get_batch(db, batch_id)
    if batch.status not in ("open", "applying", "completed"):
        raise ValueError(f"batch_not_rollbackable: {batch.status}")

    # §5.7:只能回滚场景**最近一次**提交的适配 —— 之后还有更新的 RS4a
    # 批次触过同一场景时,须先依次回滚后面的(栈序)。
    if batch.kind in ("cross_line", "correction"):
        candidates = (await db.execute(
            select(AdaptationBatch).where(
                AdaptationBatch.kind.in_(["cross_line", "correction"]),
                AdaptationBatch.status == "completed",
                AdaptationBatch.batch_id != batch.batch_id,
            )
        )).scalars().all()
        # 时间比较在 Python 侧做(SQLite CURRENT_TIMESTAMP 与绑定参数的
        # 字符串格式不同,SQL 侧 >= 会静默失配);同秒创建用快照自增 id
        # 破平(提交必然先后落 AdaptationSnapshot,id 单调)。
        involved = candidates + [batch]
        _snap_min_rows = (await db.execute(
            select(AdaptationSnapshot.batch_id,
                   func.min(AdaptationSnapshot.id))
            .where(AdaptationSnapshot.batch_id.in_(
                [b.batch_id for b in involved]))
            .group_by(AdaptationSnapshot.batch_id)
        )).all()
        _snap_min = dict(_snap_min_rows)

        def _seq(b: AdaptationBatch) -> tuple:
            return (b.created_at or _utcnow(), _snap_min.get(b.batch_id) or 0)

        batch_seq = _seq(batch)
        for other in candidates:
            if _seq(other) > batch_seq:
                for sid in (batch.scope or []):
                    if sid in (other.scope or []):
                        raise ValueError(
                            f"not_latest: 批次 {other.batch_id} 在本批次之后"
                            f"适配了场景 {sid},请先回滚它（§5.7 栈序）")

    applied_ops = (await db.execute(
        select(AdaptationOp).where(
            AdaptationOp.batch_id == batch_id,
            AdaptationOp.status == "applied",
        ).order_by(AdaptationOp.id)
    )).scalars().all()
    snapshots = (await db.execute(
        select(AdaptationSnapshot).where(
            AdaptationSnapshot.batch_id == batch_id
        ).order_by(AdaptationSnapshot.id)
    )).scalars().all()

    restored: list[dict] = []
    conflicts: list[dict] = []

    def _snap(kind: str):
        return [s for s in snapshots if s.entity_type == kind]

    for snap in _snap("scenario_copy"):  # §5.7:副本提交的回滚 = 删除副本
        row = await scenario_store.get_row(db, snap.entity_id)
        if row is None:
            conflicts.append({"entityType": "scenario_copy",
                              "entityId": snap.entity_id,
                              "note": "copy already deleted"})
            continue
        await db.delete(row)
        restored.append({"entityType": "scenario_copy",
                         "entityId": snap.entity_id,
                         "note": "copy deleted"})
    for snap in _snap("scenario"):  # 场景先恢复
        try:
            await _rollback_scenario(db, batch, snap, applied_ops,
                                     force=force)
            restored.append(
                {"entityType": "scenario", "entityId": snap.entity_id}
            )
        except _RollbackConflict as e:
            conflicts.append({
                "entityType": "scenario", "entityId": snap.entity_id,
                "note": str(e),
            })
    for snap in _snap("dataset"):
        try:
            await _rollback_dataset(db, snap, applied_ops)
            restored.append(
                {"entityType": "dataset", "entityId": snap.entity_id}
            )
        except _RollbackConflict as e:
            conflicts.append({
                "entityType": "dataset", "entityId": snap.entity_id,
                "note": str(e),
            })
    for snap in _snap("carry_binding") + _snap("carry_default"):
        try:
            await _rollback_carry(db, snap, applied_ops)
            restored.append(
                {"entityType": snap.entity_type, "entityId": snap.entity_id}
            )
        except _RollbackConflict as e:
            conflicts.append({
                "entityType": snap.entity_type, "entityId": snap.entity_id,
                "note": str(e),
            })

    for op in (await db.execute(
        select(AdaptationOp).where(
            AdaptationOp.batch_id == batch_id,
            AdaptationOp.status == "pending",
        )
    )).scalars():
        op.status = "skipped"
        op.note = "batch rolled back"
    if restored or not conflicts:
        # 有实体还原(或本来就无可还原实体)→ 收口 rolled_back;
        # 全实体冲突且零还原 → 保持可回滚(编辑者 force 确认后重试,M4)
        batch.status = "rolled_back"
    batch.closed_at = _utcnow()
    await db.commit()
    return {
        "batchId": batch_id, "status": "rolled_back",
        "restored": restored, "conflicts": conflicts,
    }


async def _rollback_scenario(
    db: AsyncSession, batch: AdaptationBatch,
    snap: AdaptationSnapshot, applied_ops: list[AdaptationOp],
    *, force: bool = False,
) -> None:
    row = await scenario_store.get_row(db, snap.entity_id)
    if row is None:
        raise _RollbackConflict(
            "scenario_missing: entity deleted after batch opened"
        )
    before = copy.deepcopy((snap.before_json or {}).get("payload") or {})
    # RS4a 批次(单事务提交,无 op 行):提交时记录了 after 态 ——
    # current == after 才还原;否则是提交后被编辑过,列为冲突(§5.7
    # 「编辑者确认放弃修改后还原」)。
    if "after_json" in (snap.before_json or {}):
        after = copy.deepcopy(snap.before_json.get("after_json") or {})
        if (row.payload or {}) == after or force:
            # force = R27「编辑者确认放弃修改后按快照还原」(M4)
            row.payload = before
            return
        raise _RollbackConflict(
            "edited_beyond_batch: current != snapshot after-state"
            "（确认放弃提交后的修改可带 force 重试）")
    expected = copy.deepcopy(before)
    try:
        for op in applied_ops:
            if op.op_type in DATASET_OPS or op.scenario_id != snap.entity_id:
                continue
            op_view = {"op": op.op_type, **(op.payload or {})}
            if op.op_type in STEP_OPS:
                conflict = check_step_addressable(
                    scenario_store.definition_from_payload(expected), op_view,
                    batch.endpoint_id,
                )
                if conflict is not None:
                    raise _RollbackConflict(
                        f"replay_failed: op {op.id}: {conflict}"
                    )
            apply_to_definition(
                scenario_store.definition_from_payload(expected), op_view,
            )
    except (KeyError, ValueError, IndexError) as e:
        raise _RollbackConflict(f"replay_failed: {e}") from e
    if (row.payload or {}) != expected:
        raise _RollbackConflict(
            "edited_beyond_batch: current != before+ops replay"
        )
    try:  # 恢复写也可能撞调色板(场景侧被冲突跳过、改名键未还原)→ 同归冲突
        await scenario_store.update(
            db, snap.entity_id, ScenarioDraft.model_validate(before)
        )
    except ValueError as e:
        raise _RollbackConflict(f"restore_failed: {e}") from e


async def _rollback_dataset(
    db: AsyncSession,
    snap: AdaptationSnapshot,
    applied_ops: list[AdaptationOp],
) -> None:
    d = await data_set_store.get_row(db, snap.entity_id)
    if d is None:
        raise _RollbackConflict(
            "dataset_missing: entity deleted after batch opened"
        )
    before = snap.before_json or {}
    expected_rows = copy.deepcopy(before.get("rows") or [])
    expected_unlocks = list(before.get("varUnlocks") or [])
    try:
        for op in applied_ops:
            op_view = {"op": op.op_type, **(op.payload or {})}
            if (op.op_type == "renameVar"
                    and op.scenario_id == before.get("scenarioId")):
                expected_rows = apply_to_rows(expected_rows, op_view)
                expected_unlocks = rename_in_list(
                    expected_unlocks, op_view["from"], op_view["to"]
                )
            elif op.op_type in DATASET_OPS and op.dataset_id == snap.entity_id:
                expected_rows = apply_to_rows(expected_rows, op_view)
    except (KeyError, ValueError) as e:
        raise _RollbackConflict(f"replay_failed: {e}") from e
    current = {"name": d.name, "description": d.description,
               "rows": d.rows or [], "varUnlocks": list(d.var_unlocks or [])}
    if current != {"name": before.get("name"),
                   "description": before.get("description"),
                   "rows": expected_rows,
                   "varUnlocks": expected_unlocks}:
        raise _RollbackConflict(
            "edited_beyond_batch: current != before+ops replay"
        )
    try:  # before 行键可能已不在调色板(场景侧被冲突跳过)→ 拒写并归冲突
        await data_set_store.update(db, snap.entity_id, DataSetDraft(
            name=before.get("name") or d.name,
            description=before.get("description") or "",
            rows=before.get("rows") or [],
            var_unlocks=list(before.get("varUnlocks") or []),
        ))
    except ValueError as e:
        raise _RollbackConflict(f"restore_failed: {e}") from e


async def _rollback_carry(db: AsyncSession, snap: AdaptationSnapshot,
                          applied_ops: list[AdaptationOp]) -> None:
    """值表回滚:期望态 = before + applied carry ops 内存重放,比对后恢复。"""
    before = dict((snap.before_json or {}).get("entries") or {})
    service = snap.entity_id if snap.entity_type == "carry_binding" else None
    expected = dict(before)
    for op in applied_ops:
        if op.op_type not in CARRY_OPS:
            continue
        payload = {**(op.payload or {})}
        if payload.get("service") != service:
            continue
        kind = op.op_type
        if kind == "renameCarryPath":
            if payload["from"] in expected:
                expected[payload["to"]] = expected.pop(payload["from"])
        elif kind == "addCarryBinding":
            expected[payload["path"]] = payload.get("value")
        else:
            expected.pop(payload.get("path"), None)
    current = (await carry_store.get_bindings(db, service)
               if service else await carry_store.get_defaults(db))
    if current != expected:
        raise _RollbackConflict(
            "edited_beyond_batch: current != before+ops replay")
    if service:
        await carry_store.put_bindings(
            db, service, before,
            updated_by_id=None, updated_by_name="rollback")
    else:
        await carry_store.put_defaults(
            db, before,
            updated_by_id=None, updated_by_name="rollback")


# ─── 批次查询与人工 op(spec §5.3/§5.4)──────────────────────────
async def list_batches(
    db: AsyncSession, *, status: str | None = None,
    page: int = 1, page_size: int = 50, viewer=None,
) -> tuple[list[dict], int]:
    """批次列表(新→旧)。M4(§6.3):status 精确 + Page 信封 —— detail
    只为当前页构建(逐批 _batch_detail 是隐藏 N+1,分页把它钉在页大小)。"""
    stmt = select(AdaptationBatch)
    if status:
        stmt = stmt.where(AdaptationBatch.status == status)
    total = (await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    batches = (await db.execute(
        stmt.order_by(AdaptationBatch.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return [await _batch_detail(db, b.batch_id, viewer=viewer)
            for b in batches], int(total)


async def list_batches_for_owner(
    db: AsyncSession, owner_id: int, *, status: str | None = None,
    page: int = 1, page_size: int = 50, viewer=None,
) -> tuple[list[dict], int]:
    """owner 视图(C13):批次涉及场景中存在本人场景的批次(新→旧)。

    归属唯一权威是 ``ComposerScenario.owner_id``;``owner`` 字符串列仅展示
    快照,过滤不得使用。涉及场景 = ops.scenario_id ∪ scenario 快照
    entity_id(快照兜底:批次回滚后 ops 仍在,场景删除时仅剩快照记录)。
    """
    owned_ids = set((await db.execute(
        select(ComposerScenario.scenario_id).where(
            ComposerScenario.owner_id == owner_id
        )
    )).scalars())
    if not owned_ids:
        return [], 0
    hit = set((await db.execute(
        select(AdaptationOp.batch_id).where(
            AdaptationOp.scenario_id.in_(owned_ids))
    )).scalars())
    hit |= set((await db.execute(
        select(AdaptationSnapshot.batch_id).where(
            AdaptationSnapshot.entity_type == "scenario",
            AdaptationSnapshot.entity_id.in_(owned_ids),
        )
    )).scalars())
    if not hit:
        return [], 0
    stmt = select(AdaptationBatch).where(AdaptationBatch.batch_id.in_(hit))
    if status:
        stmt = stmt.where(AdaptationBatch.status == status)
    total = (await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    batches = (await db.execute(
        stmt.order_by(AdaptationBatch.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return [await _batch_detail(db, b.batch_id, viewer=viewer)
            for b in batches], int(total)


async def get_batch_detail(
    db: AsyncSession, batch_id: str, *, viewer=None
) -> dict:
    return await _batch_detail(db, batch_id, viewer=viewer)


async def create_op(
    db: AsyncSession, batch_id: str, *,
    op_type: str, scenario_id: str | None,
    dataset_id: str | None, payload: dict,
) -> dict:
    """人工补一条 op(renameVar / 数据集 op / carry 值表 op,§5.4/§7)。

    仅批次 open(尚未应用任何 op)时可加 —— 此时现场补录的快照就是
    真 before 像;payload 剥掉可能的 "op" 键(类型在 op_type 列)。
    CARRY_OPS 免 scenario_id(值表 op 无场景落点,D1)。
    """
    if op_type not in ALL_OPS:
        raise ValueError(f"bad_op_type: {op_type} not in {ALL_OPS}")
    if op_type in CARRY_OPS:
        pass  # 无场景/数据集寻址;payload.service 决定触哪张值表
    elif op_type in DATASET_OPS and not dataset_id:
        raise ValueError(f"op_needs_dataset: {op_type} requires datasetId")
    elif not scenario_id:
        raise ValueError(f"op_needs_scenario: {op_type} requires scenarioId")
    batch = await _get_batch(db, batch_id)
    if batch.status != "open":
        raise ValueError(
            f"batch_not_active: {batch.status} (ops can only be added while open)"
        )
    if op_type in CARRY_OPS:
        # 回滚安全网:开批已建本表快照;op 触另一张值表(如服务批里的
        # 全局默认 op)时现场补 before 像 —— 与 _ensure_dataset_snapshot 同款
        await _ensure_carry_snapshot(db, batch_id, payload.get("service"))
    elif op_type in DATASET_OPS:
        await _ensure_dataset_snapshot(db, batch_id, dataset_id)
    else:
        await _ensure_scenario_snapshot(db, batch_id, scenario_id)
        if op_type in GLOBAL_OPS:  # renameVar 联动全部数据集列 → 快照对齐 apply 面
            ds_rows = (await db.execute(
                select(ComposerDataSet).where(
                    ComposerDataSet.scenario_id == scenario_id
                )
            )).scalars().all()
            for d in ds_rows:
                await _ensure_dataset_snapshot(db, batch_id, d.dataset_id)
    op = AdaptationOp(
        batch_id=batch_id, scenario_id=scenario_id, dataset_id=dataset_id,
        op_type=op_type,
        payload={k: v for k, v in payload.items() if k != "op"},
        status="pending",
    )
    db.add(op)
    await db.commit()
    return _op_out(op)


async def _ensure_scenario_snapshot(
    db: AsyncSession, batch_id: str, scenario_id: str
) -> None:
    """批次打开时没存档到的场景(不在受影响面内)→ 现场补 before 像。"""
    existing = (await db.execute(
        select(AdaptationSnapshot).where(
            AdaptationSnapshot.batch_id == batch_id,
            AdaptationSnapshot.entity_type == "scenario",
            AdaptationSnapshot.entity_id == scenario_id,
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return
    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise KeyError(f"scenario_not_found: {scenario_id}")
    db.add(AdaptationSnapshot(
        batch_id=batch_id, entity_type="scenario", entity_id=scenario_id,
        before_json={"payload": copy.deepcopy(row.payload or {})},
    ))


async def _ensure_dataset_snapshot(
    db: AsyncSession, batch_id: str, dataset_id: str
) -> None:
    existing = (await db.execute(
        select(AdaptationSnapshot).where(
            AdaptationSnapshot.batch_id == batch_id,
            AdaptationSnapshot.entity_type == "dataset",
            AdaptationSnapshot.entity_id == dataset_id,
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return
    d = await data_set_store.get_row(db, dataset_id)
    if d is None:
        raise KeyError(f"data_set_not_found: {dataset_id}")
    db.add(AdaptationSnapshot(
        batch_id=batch_id, entity_type="dataset", entity_id=dataset_id,
        before_json={
            "scenarioId": d.scenario_id, "name": d.name,
            "description": d.description,
            "rows": copy.deepcopy(d.rows or []),
            "varUnlocks": list(d.var_unlocks or []),
        },
    ))


async def _ensure_edit_rights(db, user, scenario_ids: list[str]) -> None:
    """R22：适配权限跟随场景编辑权——admin 或场景 owner。"""
    from fastapi import HTTPException
    from app.services.scenario_store import owned_scenario_ids

    if getattr(user, 'role', '') == 'admin':
        return
    owned = await owned_scenario_ids(db, user)
    for sid in scenario_ids:
        if str(sid) not in owned:
            raise HTTPException(
                status_code=403,
                detail=f'not_scenario_owner: 场景 {sid} 不由当前用户编辑，无权适配（R22）')


# ─── RS4a 新流程（Release v4.4 §5）：比较 → 保存检查 → 提交 ────────

def _scenario_systems(definition: dict) -> list[str]:
    """场景涉及的系统:step.endpoint 前缀优先,回落 meta.system。"""
    eps: set[str] = set()
    for st in (definition.get("steps") or []):
        if isinstance(st, dict) and st.get("endpoint"):
            eps.add(str(st["endpoint"]).split(".")[0])
    if eps:
        return sorted(eps)
    return sorted((definition.get("meta") or {}).get("system") or [])


# ─── H1/H2:方案应用与检查顺序 + 场景内引用改写 ────────────────────

def _apply_ops_to_payload(payload: dict, ops: list) -> list[str]:
    """把 op 列表应用到完整 payload(definition 就地 + 引用联动改写)。

    H2:结构级 op 经 ``op["_payload"]`` 拿到 payload 引用以改写
    ``assertion_registry`` 与 ``ui.fieldStates``(R30);字段改名/删除
    的 jsonpath 改写在 ``_rewrite_field_refs``。返回触发的结构级
    op 名(调用方据此清空 RunScheme stepTo)。
    """
    from .adaptation_ops import STRUCTURE_OPS, apply_to_definition
    definition = definition_from_payload(payload)
    structure_kinds: list[str] = []
    for op in ops:
        kind = str(op.get("op") or "")
        if kind in STRUCTURE_OPS:
            structure_kinds.append(kind)
        apply_to_definition(definition, {**op, "_payload": payload})
        if kind in ("renameField", "removeField"):
            _rewrite_field_refs(payload, op)
    return structure_kinds


def _jsonpath_root(path) -> str:
    """`$.a.b[0]` → `a`;非 $. 前缀原样。"""
    p = str(path or "")
    if not p.startswith("$."):
        return p
    return p[2:].split(".")[0].split("[")[0]


def _rewrite_field_refs(payload: dict, op: dict) -> None:
    """字段改名/删除 → 注入条目 jsonpath 与字段状态根段同步改写(R30)。

    * renameField:根段 == from 的条目/增量改写为 to;
    * removeField:根段 == field 的条目标 ``_dangling``(预检可见),
      字段状态条目删除。
    """
    kind = op.get("op")
    step_i = op.get("step")
    old = op.get("from") if kind == "renameField" else op.get("field")
    new = op.get("to")
    if old is None:
        return
    step_key = str(step_i) if isinstance(step_i, int) else None

    reg = payload.get("assertion_registry") or {}
    if isinstance(reg, dict):
        for e in (reg.get("entries") or []):
            if not isinstance(e, dict):
                continue
            loc = e.get("path")          # 条目形状:{path:{stepIndex,source,jsonpath}}
            if not isinstance(loc, dict):
                continue
            if step_key is not None and str(loc.get("stepIndex")) != step_key:
                continue
            root = _jsonpath_root(loc.get("jsonpath"))
            if root != old:
                continue
            jp = str(loc.get("jsonpath") or "")
            rest = jp[2 + len(old):] if jp.startswith("$.") else ""
            if kind == "renameField" and new:
                loc["jsonpath"] = f"$.{new}{rest}"
                e.pop("_dangling", None)
            else:  # removeField:悬空(正式执行 409 可见,预检告警)
                e["_dangling"] = True

    ui = payload.get("ui") or {}
    fs = (ui.get("fieldStates") if isinstance(ui, dict) else None) or {}
    if step_key and isinstance(fs.get(step_key), dict):
        inc = fs[step_key]
        if kind == "renameField" and new:
            for p in [p for p in inc if _jsonpath_root(p) == old]:
                rest = p[2 + len(old):] if p.startswith("$.") else ""
                inc[f"$.{new}{rest}"] = inc.pop(p)
        else:
            for p in [p for p in inc if _jsonpath_root(p) == old]:
                del inc[p]


async def _clear_scheme_step_to(db: AsyncSession, scenario_id: str) -> int:
    """R30:步骤位置变化时清空 RunScheme 的执行区间 stepTo。

    调试区间是按步骤序号的参数,不做精确重映射;清空后在批次页提示
    「调试区间已重置」。返回清空的方案数。
    """
    from ..models.composer_run_scheme import ComposerRunScheme
    rows = (await db.execute(
        select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == scenario_id)
    )).scalars().all()
    cleared = 0
    for r in rows:
        p = r.payload or {}
        if not isinstance(p, dict):
            continue
        # M10 RunOptions 迁移完成:stepTo 只在 payload.options.step_to
        opts = p.get("options")
        if isinstance(opts, dict) and opts.get("step_to") is not None:
            r.payload = {**p, "options": {**opts, "step_to": None}}
            cleared += 1
    return cleared


def _draft_field_ops(field_group: dict) -> list[dict]:
    """从 R7 field_diff 自动起草字段级 op（§5.4「草案」来源）。

    可起草：新增字段（addField 补骨架值）、删除字段（removeField）、
    path 占位符改名（renamePathParam）；改名一删一增由用户配对
    （renameField 用户指定）、值域变化 mapValue 给骨架（map 空）——
    这两类不在自动草案里。
    """
    parts = field_group.get("parts") or {}
    req = parts.get("request") or {}
    fd = req.get("field_diff") or {}
    ops: list[dict] = []
    step, eid = field_group.get("step"), field_group.get("endpoint")
    for p in fd.get("removed", []):
        root = p[2:].split(".")[0].split("[")[0] if p.startswith("$.") else p
        ops.append({"op": "removeField", "step": step, "field": root,
                    "endpoint": eid})
    for p in fd.get("added", []):
        root = p[2:].split(".")[0].split("[")[0] if p.startswith("$.") else p
        ops.append({"op": "addField", "step": step, "field": root,
                    "value": "", "endpoint": eid})
    binding = parts.get("binding") or {}
    pp = binding.get("path_placeholders") or {}
    for old, new in zip(pp.get("from") or [], pp.get("to") or []):
        ops.append({"op": "renamePathParam", "step": step,
                    "from": old, "to": new, "endpoint": eid})
    return ops


async def compare_scenario(
    db: AsyncSession, *, scenario_id: str, target_revision: str,
    system: str | None = None,
) -> dict:
    """RS4a 比较（§5.3）:起点修订 vs 目标修订的 plate 差异 + 三组影响。"""
    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise ValueError(f"scenario_not_found: {scenario_id}")
    payload = row.payload or {}
    definition = definition_from_payload(payload)
    meta_plate = (definition.get("meta") or {}).get("plate") or {}
    systems = [system] if system else _scenario_systems(definition)
    if len(systems) > 1:
        raise ValueError(
            "multi_system_scenario: 场景声明了多个系统，请指定 system 参数分别比较")
    if not systems:
        raise ValueError("no_system_declared: 场景未声明任何系统")

    sys_ = systems[0]
    from_ref = meta_plate.get(sys_) or "working"
    diff = await plate_diff_for_adaptation(sys_, from_ref, target_revision)

    # 对象键形如 "endpoint.{id}"(id 自身含点,按前缀剥离,不 rsplit)
    changed = {k[len("endpoint."):] for k in diff.get("changed", {})
               if k.startswith("endpoint.")}
    removed = {k[len("endpoint."):] for k in diff.get("removed", [])
               if k.startswith("endpoint.")}

    # 三组判定（§5.3）
    direct: list[dict] = []
    field: list[dict] = []
    structure: list[dict] = []
    for i, st in enumerate(definition.get("steps") or []):
        if not isinstance(st, dict) or not st.get("endpoint"):
            continue
        eid = str(st["endpoint"])
        if eid in removed:
            structure.append({"step": i, "endpoint": eid,
                              "reason": "endpoint_removed"})
        elif eid in changed:
            parts = (diff.get("changed", {})
                     .get(f"endpoint.{eid}", {}).get("parts") or {})
            keys = set(parts or {})
            if keys and keys <= {"service", "binding"} and not parts.get(
                    "path_placeholders_changed"):
                direct.append({"step": i, "endpoint": eid,
                               "reason": "binding_only"})
            else:
                field.append({"step": i, "endpoint": eid, "parts": parts})
        else:
            direct.append({"step": i, "endpoint": eid,
                           "reason": "unchanged"})
    # §5.4:字段级 op 从差异自动起草（新增/删除/占位符改名）;
    # 向导提交时作为 ops 初稿,用户可增删
    drafted_ops: list[dict] = []
    for fg in field:
        drafted_ops.extend(_draft_field_ops(fg))
    return {
        "scenario_id": scenario_id, "system": sys_,
        "from": from_ref, "to": target_revision,
        "diff": diff,
        "groups": {"direct": direct, "field": field, "structure": structure},
        "drafted_ops": drafted_ops,
    }


def _body_root_keys(body) -> set[str]:
    """body 一层键(root 段匹配口径)。"""
    return set(body.keys()) if isinstance(body, dict) else set()


def _declared_roots(item, section: str) -> set[str]:
    """目标修订契约的声明路径根段全集(request/responses)。"""
    if not isinstance(item, dict):
        return set()
    sec = item.get(section)
    decls = (sec.get("declarations")
             if isinstance(sec, dict) else None) or []
    out: set[str] = set()
    for d in decls:
        if isinstance(d, dict):
            p = d.get("path")
            if isinstance(p, str) and p.startswith("$."):
                out.add(p[2:].split(".")[0].split("[")[0])
    return out


async def save_check(
    db: AsyncSession, *, scenario_id: str, target_revision: str,
    system: str | None = None,
) -> dict:
    """RS4a 保存检查（§5.6）——向导第 3 步的**现状**预检。

    检查对象是当前存储的场景(方案起草前的口径:展示「还差什么」)。
    提交路径(submit_adaptation)检查的是**应用方案之后**的场景
    (H1)——两处共用 ``_check_payload``。
    """
    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise ValueError(f"scenario_not_found: {scenario_id}")
    return await _check_payload(
        db, row.payload or {}, target_revision, system,
        scenario_id=scenario_id, owner_id=row.owner_id)


async def _check_payload(
    db: AsyncSession, payload: dict, target_revision: str,
    system: str | None, *, scenario_id: str, owner_id: int | None,
) -> dict:
    """保存检查主体:①目标修订试算（阻断）②引用检查 ③保存方式推荐。

    入参 payload 是待检场景(H1:提交路径传入应用 op 之后的方案态)。
    """
    payload = copy.deepcopy(payload)
    definition = definition_from_payload(payload)
    meta_plate = (definition.get("meta") or {}).get("plate") or {}
    systems = [system] if system else _scenario_systems(definition)
    if len(systems) > 1:
        raise ValueError("multi_system_scenario: 请指定 system 参数")
    if not systems:
        raise ValueError("no_system_declared")

    sys_ = systems[0]
    from_ref = meta_plate.get(sys_) or "working"
    issues: list[dict] = []
    review_items: list[dict] = []

    # ① 目标修订试算:meta.plate 指向目标 → /convert(forbid+重投影)
    definition.setdefault("meta", {}).setdefault(
        "plate", {})[sys_] = target_revision
    convert_result = None
    try:
        convert_result = await plate_client.convert(payload)
    except plate_client.PlateRejectedError as e:
        issues.append({"code": "trial_rejected", "message": str(e)})
    except plate_client.PlateUnavailableError as e:
        issues.append({"code": "plate_unavailable", "message": str(e.message)})

    # ①b 逐步骤字段比对(多余/缺失必填/类型不符,M3)+ 字段状态定位
    fulls: dict = {}
    for st in (definition.get("steps") or []):
        if isinstance(st, dict) and st.get("endpoint"):
            eid = str(st["endpoint"])
            if eid not in fulls:
                try:
                    fulls[eid] = await plate_client.get_endpoint_full_at(
                        eid, target_revision)
                except plate_client.PlateUnavailableError:
                    fulls[eid] = None

    def _roots(item, section: str) -> dict[str, dict]:
        """根段 → 声明条目(含 required/type/state)。"""
        if not isinstance(item, dict):
            return {}
        sec = item.get(section)
        decls = (sec.get("declarations")
                 if isinstance(sec, dict) else None) or []
        out: dict[str, dict] = {}
        for d in decls:
            if isinstance(d, dict):
                p = d.get("path")
                if isinstance(p, str) and p.startswith("$."):
                    root = p[2:].split(".")[0].split("[")[0]
                    # 深层声明归到根(比对口径 = 根段)
                    out.setdefault(root, d)
        return out

    req_roots = {eid: _roots(f, "request") for eid, f in fulls.items()}
    resp_roots = {eid: _roots(f, "responses") for eid, f in fulls.items()}

    _TYPE_OF: dict[type, str] = {
        str: "string", bool: "boolean", int: "number", float: "number",
    }

    ui_fs = (payload.get("ui") or {}).get("fieldStates") or {}
    for i, st in enumerate(definition.get("steps") or []):
        if not isinstance(st, dict):
            continue
        eid = str(st.get("endpoint") or "")
        if not eid:
            continue
        roots = req_roots.get(eid)
        if roots is None:
            continue                      # 契约不可得:试算已覆盖该错误面
        body = (st.get("request") or {}).get("body")
        body_keys = set(body.keys()) if isinstance(body, dict) else set()
        for extra in sorted(body_keys - set(roots)):
            issues.append({
                "code": "extra_field", "step": i, "field": extra,
                "message": f"步骤 {i + 1} 字段 {extra} 不在目标修订声明中"})
        for root, decl in sorted(roots.items()):
            if root not in body_keys:
                if decl.get("required"):
                    issues.append({
                        "code": "missing_required", "step": i, "field": root,
                        "message": (f"步骤 {i + 1} 缺必填字段 {root}"
                                    "(目标修订声明 required)")})
                continue
            # 类型不符:字面量值才判(${var}/嵌套容器跳过)
            want = str(decl.get("type") or "").lower()
            val = body.get(root)
            got = _TYPE_OF.get(type(val))
            if (want and got and got != want
                    and not (isinstance(val, str) and "${" in val)):
                issues.append({
                    "code": "type_mismatch", "step": i, "field": root,
                    "message": (f"步骤 {i + 1} 字段 {root} 类型不符:"
                                f"声明 {want},场景 {got}")})
        inc = ui_fs.get(str(i)) or {}
        for p in sorted(inc):
            if _jsonpath_root(p) not in roots:
                issues.append({
                    "code": "field_state_unlocatable", "step": i, "field": p,
                    "message": f"字段状态 {p} 在目标修订上无法定位"})

    # 断言注册表定位 + R14 评审项(JSONPath 根段无法定位)
    entries = ((payload.get("assertion_registry") or {})
               .get("entries")) or []
    steps = definition.get("steps") or []
    for e in entries:
        if not isinstance(e, dict):
            continue
        p = e.get("path")
        if not isinstance(p, dict):
            continue
        si = p.get("stepIndex")
        jp = str(p.get("jsonpath") or "")
        root = _jsonpath_root(jp)
        if not isinstance(si, int) or not (0 <= si < len(steps)):
            issues.append({
                "code": "entry_step_out_of_range", "entry": e.get("id"),
                "message": f"注入条目 {e.get('id')} 的步骤索引越界"})
            continue
        eid = str((steps[si] or {}).get("endpoint") or "")
        universe = set(req_roots.get(eid) or {}) | set(resp_roots.get(eid) or {})
        if root and root not in universe:
            review_items.append({
                "entry": e.get("id"), "step": si, "jsonpath": jp,
                "reason": "root_not_locatable",
                "message": (f"条目 {e.get('id')} 的 JSONPath 根段 {root} "
                            "在目标修订上不存在（R14:需确认）"),
            })

    # ② 引用检查（区分自己/他人）
    suites = (await db.execute(select(Suite))).scalars().all()
    refs_own: list[dict] = []
    refs_others: list[dict] = []
    for su in suites:
        if scenario_id in ((su.mode_config or {}).get("units") or {}):
            entry = {"type": "suite", "id": su.id, "name": su.name,
                     "owner_id": su.owner_id}
            (refs_own if su.owner_id == owner_id
             else refs_others).append(entry)
    tasks = (await db.execute(
        select(IntegrationTask).where(
            IntegrationTask.scenario_id == scenario_id)
    )).scalars().all()
    for t in tasks:
        entry = {"type": "integration", "id": t.id, "name": t.name,
                 "owner_id": t.holder_id or t.owner_id}
        (refs_own if entry["owner_id"] == owner_id
         else refs_others).append(entry)

    # ③ 保存方式推荐（§5.6 默认规则）
    from_line = from_ref.split("#")[0]
    env_declares_old = False
    envs = (await db.execute(select(Environment))).scalars().all()
    for env in envs:
        if (env.lines or {}).get(sys_) == from_line:
            env_declares_old = True
            break
    recommendation = ("copy" if (target_revision == "working"
                                 or refs_others or env_declares_old)
                      else "direct")

    return {
        "ok": not issues and not review_items,
        "blocking_issues": issues,
        "review_items": review_items,        # R14:确认后可提交
        "references": {"own": refs_own, "others": refs_others},
        "recommendation": recommendation,
        "from": from_ref, "to": target_revision, "system": sys_,
        "convert_result": convert_result,
    }


async def submit_adaptation(
    db: AsyncSession, *, scenario_id: str, ops: list,
    target_revision: str, save_mode: str,
    review_confirmed: bool = False, system: str | None = None, user=None,
) -> dict:
    """RS4a 提交（§5.7）:按场景单事务 —— 快照 → 应用 op → meta.plate → 审计。

    H1:保存检查的对象是**应用方案之后**的场景(先构造方案态,试算
    通过才落库);H2:op 应用带 payload 引用,注入条目/字段状态随
    op 联动改写,结构级 op 清空 RunScheme stepTo(R30)。
    """
    from ..services import activity as activity_svc

    await _ensure_edit_rights(db, user, [scenario_id])

    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise ValueError(f"scenario_not_found: {scenario_id}")
    payload = row.payload or {}
    original_definition = definition_from_payload(payload)
    sys_candidates = ([system] if system
                      else _scenario_systems(original_definition))
    if len(sys_candidates) > 1:
        raise ValueError("multi_system_scenario: 请指定 system 参数")
    if not sys_candidates:
        raise ValueError("no_system_declared")
    sys_ = sys_candidates[0]
    from_ref = ((original_definition.get("meta") or {})
                .get("plate") or {}).get(sys_) or "working"

    # ① 方案态:应用全部 op(含引用改写)+ meta.plate 指向目标
    planned = copy.deepcopy(payload)
    structure_kinds = _apply_ops_to_payload(planned, ops or [])
    definition_from_payload(planned).setdefault(
        "meta", {}).setdefault("plate", {})[sys_] = target_revision
    # R30:步骤位置变化 → 清空 RunScheme 执行区间(调试参数不重映射)
    if structure_kinds:
        await _clear_scheme_step_to(db, scenario_id)

    # ② 保存检查跑在方案态上(H1)
    check = await _check_payload(
        db, planned, target_revision, sys_,
        scenario_id=scenario_id, owner_id=row.owner_id)
    if check["blocking_issues"]:
        raise ValueError(
            "save_check_failed: " + "; ".join(
                i.get("message", str(i)) for i in check["blocking_issues"]))
    if check["review_items"] and not review_confirmed:
        raise ValueError(
            "review_items_unconfirmed: "
            f"{len(check['review_items'])} 个 R14 评审项未确认")

    same_line = from_ref.split("#")[0] == target_revision.split("#")[0]
    kind = "correction" if same_line else "cross_line"
    operator_name = (getattr(user, "display_name", None)
                     or getattr(user, "username", None) or "")
    batch_id = f"bt-{uuid4().hex[:12]}"

    if save_mode == "copy":
        result = await save_as_copy(
            db, scenario_id, user=user, ops=ops,
            target_revision=target_revision, batch_id=batch_id)
        db.add(AdaptationBatch(
            batch_id=batch_id, kind=kind,
            endpoint_id=f"rs4a:{sys_}",
            from_version=from_ref, to_version=target_revision,
            from_revisions=[{"scenario_id": scenario_id, "from": from_ref}],
            to_revision=target_revision, scope=[scenario_id],
            save_mode="copy", status="completed",
            operator_id=getattr(user, "id", None),
            operator_name=operator_name, closed_at=_utcnow()))
        # 副本回滚即删:快照记录新建的副本 id
        db.add(AdaptationSnapshot(
            batch_id=batch_id, entity_type="scenario_copy",
            entity_id=result["new_scenario_id"],
            before_json={"source": scenario_id,
                         "target_revision": target_revision}))
        await db.commit()
        await activity_svc.record(
            db, actor_id=getattr(user, "id", None),
            kind="scenario.version_change",
            resource_type="scenario", resource_id=result["new_scenario_id"],
            detail={"from": from_ref, "to": target_revision,
                    "batchId": batch_id, "saveMode": "copy",
                    "sourceScenarioId": scenario_id})
        return {"success": True, "new_scenario_id": result["new_scenario_id"],
                "save_mode": "copy", "batch_id": batch_id}

    # ③ 直接保存:单事务(快照 → 方案态落库 → 引用索引)
    before = copy.deepcopy(payload)
    row.payload = planned
    db.add(AdaptationSnapshot(
        batch_id=batch_id, entity_type="scenario", entity_id=scenario_id,
        before_json={"payload": before, "after_json": copy.deepcopy(planned),
                     "save_mode": "direct",
                     "from": from_ref, "to": target_revision}))
    db.add(AdaptationBatch(
        batch_id=batch_id, kind=kind,
        endpoint_id=f"rs4a:{sys_}",
        from_version=from_ref, to_version=target_revision,
        from_revisions=[{"scenario_id": scenario_id, "from": from_ref}],
        to_revision=target_revision, scope=[scenario_id],
        save_mode="direct", status="completed",
        operator_id=getattr(user, "id", None),
        operator_name=operator_name, closed_at=_utcnow()))
    await endpoint_ref_index.sync_scenario(db, scenario_id, row.payload)
    await db.commit()

    await activity_svc.record(
        db, actor_id=getattr(user, "id", None),
        kind="scenario.version_change",
        resource_type="scenario", resource_id=scenario_id,
        detail={"from": from_ref, "to": target_revision,
                "batchId": batch_id, "saveMode": "direct",
                **({"stepToReset": True} if structure_kinds else {})})
    # §5.9:影响他人引用时通知其所有者
    try:
        await notify_cross_owner(
            db, scenario_id, from_rev=from_ref, to_rev=target_revision,
            batch_id=batch_id)
    except Exception:  # noqa: BLE001 — 通知失败不阻断提交
        logger.warning("adaptation: notify_cross_owner failed ({})", scenario_id)
    return {"success": True, "scenario_id": scenario_id,
            "save_mode": "direct", "batch_id": batch_id}


async def stale_scenarios(
    db: AsyncSession, *, user_id: int | None = None,
) -> list[dict]:
    """RS4a 陈旧清单（§2.3）:仍为预览 / 有新版本线 / 定义已修正 / 线已退役。"""
    stmt = select(ComposerScenario)
    if user_id is not None:
        stmt = stmt.where(ComposerScenario.owner_id == user_id)
    rows = (await db.execute(stmt)).scalars().all()

    envs = (await db.execute(select(Environment))).scalars().all()

    # plate 调用在请求内按系统缓存(stale 是入口页,不让 plate 放大 N 倍)
    lines_by_system: dict = {}
    stale: list[dict] = []
    for scen in rows:
        definition = definition_from_payload(scen.payload or {})
        meta_plate = (definition.get("meta") or {}).get("plate") or {}
        reasons: list[str] = []
        endpoints_used: dict = {}
        for st in (definition.get("steps") or []):
            if isinstance(st, dict) and st.get("endpoint"):
                eid = str(st["endpoint"])
                endpoints_used.setdefault(eid.split(".")[0], []).append(eid)
        resolvable = {s: ref for s, ref in meta_plate.items()
                      if ref and ref != "working"
                      and endpoints_used.get(s)}
        resolved: dict = {}
        if resolvable:
            try:
                resolved = await plate_client.resolve(
                    resolvable,
                    {s: endpoints_used[s] for s in resolvable})
            except Exception:  # noqa: BLE001 — plate 不可达:提示降级
                resolved = {}
        for sys_, ref in meta_plate.items():
            if ref == "working" or not ref:
                reasons.append(f"{sys_}: 仍为预览(working)")
                continue
            line = ref.split("#")[0]
            if sys_ not in lines_by_system:
                try:
                    lines_by_system[sys_] = await plate_client.list_lines(sys_)
                except Exception:  # noqa: BLE001
                    lines_by_system[sys_] = None
            lines = lines_by_system.get(sys_) or []
            line_names = [l.get("line") for l in lines]
            # 有新版本线:声明的线之后存在更新的线(按签发序)
            if line in line_names and line_names.index(line) < len(lines) - 1:
                newer = lines[-1].get("latest")
                reasons.append(
                    f"{sys_}: 有新版本线 {newer}")
            # 版本线已退役:没有任何环境声明该线
            declared_envs = [e.name for e in envs
                             if (e.lines or {}).get(sys_) == line]
            if not declared_envs and line_names and line in line_names:
                reasons.append(
                    f"{sys_}: 版本线 {line} 未被任何环境声明(已退役)")
            # 定义已修正:生效修订与已验证不同
            info = resolved.get(sys_) or {}
            eff = info.get("effective")
            if eff and eff != ref:
                reasons.append(
                    f"{sys_}: 定义已修正(生效修订 {eff} ≠ 已验证 {ref})")
        if not meta_plate:
            reasons.append("无版本声明(过渡期存量)")
        if reasons:
            stale.append({
                "scenario_id": scen.scenario_id,
                "name": (definition.get("meta") or {}).get("name", ""),
                "reasons": reasons,
            })
    return stale


async def save_as_copy(
    db, scenario_id: str, *, user, ops: list[dict],
    target_revision: str, batch_id: str | None = None,
) -> dict:
    """RS4a 保存为副本（Release v4.4 §5.6 ③）：原场景不动；新建副本 +
    应用方案 + meta.plate 设为目标修订 + forked_from + RunScheme 拷贝
    （copy_scenario 一并拷贝数据集与方案）。
    """
    from copy import deepcopy

    # 1. 副本底座：深拷贝场景 + 数据集 + RunScheme + forked_from 三件套
    copy = await scenario_store.copy_scenario(
        db, scenario_id,
        new_owner=user.display_name or user.username,
        new_owner_id=user.id,
        activity_kind="scenario.forked_for_adaptation",
        activity_detail={"from": scenario_id, "to_revision": target_revision,
                         "batch_id": batch_id},
    )
    new_sid = copy.meta.scenario_id
    new_row = await scenario_store.get_row(db, new_sid)
    if new_row is None:  # 理论不可达：copy_scenario 刚提交
        raise ValueError(f"copy of {scenario_id} vanished")

    # 2. 在副本上应用方案（统一路径:引用改写随 op 联动,H2）
    payload = deepcopy(new_row.payload or {})
    structure_kinds = _apply_ops_to_payload(payload, ops or [])
    definition = definition_from_payload(payload)

    # 3. meta.plate 设为目标修订（按 step.endpoint 的系统前缀分派）
    meta_plate = (definition.setdefault("meta", {}) or {}).setdefault("plate", {})
    for step in (definition.get("steps") or []):
        ep = step.get("endpoint")
        if ep:
            system = str(ep).split(".")[0]
            meta_plate[system] = target_revision
    if structure_kinds:
        await _clear_scheme_step_to(db, new_sid)   # R30:副本方案同步清空

    new_row.payload = payload
    await db.commit()
    return {"new_scenario_id": new_sid,
            "target_revision": target_revision}


async def notify_cross_owner(
    db, scenario_id: str, *, from_rev: str, to_rev: str, batch_id: str,
) -> int:
    """RS4a 跨所有者通知（Release v4.4 §5.9）：直接保存影响他人的
    Suite / 集成任务时，通知其所有者场景从哪个修订改到了哪个修订。
    """
    from app.models import Suite, IntegrationTask
    from app.services.notifications import create_notification

    # 1. 引用该场景的 Suite（mode_config.units 按 scenarioId 索引）
    suites = (await db.execute(select(Suite))).scalars().all()
    affected_suites = [
        s for s in suites
        if scenario_id in ((s.mode_config or {}).get("units") or {})
    ]

    # 2. 引用该场景的集成任务（scenario_id 列单场景引用）
    tasks = (await db.execute(
        select(IntegrationTask).where(
            IntegrationTask.scenario_id == scenario_id)
    )).scalars().all()

    # 3. 逐所有者发通知（同一人只收一条）
    sent = 0
    notified: set[int] = set()
    msg = f"场景 {scenario_id} 已从 {from_rev} 适配到 {to_rev}"

    for suite in affected_suites:
        owner = suite.owner_id
        if owner and owner not in notified:
            await create_notification(
                db, user_id=owner,
                type_="scenario.version_change",
                title=msg,
                body=f"Suite「{suite.name}」引用了该场景（批次 {batch_id}）",
                link=f"/adaptations/batches/{batch_id}")
            notified.add(owner)
            sent += 1

    for task in tasks:
        owner = task.holder_id or task.owner_id
        if owner and owner not in notified:
            await create_notification(
                db, user_id=owner,
                type_="scenario.version_change",
                title=msg,
                body=f"集成任务「{task.name}」引用了该场景（批次 {batch_id}）",
                link=f"/adaptations/batches/{batch_id}")
            notified.add(owner)
            sent += 1

    return sent
