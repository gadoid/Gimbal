"""carry 漂移 diff(spec §7)— plate 面 vs 两表 paths 三类结果。"""
from __future__ import annotations

from app.core import db as db_module
from app.services import carry_store

from .test_carry_api import _admin


async def _seed():
    async with db_module.SessionLocal() as db:
        # fin-service:$.old 绑了但 plate 面已无(orphaned);
        # $.new 面上有但没绑(uncovered);$.remark 面上有且有绑(对齐)
        await carry_store.put_bindings(
            db, "fin-service", {"$.old": "x", "$.remark": "r"}, "alice")
        await db.commit()


async def test_drift_three_classes(client, plate):
    await _seed()
    plate.items = [{"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
                    "service": "fin-service"}]
    plate.fulls = {"fin.ep1": {"request": {"carry": {
        "$.remark": {"type": "string"},
        "$.new": {"type": "string"}}}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    assert r.status_code == 200, r.text
    services = r.json()["services"]
    fin = next(s for s in services if s["service"] == "fin-service")
    assert fin["orphaned"] == ["$.old"]
    assert sorted(fin["uncovered"]) == ["$.new"]
    # 单 orphaned × 单 uncovered(同 string)→ rename 建议
    assert fin["renamedSuggestions"] == [{"from": "$.old", "to": "$.new"}]


async def test_drift_empty_when_aligned(client, plate):
    await _seed()
    plate.items = [{"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
                    "service": "fin-service"}]
    plate.fulls = {"fin.ep1": {"request": {"carry": {
        "$.remark": {"type": "string"}, "$.old": {"type": "string"}}}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    fin = next(s for s in r.json()["services"] if s["service"] == "fin-service")
    assert fin["orphaned"] == [] and fin["uncovered"] == []
