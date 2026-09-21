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
            db, "fin-service", {"$.old": "x", "$.remark": "r"},
            updated_by_id=None, updated_by_name="alice")
        await db.commit()


async def test_drift_three_classes(client, plate):
    await _seed()
    plate.items = [{"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
                    "service": "fin-service"}]
    plate.fulls = {"fin.ep1": {"request": {"declarations": [
        {"path": "$.remark", "state": "carry", "type": "string"},
        {"path": "$.new", "state": "carry", "type": "string"}]}}}
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
        {"path": "$.remark", "state": "carry", "type": "string"},
        {"path": "$.old", "state": "carry", "type": "string"}]}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    fin = next(s for s in r.json()["services"] if s["service"] == "fin-service")
    assert fin["orphaned"] == [] and fin["uncovered"] == []


async def test_drift_plate_down_flags_and_degrades(client, plate):
    """plate 列表不可达 → plateReachable=False + face 空集降级
    (绑定全成 orphaned)— 面板先看信号再渲染,防不可达被误读成漂移。"""
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.old": "x"}, updated_by_id=None, updated_by_name="alice")
        await db.commit()
    plate.down = True
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plateReachable"] is False
    fin = next(s for s in body["services"] if s["service"] == "fin-service")
    assert fin["orphaned"] == ["$.old"]


async def test_drift_alias_key_diffed_against_base_face(client, plate):
    """键归一(配套方案 §2.3):别名键绑定的行对 base 的面做 diff——
    只报 orphaned(uncovered 是 base 行的事),baseService 标注归一
    关系。修复前别名键 face 恒空 → 全量误报 orphaned,且经漂移面板
    会生成「删光别名绑定」的批次草案。"""
    async with db_module.SessionLocal() as db:
        # base 行:$.ok 对齐;别名行:$.ok 覆盖(对齐)+ $.gone 已无面
        await carry_store.put_bindings(
            db, "fin-service", {"$.ok": "b"}, updated_by_id=None, updated_by_name="alice")
        await carry_store.put_bindings(
            db, "fin-service-测试", {"$.ok": "a", "$.gone": "g"},
            updated_by_id=None, updated_by_name="alice")
        await db.commit()
    plate.items = [{"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
                    "service": "fin-service"}]
    plate.fulls = {"fin.ep1": {"request": {"declarations": [
        {"path": "$.ok", "state": "carry", "type": "string"}]}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    assert r.status_code == 200, r.text
    services = r.json()["services"]
    base_row = next(s for s in services if s["service"] == "fin-service")
    assert base_row["baseService"] is None
    assert base_row["orphaned"] == [] and base_row["uncovered"] == []
    alias_row = next(s for s in services if s["service"] == "fin-service-测试")
    assert alias_row["baseService"] == "fin-service"
    assert alias_row["orphaned"] == ["$.gone"]
    assert alias_row["uncovered"] == []          # 覆盖层不谈 uncovered
    assert alias_row["renamedSuggestions"] == []  # 无 uncovered → 无配对


async def test_drift_no_rename_suggestion_when_multiple_candidates(client, plate):
    """2 orphaned × 2 uncovered → 不猜配对(多候选负分支)。"""
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.old": "x", "$.old2": "y"},
            updated_by_id=None, updated_by_name="alice")
        await db.commit()
    plate.items = [{"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
                    "service": "fin-service"}]
    plate.fulls = {"fin.ep1": {"request": {"declarations": [
        {"path": "$.new", "state": "carry", "type": "string"},
        {"path": "$.new2", "state": "carry", "type": "string"}]}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    assert r.status_code == 200, r.text
    fin = next(s for s in r.json()["services"] if s["service"] == "fin-service")
    assert fin["renamedSuggestions"] == []
