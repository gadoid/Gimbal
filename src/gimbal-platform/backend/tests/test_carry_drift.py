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
    plate.fulls = {"fin.ep1": {"request": {"declarations": [
        {"path": "$.remark", "channel": "carry", "type": "string"},
        {"path": "$.new", "channel": "carry", "type": "string"}]}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["plateReachable"] is True
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
    plate.fulls = {"fin.ep1": {"request": {"declarations": [
        {"path": "$.remark", "channel": "carry", "type": "string"},
        {"path": "$.old", "channel": "carry", "type": "string"}]}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    fin = next(s for s in r.json()["services"] if s["service"] == "fin-service")
    assert fin["orphaned"] == [] and fin["uncovered"] == []


async def test_drift_plate_down_flags_and_degrades(client, plate):
    """plate 列表不可达 → plateReachable=False + face 空集降级
    (绑定全成 orphaned)— 面板先看信号再渲染,防不可达被误读成漂移。"""
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.old": "x"}, "alice")
        await db.commit()
    plate.down = True
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plateReachable"] is False
    fin = next(s for s in body["services"] if s["service"] == "fin-service")
    assert fin["orphaned"] == ["$.old"]


async def test_drift_no_rename_suggestion_when_multiple_candidates(client, plate):
    """2 orphaned × 2 uncovered → 不猜配对(多候选负分支)。"""
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.old": "x", "$.old2": "y"}, "alice")
        await db.commit()
    plate.items = [{"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
                    "service": "fin-service"}]
    plate.fulls = {"fin.ep1": {"request": {"declarations": [
        {"path": "$.new", "channel": "carry", "type": "string"},
        {"path": "$.new2", "channel": "carry", "type": "string"}]}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    assert r.status_code == 200, r.text
    fin = next(s for s in r.json()["services"] if s["service"] == "fin-service")
    assert fin["renamedSuggestions"] == []
