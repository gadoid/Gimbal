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
