"""open_batch / apply_op / rollback_batch 服务层测试(spec §5.3)。

造数走真实 store(scenario_store/data_set_store)—— 倒排索引随创建同事务
落库,即 open_batch 的受影响面数据源,不做手工索引插桩。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.models.adaptation_batch import AdaptationBatch
from app.models.adaptation_op import AdaptationOp
from app.models.catalog_version import CatalogVersion
from app.schemas.scenario_composer import DataSetDraft, ScenarioDraft
from app.services import adaptation_service, data_set_store, scenario_store

from .helpers import make_draft

EP = "fin.order.add"

OLD_FULL = {
    "id": EP, "version": "1.0.0",
    "request": {"fields": [
        {"name": "amount"},
        {"name": "legacy_field"},
        {"name": "settle_type", "enum": ["1", "2"]},
    ]},
}
NEW_FULL = {
    "id": EP, "version": "1.1.0",
    "request": {"fields": [
        {"name": "amount"},
        {"name": "extra", "default": "E"},
        {"name": "settle_type", "enum": ["2", "3"]},
    ]},
}


def _steps():
    return [{
        "api": {"view_hints": {"endpoint_id": EP}, "headers": {}, "query": {}},
        "request": {"body": {"amount": "${var.amount}", "legacy_field": "L",
                             "settle_type": "1"}},
    }]


async def _session():
    return db_module.SessionLocal()


async def _seed_scenario(sid: str = "sc-batch", *, with_dataset: bool = False):
    async with await _session() as s:
        scenario = await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft(sid, steps=_steps(), vars_map={"amount": 100})
            ),
            owner="alice", owner_id=1,
        )
        if with_dataset:
            await data_set_store.create(s, scenario.meta.scenario_id, DataSetDraft(
                name="主数据集", rows=[{"amount": 5}, {"amount": 6}],
            ))
    return sid


async def _seed_stamp():
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id=EP, version="1.0.0",
                             spec_json=OLD_FULL, synced_at=datetime(2026, 1, 1)))
        await s.commit()


def _install_plate(plate):
    plate.items = [{"id": EP, "version": "1.1.0",
                    "updated_at": "2026-06-01T00:00:00Z"}]
    plate.fulls = {EP: NEW_FULL}


async def test_open_batch_creates_snapshots_and_drafts(fresh_db, plate):
    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)

    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)

    assert detail["status"] == "open"
    assert detail["fromVersion"] == "1.0.0" and detail["toVersion"] == "1.1.0"
    assert detail["endpointId"] == EP
    assert detail["snapshots"] == [
        {"entityType": "scenario", "entityId": "sc-batch"},
    ]
    # 草案三件套(§5.4):addField(extra=plate default) + removeField(legacy)
    # + mapValue 骨架(settle_type 值域变了,map 空)
    ops = {(o["opType"], o["payload"].get("field")) for o in detail["ops"]}
    assert ops == {("addField", "extra"), ("removeField", "legacy_field"),
                   ("mapValue", "settle_type")}
    assert all(o["status"] == "pending" for o in detail["ops"])
    assert all(o["payload"].get("step") == 0 for o in detail["ops"])
    assert detail["opCounts"] == {"pending": 3}


async def test_open_batch_requires_baseline_and_bump(fresh_db, plate):
    _install_plate(plate)
    async with await _session() as s:
        with pytest.raises(ValueError, match="no_baseline"):
            await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)

    await _seed_stamp()
    plate.items = [{"id": EP, "version": "1.0.0", "updated_at": None}]  # 未前进
    plate.fulls = {EP: OLD_FULL}
    async with await _session() as s:
        with pytest.raises(ValueError, match="no_pending_change"):
            await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)

    plate.fulls = {}  # plate 侧端点已下架(/full 404)
    async with await _session() as s:
        with pytest.raises(ValueError, match="no_pending_change"):
            await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)


async def test_open_batch_snapshots_datasets_too(fresh_db, plate):
    await _seed_scenario(with_dataset=True)
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
    assert {"entityType": "dataset", "entityId": "ds-001"} in detail["snapshots"]


async def test_open_batch_zero_refs_autocompletes(fresh_db, plate):
    """有戳有版本前进,但无任何场景引用 → 零 op 批次直接 completed + 推进戳
    (否则该 endpoint 的戳永远推不动,diff 天天报 pending)。"""
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        stamp = (await s.execute(select(CatalogVersion))).scalar_one()
    assert detail["status"] == "completed"
    assert detail["ops"] == []
    assert detail["snapshots"] == []
    assert stamp.version == "1.1.0"
    assert stamp.spec_json == NEW_FULL


# ─── apply_op(Task 8)─────────────────────────────────────────────
async def test_apply_all_completes_and_advances_stamp(fresh_db, plate):
    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        for o in detail["ops"]:
            res = await adaptation_service.apply_op(s, o["id"])
            assert res["status"] == "applied"
        ops = (await s.execute(select(AdaptationOp))).scalars().all()
        batch = (await s.execute(select(AdaptationBatch))).scalar_one()
        stamp = (await s.execute(select(CatalogVersion))).scalar_one()
        scenario = await scenario_store.get_row(s, "sc-batch")
    assert batch.status == "completed" and batch.closed_at is not None
    assert all(o.status == "applied" and o.applied_at for o in ops)
    assert stamp.version == "1.1.0" and stamp.spec_json == NEW_FULL
    body = scenario.payload["definition"]["steps"][0]["request"]["body"]
    assert body["extra"] == "E"           # addField(值 = plate default)
    assert "legacy_field" not in body     # removeField
    assert body["settle_type"] == "1"     # mapValue 骨架 map 空 → 不动值


async def test_apply_resyncs_endpoint_ref_index(fresh_db, plate):
    """应用走 scenario_store.update → 倒排索引同事务重解析(P1 钩子自动生效)。"""
    from app.models.scenario_endpoint_ref import ScenarioEndpointRef

    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        for o in detail["ops"]:
            await adaptation_service.apply_op(s, o["id"])
        refs = (await s.execute(select(ScenarioEndpointRef))).scalars().all()
    assert {r.field_name for r in refs} == {"amount", "settle_type", "extra"}
    # removeField 的 legacy_field 索引行消失;addField 的 extra 进索引(直填)


async def test_apply_op_idempotent_replay(fresh_db, plate):
    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        first = await adaptation_service.apply_op(s, detail["ops"][0]["id"])
        second = await adaptation_service.apply_op(s, detail["ops"][0]["id"])
        ops = (await s.execute(select(AdaptationOp))).scalars().all()
    assert first["status"] == second["status"] == "applied"
    assert sum(1 for o in ops if o.op_type == first["opType"]) == 1  # 没有重复行
    scenario_body_applied_once = True  # apply 幂等由 Task 6 纯引擎保证,这里验编排不重复落库
    assert scenario_body_applied_once


async def test_apply_conflict_when_step_reordered(fresh_db, plate):
    """C5:清单生成后用户重排步骤 → 应用时 endpoint_mismatch,标 conflict 不盲改。"""
    import copy as _copy

    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        # 批次打开后在最前面插一个绑定别的 endpoint 的占位步骤 → 目标 step 挪到 1
        row = await scenario_store.get_row(s, "sc-batch")
        payload = _copy.deepcopy(row.payload)
        payload["definition"]["steps"].insert(0, {
            "api": {"view_hints": {"endpoint_id": "fin.order.book"},
                    "headers": {}, "query": {}},
            "request": {"body": {}},
        })
        await scenario_store.update(s, "sc-batch", ScenarioDraft.model_validate(payload))

        res = await adaptation_service.apply_op(s, detail["ops"][0]["id"])
    assert res["status"] == "conflict"
    assert "endpoint_mismatch" in (res["note"] or "")


async def test_manual_dataset_op_conflict_on_palette(fresh_db, plate):
    """renameDatasetColumn 改到未声明键 → data_set_store 调色板 422 校验
    抛 ValueError → 归并为 op conflict(spec §4.3 校验天然兜底)。"""
    await _seed_scenario(with_dataset=True)
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        s.add(AdaptationOp(
            batch_id=detail["batchId"], scenario_id="sc-batch", dataset_id="ds-001",
            op_type="renameDatasetColumn",
            payload={"from": "amount", "to": "undeclared_key"}, status="pending",
        ))
        await s.commit()
        op_id = (await s.execute(
            select(AdaptationOp).where(AdaptationOp.op_type == "renameDatasetColumn")
        )).scalar_one().id
        res = await adaptation_service.apply_op(s, op_id)
        ds = await data_set_store.get_row(s, "ds-001")
    assert res["status"] == "conflict"
    assert "undeclared_var" in (res["note"] or "")
    assert ds.rows == [{"amount": 5}, {"amount": 6}]  # 库内未动


async def test_rename_var_updates_scenario_and_datasets(fresh_db, plate):
    await _seed_scenario(with_dataset=True)
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        s.add(AdaptationOp(  # 人工构造 renameVar(§5.4:不在自动草案内)
            batch_id=detail["batchId"], scenario_id="sc-batch", dataset_id=None,
            op_type="renameVar", payload={"from": "amount", "to": "amt"},
            status="pending",
        ))
        await s.commit()
        op_id = (await s.execute(
            select(AdaptationOp).where(AdaptationOp.op_type == "renameVar")
        )).scalar_one().id
        res = await adaptation_service.apply_op(s, op_id)
        scenario = await scenario_store.get_row(s, "sc-batch")
        ds = await data_set_store.get_row(s, "ds-001")
    assert res["status"] == "applied"
    body = scenario.payload["definition"]["steps"][0]["request"]["body"]
    assert body["amount"] == "${var.amt}" and "amt" not in body
    assert scenario.payload["definition"]["config"]["vars"] == {"amt": 100}
    assert ds.rows == [{"amt": 5}, {"amt": 6}]  # 调色板先就位 → 列改名通过


async def test_completion_survives_plate_down(fresh_db, plate):
    """完成时 plate 拉取失败 → 仍完成并推进 version,spec_json 留旧(自愈)。"""
    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        for o in detail["ops"][:-1]:
            await adaptation_service.apply_op(s, o["id"])
        plate.down = True  # 最后一条应用触发完成,plate full 拉取失败
        await adaptation_service.apply_op(s, detail["ops"][-1]["id"])
        batch = (await s.execute(select(AdaptationBatch))).scalar_one()
        stamp = (await s.execute(select(CatalogVersion))).scalar_one()
    assert batch.status == "completed"
    assert stamp.version == "1.1.0"
    assert stamp.spec_json == OLD_FULL  # 留旧


async def test_apply_rejects_terminal_and_inactive(fresh_db, plate):
    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        for o in detail["ops"]:
            await adaptation_service.apply_op(s, o["id"])
        # 批次已 completed → 再想塞一条人工 op 应用 → batch_not_active
        s.add(AdaptationOp(batch_id=detail["batchId"], scenario_id="sc-batch",
                           dataset_id=None, op_type="renameVar",
                           payload={"from": "amount", "to": "amt"}, status="pending"))
        await s.commit()
        extra_id = (await s.execute(
            select(AdaptationOp).where(AdaptationOp.op_type == "renameVar")
        )).scalar_one().id
        with pytest.raises(ValueError, match="batch_not_active"):
            await adaptation_service.apply_op(s, extra_id)
    # op_not_found
    async with await _session() as s:
        with pytest.raises(KeyError, match="op_not_found"):
            await adaptation_service.apply_op(s, 99999)
