"""catalog_diff 服务测试(spec §5.1):

冷启动基线(幂等)/ 版本前进 pending / C12 忘 bump 异常 /
plate 下架残留戳异常 / full 404 异常 / plate 不可达。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.models.catalog_version import CatalogVersion
from app.services.adaptation_service import catalog_diff
from app.services.plate_client import PlateUnavailableError

FULL = {
    "id": "fin.order.add", "version": "1.0.0",
    "request": {"declarations": [
        {"name": "amount", "state": "form", "enum": None}]},
}


async def _session():
    return db_module.SessionLocal()


async def test_cold_start_baselines_then_idempotent(fresh_db, plate):
    plate.items = [
        {"id": "fin.order.add", "version": "1.0.0",
         "updated_at": "2026-01-01T00:00:00Z"},
        {"id": "fin.order.book", "version": "2.0.0", "updated_at": None},
    ]
    plate.fulls = {
        "fin.order.add": FULL,
        "fin.order.book": {**FULL, "id": "fin.order.book"},
    }

    async with await _session() as s:
        report = await catalog_diff(s)
    assert report == {"pending": [], "anomalies": [], "baselinedNow": 2}

    async with await _session() as s:  # 第二次:已基线 → 幂等无 pending
        report2 = await catalog_diff(s)
    assert report2 == {"pending": [], "anomalies": [], "baselinedNow": 0}

    async with await _session() as s:
        stamps = {
            r.endpoint_id: r
            for r in (await s.execute(select(CatalogVersion))).scalars()
        }
    assert stamps["fin.order.add"].version == "1.0.0"
    assert stamps["fin.order.add"].spec_json["id"] == "fin.order.add"
    assert stamps["fin.order.book"].version == "2.0.0"


async def test_version_bump_pending(fresh_db, plate):
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.add", version="1.0.0",
                             spec_json=FULL, synced_at=datetime(2026, 1, 1)))
        await s.commit()
    plate.items = [{"id": "fin.order.add", "version": "1.1.0",
                    "updated_at": "2026-06-01T00:00:00Z"}]
    async with await _session() as s:
        report = await catalog_diff(s)
    assert report["baselinedNow"] == 0
    assert report["anomalies"] == []
    assert report["pending"] == [{
        "endpointId": "fin.order.add",
        "fromVersion": "1.0.0", "toVersion": "1.1.0",
    }]


async def test_c12_updated_without_bump(fresh_db, plate):
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.add", version="1.0.0",
                             spec_json=FULL, synced_at=datetime(2026, 1, 1)))
        await s.commit()
    plate.items = [{"id": "fin.order.add", "version": "1.0.0",   # 版本没动
                    "updated_at": "2026-02-02T00:00:00Z"}]        # 但 plate 改过
    async with await _session() as s:
        report = await catalog_diff(s)
    assert report["pending"] == []
    assert report["baselinedNow"] == 0
    (anomaly,) = report["anomalies"]
    assert anomaly["endpointId"] == "fin.order.add"
    assert anomaly["reason"] == "updated_without_bump"


async def test_missing_on_plate_and_full_404(fresh_db, plate):
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.gone", version="1.0.0",
                             spec_json={}, synced_at=datetime(2026, 1, 1)))
        await s.commit()
    plate.items = [{"id": "fin.order.ghost", "version": "1.0.0",
                    "updated_at": "2026-01-01T00:00:00Z"}]
    # fulls 为空 → fin.order.ghost 的 /full 404 → full_unavailable
    async with await _session() as s:
        report = await catalog_diff(s)
    reasons = {a["endpointId"]: a["reason"] for a in report["anomalies"]}
    assert reasons == {
        "fin.order.gone": "missing_on_plate",
        "fin.order.ghost": "full_unavailable",
    }


async def test_plate_unavailable(fresh_db, plate):
    plate.down = True
    async with await _session() as s:
        with pytest.raises(PlateUnavailableError):
            await catalog_diff(s)
