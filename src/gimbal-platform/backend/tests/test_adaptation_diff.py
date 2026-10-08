"""catalog_diff 服务测试(spec §5.1):

冷启动基线(幂等)/ 旧 semver 戳重落基线(R6④)/ shape_hash 变化 pending /
plate 下架残留戳异常 / full 404 异常 / plate 不可达。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.models.catalog_version import CatalogVersion
from app.services.adaptation_service import catalog_diff
from app.services.plate_client import PlateUnavailableError

# 8m 迁移后的真实形态:轻列表带 shape_hash,戳 version 列存 64-hex 指纹
H1 = "aa" * 32
H2 = "bb" * 32
FULL = {
    "id": "fin.order.add", "shape_hash": H1,
    "request": {"declarations": [
        {"name": "amount", "state": "form", "enum": None}]},
}


async def _session():
    return db_module.SessionLocal()


async def test_cold_start_baselines_then_idempotent(fresh_db, plate):
    plate.items = [
        {"id": "fin.order.add", "shape_hash": H1},
        {"id": "fin.order.book", "shape_hash": H2},
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
    assert stamps["fin.order.add"].version == H1
    assert stamps["fin.order.add"].spec_json["id"] == "fin.order.add"
    assert stamps["fin.order.book"].version == H2


async def test_legacy_semver_stamp_rebaselined(fresh_db, plate):
    """R6④:未跑 8m 迁移的环境(旧 semver 戳)按首见基线重落,
    不产生 149 个假 pending;/full 404 才走异常。"""
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.add", version="1.1.0",
                             spec_json={"legacy": True},
                             synced_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        await s.commit()
    plate.items = [{"id": "fin.order.add", "shape_hash": H1}]
    plate.fulls = {"fin.order.add": FULL}
    async with await _session() as s:
        report = await catalog_diff(s)
    assert report == {"pending": [], "anomalies": [], "baselinedNow": 1}
    async with await _session() as s:
        stamps = {
            r.endpoint_id: r
            for r in (await s.execute(select(CatalogVersion))).scalars()
        }
    assert stamps["fin.order.add"].version == H1
    assert stamps["fin.order.add"].spec_json["id"] == "fin.order.add"


async def test_legacy_semver_with_field_drift_kept_pending(fresh_db, plate):
    """N3:旧戳 spec_json 携带形状缓存且与真源有漂移(字段被删)时,
    保留为待适配——不静默重落吞掉本应出现的 removeField。"""
    drifted_old = {
        "id": "fin.order.add", "shape_hash": H1,
        "request": {"declarations": [
            {"name": "amount", "state": "form", "enum": None},
            {"name": "gone_later", "path": "$.gone", "type": "string"},
        ]},
    }
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.add", version="1.1.0",
                             spec_json=drifted_old,
                             synced_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        await s.commit()
    plate.items = [{"id": "fin.order.add", "shape_hash": H1}]
    plate.fulls = {"fin.order.add": FULL}
    async with await _session() as s:
        report = await catalog_diff(s)
    assert report["baselinedNow"] == 0
    assert report["pending"] == [{
        "endpointId": "fin.order.add",
        "fromVersion": "1.1.0", "toVersion": H1[:8],
    }]
    async with await _session() as s:   # 戳未被覆盖,漂移证据保留
        stamp = (await s.execute(select(CatalogVersion))).scalars().first()
        assert stamp.version == "1.1.0"
        assert stamp.spec_json == drifted_old


async def test_legacy_semver_without_shape_cache_rebaselined(fresh_db, plate):
    """N3 对照:旧戳无形状缓存(空 spec_json)没有可比对物——
    静默重落(否则 diff_field_specs 会把全部字段误判为新增)。"""
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.add", version="1.1.0",
                             spec_json={},
                             synced_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        await s.commit()
    plate.items = [{"id": "fin.order.add", "shape_hash": H1}]
    plate.fulls = {"fin.order.add": FULL}
    async with await _session() as s:
        report = await catalog_diff(s)
    assert report == {"pending": [], "anomalies": [], "baselinedNow": 1}


async def test_shape_hash_change_pending(fresh_db, plate):
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.add", version=H1,
                             spec_json=FULL, synced_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        await s.commit()
    # A2:shape_hash 门(hash 变 = pending;from/to 显示为指纹前缀)
    plate.items = [{"id": "fin.order.add", "shape_hash": H2}]
    async with await _session() as s:
        report = await catalog_diff(s)
    assert report["baselinedNow"] == 0
    assert report["anomalies"] == []
    assert report["pending"] == [{
        "endpointId": "fin.order.add",
        "fromVersion": H1[:8], "toVersion": H2[:8],
    }]


async def test_same_shape_no_pending(fresh_db, plate):
    """A2/修订九:C12「updated_without_bump」异常类消灭——shape 相同即无变更,
    plate 重启假时间戳不再触发误报(hash 门天然覆盖「改了忘 bump」)。"""
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.add", version=H1,
                             spec_json=FULL, synced_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        await s.commit()
    plate.items = [{"id": "fin.order.add", "shape_hash": H1}]
    async with await _session() as s:
        report = await catalog_diff(s)
    assert report["pending"] == []
    assert report["baselinedNow"] == 0
    assert report["anomalies"] == []


async def test_missing_on_plate_and_full_404(fresh_db, plate):
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.gone", version=H1,
                             spec_json={}, synced_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        await s.commit()
    plate.items = [{"id": "fin.order.ghost", "shape_hash": H2}]
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
