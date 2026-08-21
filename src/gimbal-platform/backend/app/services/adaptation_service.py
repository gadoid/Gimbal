"""变更适配编排(spec §5):目录 diff / 影响查询 / 批次生命周期。

plate 目录是接口契约权威;本模块把"plate 现状"与平台基线戳
(``catalog_versions``)对齐,产出待适配/异常清单,并编排适配批次
(存档 → 草案 → 逐条应用 → 完成/回滚)。
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.adaptation_batch import AdaptationBatch
from ..models.adaptation_op import AdaptationOp
from ..models.adaptation_snapshot import AdaptationSnapshot
from ..models.catalog_version import CatalogVersion
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..models.scenario_endpoint_ref import ScenarioEndpointRef
from ..schemas.scenario_composer import DataSetDraft, ScenarioDraft
from . import data_set_store, plate_client, scenario_store
from .adaptation_ops import (
    DATASET_OPS,
    STEP_OPS,
    apply_to_definition,
    apply_to_rows,
    check_step_addressable,
    diff_field_specs,
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
    """GET /api/endpoint/{id}/full → data.item;plate 404 → None(端点已下架)。"""
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


# ─── 版本/时间比较 ────────────────────────────────────────────────
def _semver_key(version: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(p) for p in version.strip().split("."))
    except ValueError:
        return None


def _semver_gt(a: str, b: str) -> bool:
    """a 严格高于 b。双侧可解析 → 元组数值比较;否则退化为字典序,
    且仅"确实不同"才算前进(避免怪版本号误报 pending)。"""
    ka, kb = _semver_key(a), _semver_key(b)
    if ka is not None and kb is not None:
        return ka > kb
    return a != b and a > b


def _parse_dt(value) -> datetime | None:
    """plate 侧 ISO 时间(可带 Z / +00:00)→ naive-UTC;解析失败 → None。"""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _utcnow() -> datetime:
    """naive-UTC(与 _parse_dt 同基准;SQLite CURRENT_TIMESTAMP 亦为 UTC)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── 检测:目录 diff(spec §5.1)─────────────────────────────────
async def catalog_diff(db: AsyncSession) -> dict:
    """全量拉取 plate 目录,逐 endpoint 对戳。

    * 首见(库内无戳)→ 拉全量 spec 落基线戳 + spec_json(幂等,
      不算待适配、不建批次);列表有但 /full 404 → full_unavailable 异常;
    * plate version 严格高于戳 → pending;
    * version 相同但 plate updated_at > synced_at → C12「忘 bump」异常;
    * 库内有戳但 plate 列表无此 endpoint → missing_on_plate 异常。

    基线落库是写副作用,末尾单次 commit —— 路由层因此用 POST。
    """
    items = await _plate_list_endpoints()
    stamps: dict[str, CatalogVersion] = {
        row.endpoint_id: row
        for row in (await db.execute(select(CatalogVersion))).scalars()
    }
    pending: list[dict] = []
    anomalies: list[dict] = []
    baselined = 0
    for it in sorted(items, key=lambda x: str(x.get("id") or "")):
        eid = str(it.get("id") or "")
        ver = str(it.get("version") or "")
        if not eid:
            continue
        stamp = stamps.pop(eid, None)
        if stamp is None:
            full = await _plate_full_endpoint(eid)
            if full is None:  # 列表有、full 404:plate 自身状态不一致
                anomalies.append({
                    "endpointId": eid, "reason": "full_unavailable",
                    "detail": "plate list has endpoint but /full returned 404",
                })
                continue
            db.add(CatalogVersion(
                endpoint_id=eid, version=ver,
                spec_json=full, synced_at=_utcnow(),
            ))
            baselined += 1
            continue
        if _semver_gt(ver, stamp.version):
            pending.append({
                "endpointId": eid,
                "fromVersion": stamp.version, "toVersion": ver,
            })
            continue
        updated = _parse_dt(it.get("updated_at"))
        if ver == stamp.version and updated is not None and updated > stamp.synced_at:
            anomalies.append({
                "endpointId": eid, "reason": "updated_without_bump",
                "detail": (
                    f"plate updated_at {updated.isoformat()}"
                    f" > synced_at {stamp.synced_at.isoformat()}"
                ),
            })
    for eid in sorted(stamps):  # 库内残留、plate 已下架
        anomalies.append({
            "endpointId": eid, "reason": "missing_on_plate",
            "detail": "catalog stamp exists but plate no longer lists this endpoint",
        })
    await db.commit()
    return {"pending": pending, "anomalies": anomalies, "baselinedNow": baselined}


