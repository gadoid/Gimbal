"""四张派生表的形状冒烟:建表、复合 PK 唯一性、JSON 列往返。"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import db as db_module
from app.models.adaptation_batch import AdaptationBatch
from app.models.adaptation_snapshot import AdaptationSnapshot
from app.models.catalog_version import CatalogVersion
from app.models.scenario_endpoint_ref import ScenarioEndpointRef


async def _session():
    return db_module.SessionLocal()


@pytest.mark.filterwarnings("ignore:New instance.*:sqlalchemy.exc.SAWarning")
async def test_endpoint_ref_roundtrip_and_pk(fresh_db):
    async with await _session() as s:
        s.add(ScenarioEndpointRef(
            scenario_id="sc-a", step_index=0, source="body",
            field_name="amount", endpoint_id="fin.order.add", via_var="amount",
        ))
        s.add(ScenarioEndpointRef(  # 同字段名不同 source → 不撞 PK
            scenario_id="sc-a", step_index=0, source="headers",
            field_name="amount", endpoint_id="fin.order.add", via_var=None,
        ))
        await s.commit()
        rows = (await s.execute(select(ScenarioEndpointRef))).scalars().all()
        assert {(r.source, r.field_name, r.via_var) for r in rows} == {
            ("body", "amount", "amount"), ("headers", "amount", None),
        }
        s.add(ScenarioEndpointRef(  # 完整 PK 重复 → IntegrityError
            scenario_id="sc-a", step_index=0, source="body",
            field_name="amount", endpoint_id="fin.order.add",
        ))
        with pytest.raises(IntegrityError):
            await s.commit()
        await s.rollback()


async def test_catalog_batch_snapshot_roundtrip(fresh_db):
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.add", version="1.0.0"))
        s.add(AdaptationBatch(
            batch_id="bt-1", endpoint_id="fin.order.add",
            from_version="1.0.0", to_version="1.1.0",
            status="open", operator_id=1,
        ))
        await s.commit()
        s.add(AdaptationSnapshot(
            batch_id="bt-1", entity_type="scenario",
            entity_id="sc-a", before_json={"definition": {"steps": []}},
        ))
        await s.commit()
        snap = (await s.execute(select(AdaptationSnapshot))).scalar_one()
        assert snap.before_json["definition"]["steps"] == []
