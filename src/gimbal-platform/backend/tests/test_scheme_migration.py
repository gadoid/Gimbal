"""存储切换:payload→表迁移幂等性、生命周期钩子、draft 回填、旧端点桥接。"""
from sqlalchemy import select

from app.models.composer_scenario import ComposerScenario
from app.services import scheme_store
from app.services.migration_run_schemes import migrate_run_schemes_to_table
from .helpers import make_draft
from .test_scenario_visibility_and_copy import _member


def _legacy_draft() -> dict:
    d = make_draft()
    d["orchestration"]["runSchemes"] = [{
        "name": "存量方案", "dataSetIds": ["ds-001"],
        "dataSetSelection": [{"datasetId": "ds-001", "rowIndexes": [0]}],
        "injectionEntryIds": [], "serviceBindings": {},
        "plugins": None, "logSub": None,
    }]
    return d


async def test_migration_moves_schemes_and_clears_payload(client):
    from app.core.db import SessionLocal
    h = await _member(client, "alice")
    r = await client.post("/api/scenarios", headers=h, json=_legacy_draft())
    assert r.status_code == 201, r.text
    sid = r.json()["meta"]["scenarioId"]
    async with SessionLocal() as db:
        n = await migrate_run_schemes_to_table(db)
        assert n == 1
        lst = await scheme_store.list_schemes(db, sid)
        assert [s["name"] for s in lst] == ["默认方案", "存量方案"]
        assert lst[1]["dataSetSelection"] == [{"datasetId": "ds-001", "rowIndexes": [0]}]
        row = (await db.execute(select(ComposerScenario)
                .where(ComposerScenario.scenario_id == sid))).scalar_one()
        assert ((row.payload.get("orchestration") or {}).get("runSchemes")) == []
        assert await migrate_run_schemes_to_table(db) == 0  # 幂等


async def test_migration_ensures_default_for_schemeless_scenarios(client):
    """无方案存量的场景也在迁移中被补上默认方案(D8 全物化)。"""
    from app.core.db import SessionLocal
    h = await _member(client, "alice2")
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text
    sid = r.json()["meta"]["scenarioId"]
    async with SessionLocal() as db:
        n = await migrate_run_schemes_to_table(db)  # 无方案可搬 → 0
        assert n == 0
        lst = await scheme_store.list_schemes(db, sid)
    assert [s["name"] for s in lst] == ["默认方案"]


async def test_new_scenario_gets_default_scheme(client):
    from app.core.db import SessionLocal
    h = await _member(client, "bob")
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text
    sid = r.json()["meta"]["scenarioId"]
    async with SessionLocal() as db:
        lst = await scheme_store.list_schemes(db, sid)
    assert len(lst) == 1 and lst[0]["isDefault"] is True


async def test_draft_and_get_backfill_run_schemes_from_table(client):
    h = await _member(client, "carol")
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text
    sid = r.json()["meta"]["scenarioId"]
    # 通过旧端点写(桥接验证):数据应落新表
    put = await client.put(f"/api/scenarios/{sid}/run-schemes", headers=h, json={
        "schemes": [{"name": "桥接方案", "dataSetIds": [], "dataSetSelection": [],
                     "injectionEntryIds": [], "serviceBindings": {},
                     "plugins": None, "logSub": None}]})
    assert put.status_code == 200, put.text
    draft = (await client.get(f"/api/scenarios/{sid}/draft", headers=h)).json()
    names = [s["name"] for s in draft["orchestration"]["runSchemes"]]
    assert names[0] == "默认方案" and "桥接方案" in names
    # 非 draft 读侧(GET /{id} 的 orchestration)同样回填
    got = (await client.get(f"/api/scenarios/{sid}", headers=h)).json()
    names2 = [s["name"] for s in got["orchestration"]["runSchemes"]]
    assert names2[0] == "默认方案" and "桥接方案" in names2


async def test_copy_scenario_carries_schemes(client):
    from app.core.db import SessionLocal
    h = await _member(client, "dave")
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text
    sid = r.json()["meta"]["scenarioId"]
    await client.put(f"/api/scenarios/{sid}/run-schemes", headers=h, json={
        "schemes": [{"name": "跟走", "dataSetIds": [], "dataSetSelection": [],
                     "injectionEntryIds": [], "serviceBindings": {},
                     "plugins": None, "logSub": None}]})
    cp = await client.post(f"/api/scenarios/{sid}/copy", headers=h)
    assert cp.status_code == 201, cp.text
    new_sid = cp.json()["meta"]["scenarioId"]
    async with SessionLocal() as db:
        lst = await scheme_store.list_schemes(db, new_sid)
    assert [s["name"] for s in lst] == ["默认方案", "跟走"]
    # scheme_id 重新分配,不与源冲突
    assert all(s["schemeId"] for s in lst)


async def test_list_scenarios_exposes_scheme_count(client):
    h = await _member(client, "erin")
    await client.post("/api/scenarios", headers=h, json=make_draft())
    lst = (await client.get("/api/scenarios", headers=h)).json()
    mine = next(s for s in lst if s["meta"]["scenarioId"] == "sc-test")
    assert mine["schemeCount"] == 1  # 新场景 = 仅默认方案