# ─── 影响查询(spec §5.2)────────────────────────────────────────
async def impact(
    db: AsyncSession, endpoint_id: str, field_name: str | None = None
) -> list[dict]:
    """endpoint(可选再按 field)→ 受影响清单条目(spec §5.2)。

    直填字段同样命中(索引行按字段键存在,与值是否模板无关);
    via_var 条目按数据集行实际含键(内存列存在性,D5 —— 不建
    dataset_columns 表)配对;无数据集命中时仍出一条 datasetId=None
    (变量默认值通路,D9 基线 = 直填 ∪ vars 扁平值)。
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
    if not refs:
        return []
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
        entry = {
            "scenarioId": r.scenario_id, "stepIndex": r.step_index,
            "source": r.source, "field": r.field_name, "viaVar": r.via_var,
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


# ─── 批次生命周期:开批次(spec §5.3)────────────────────────────
async def open_batch(
    db: AsyncSession, *, endpoint_id: str, operator_id: int
) -> dict:
    """开适配批次:校验有基线且版本确实前进 → 存档受影响实体 →
    生成自动草案 → 建 batch + ops(全部 pending)。

    * 无基线戳 → ValueError("no_baseline")(先 POST /adaptations/catalog/diff);
    * plate 版本未前进 / 端点已下架 → ValueError("no_pending_change");
    * 草案展开:addField → 该 endpoint 全部 (scenario, step) 引用对;
      removeField/mapValue → 仅实际引用该字段的引用对(集合去重);
    * 零 op(无引用或形状无 diff)→ 直接 completed + 推进戳。
    """
    stamp = (await db.execute(
        select(CatalogVersion).where(CatalogVersion.endpoint_id == endpoint_id)
    )).scalar_one_or_none()
    if stamp is None:
        raise ValueError(
            f"no_baseline: {endpoint_id} — run POST /adaptations/catalog/diff first"
        )
    full = await _plate_full_endpoint(endpoint_id)
    if full is None:
        raise ValueError(f"no_pending_change: {endpoint_id} missing on plate")
    to_version = str(full.get("version") or "")
    if not _semver_gt(to_version, stamp.version):
        raise ValueError(
            f"no_pending_change: plate {to_version} not ahead of {stamp.version}"
        )

    refs = (await db.execute(
        select(ScenarioEndpointRef).where(
            ScenarioEndpointRef.endpoint_id == endpoint_id
        ).order_by(
            ScenarioEndpointRef.scenario_id, ScenarioEndpointRef.step_index,
            ScenarioEndpointRef.source, ScenarioEndpointRef.field_name,
        )
    )).scalars().all()

    scenario_rows: dict[str, ComposerScenario] = {}
    for sid in sorted({r.scenario_id for r in refs}):
        row = await scenario_store.get_row(db, sid)
        if row is not None:
            scenario_rows[sid] = row

    batch_id = f"bt-{uuid4().hex[:12]}"
    db.add(AdaptationBatch(
        batch_id=batch_id, endpoint_id=endpoint_id,
        from_version=stamp.version, to_version=to_version,
        status="open", operator_id=operator_id,
    ))
    # 存档:受影响场景的完整容器 payload + 其全部数据集(回滚安全网)
    for sid, row in scenario_rows.items():
        db.add(AdaptationSnapshot(
            batch_id=batch_id, entity_type="scenario", entity_id=sid,
            before_json={"payload": copy.deepcopy(row.payload or {})},
        ))
    if scenario_rows:
        ds_rows = (await db.execute(
            select(ComposerDataSet).where(
                ComposerDataSet.scenario_id.in_(sorted(scenario_rows))
            )
        )).scalars().all()
    else:
        ds_rows = []
    for d in ds_rows:
        db.add(AdaptationSnapshot(
            batch_id=batch_id, entity_type="dataset", entity_id=d.dataset_id,
            before_json={
                "scenarioId": d.scenario_id, "name": d.name,
                "description": d.description,
                "rows": copy.deepcopy(d.rows or []),
            },
        ))

    # 自动草案展开(§5.4 收窄):payload 不含 "op"(类型在 op_type 列)
    drafts = diff_field_specs(stamp.spec_json or {}, full)
    pairs = sorted({(r.scenario_id, r.step_index) for r in refs})
    op_count = 0
    for draft in drafts:
        kind, field = draft["op"], draft.get("field")
        if kind == "addField":
            targets = pairs  # 新字段:全部引用位都要补
        else:  # removeField / mapValue:仅实际引用该字段的 step
            targets = sorted({(r.scenario_id, r.step_index)
                              for r in refs if r.field_name == field})
        for sid, step_index in targets:
            db.add(AdaptationOp(
                batch_id=batch_id, scenario_id=sid, dataset_id=None,
                op_type=kind,
                payload={k: v for k, v in draft.items() if k != "op"}
                | {"step": step_index},
                status="pending",
            ))
            op_count += 1

    if op_count == 0:  # 零 op:直接完成并推进戳
        batch = await _get_batch(db, batch_id)
        batch.status = "completed"
        batch.closed_at = _utcnow()
        await _advance_stamp(
            db, endpoint_id=endpoint_id, to_version=to_version, full=full,
        )
    await db.commit()
    return await _batch_detail(db, batch_id)


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


async def _batch_detail(db: AsyncSession, batch_id: str) -> dict:
    """批次详情 dict(camelCase)—— open_batch / get_batch_detail 共用,
    Task 10 的 BatchDetail 响应模型按此形状校验。"""
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
    return {
        "batchId": batch.batch_id, "endpointId": batch.endpoint_id,
        "fromVersion": batch.from_version, "toVersion": batch.to_version,
        "status": batch.status, "operatorId": batch.operator_id,
        "createdAt": batch.created_at, "closedAt": batch.closed_at,
        "opCounts": counts,
        "ops": [_op_out(op) for op in ops],
        "snapshots": [
            {"entityType": s.entity_type, "entityId": s.entity_id}
            for s in snapshots
        ],
    }


async def _advance_stamp(
    db: AsyncSession, *, endpoint_id: str, to_version: str, full: dict | None
) -> None:
    """批次完成时推进基线戳(spec §3.3)。调用方负责 commit。

    full=None(完成时 plate 拉取失败)→ 只推进 version + synced_at,
    spec_json 留旧 —— 形状基准滞后由下一次 diff 的版本/C12 语义自愈。
    """
    stamp = (await db.execute(
        select(CatalogVersion).where(CatalogVersion.endpoint_id == endpoint_id)
    )).scalar_one_or_none()
    if stamp is None:  # 理论不可达(开批次前必须有戳);防御性兜底
        stamp = CatalogVersion(endpoint_id=endpoint_id, version="", spec_json={})
        db.add(stamp)
    stamp.version = to_version
    if full is not None:
        stamp.spec_json = full
    stamp.synced_at = _utcnow()


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
        if op.op_type in DATASET_OPS:
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
    ))


async def _maybe_complete(db: AsyncSession, batch: AdaptationBatch) -> None:
    """无 pending 剩余 → completed + 推进戳。plate full 拉取 best-effort。"""
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
    try:
        full = await _plate_full_endpoint(batch.endpoint_id)
    except PlateUnavailableError:
        full = None
    await _advance_stamp(
        db, endpoint_id=batch.endpoint_id,
        to_version=batch.to_version, full=full,
    )


# ─── 批次生命周期:整批回滚(spec §5.3 乐观冲突)─────────────────
class _RollbackConflict(Exception):
    """回滚乐观冲突:实体被批次外编辑 / 重放失败 / 实体消失。"""


async def rollback_batch(db: AsyncSession, batch_id: str) -> dict:
    """整批回滚:期望态 = before + applied ops 内存重放(收敛幂等 ⇒ 重放可行)。

    场景先于数据集恢复(renameVar 对称序);当前态 ≠ 期望态 → 该实体
    conflict 跳过不盲写;pending ops → skipped;戳不推进。
    """
    batch = await _get_batch(db, batch_id)
    if batch.status not in ("open", "applying"):
        raise ValueError(f"batch_not_rollbackable: {batch.status}")

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

    for snap in _snap("scenario"):  # 场景先恢复
        try:
            await _rollback_scenario(db, batch, snap, applied_ops)
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

    for op in (await db.execute(
        select(AdaptationOp).where(
            AdaptationOp.batch_id == batch_id,
            AdaptationOp.status == "pending",
        )
    )).scalars():
        op.status = "skipped"
        op.note = "batch rolled back"
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
) -> None:
    row = await scenario_store.get_row(db, snap.entity_id)
    if row is None:
        raise _RollbackConflict(
            "scenario_missing: entity deleted after batch opened"
        )
    before = copy.deepcopy((snap.before_json or {}).get("payload") or {})
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
    await scenario_store.update(
        db, snap.entity_id, ScenarioDraft.model_validate(before)
    )


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
    try:
        for op in applied_ops:
            op_view = {"op": op.op_type, **(op.payload or {})}
            if (op.op_type == "renameVar"
                    and op.scenario_id == before.get("scenarioId")):
                expected_rows = apply_to_rows(expected_rows, op_view)
            elif op.op_type in DATASET_OPS and op.dataset_id == snap.entity_id:
                expected_rows = apply_to_rows(expected_rows, op_view)
    except (KeyError, ValueError) as e:
        raise _RollbackConflict(f"replay_failed: {e}") from e
    current = {"name": d.name, "description": d.description,
               "rows": d.rows or []}
    if current != {"name": before.get("name"),
                   "description": before.get("description"),
                   "rows": expected_rows}:
        raise _RollbackConflict(
            "edited_beyond_batch: current != before+ops replay"
        )
    await data_set_store.update(db, snap.entity_id, DataSetDraft(
        name=before.get("name") or d.name,
        description=before.get("description") or "",
        rows=before.get("rows") or [],
    ))
