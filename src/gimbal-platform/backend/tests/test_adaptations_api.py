"""adaptations 路由 API 测试:admin 门控(403/401)、diff 502、impact 只读。"""
from __future__ import annotations

from datetime import datetime

from app.core import db as db_module
from app.models.catalog_version import CatalogVersion
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store

from .helpers import make_draft, register_and_login

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


async def _api_seed_scenario(sid: str = "sc-api"):
    async with await _session() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft(sid, steps=_steps(), vars_map={"amount": 100})
            ),
            owner="alice", owner_id=1,
        )


async def _api_seed_stamp():
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id=EP, version="1.0.0",
                             spec_json=OLD_FULL, synced_at=datetime(2026, 1, 1)))
        await s.commit()


def _api_plate_ahead(plate):
    plate.items = [{"id": EP, "version": "1.1.0",
                    "updated_at": "2026-06-01T00:00:00Z"}]
    plate.fulls = {EP: NEW_FULL}


async def test_diff_requires_login(client, plate):
    r = await client.post("/api/adaptations/catalog/diff")
    assert r.status_code == 401


async def test_diff_admin_only(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")   # uid 1 → 自动 admin
    member = await register_and_login(client, "peon", "peonpass123")  # uid 2 → 普通用户
    denied = await client.post("/api/adaptations/catalog/diff", headers=member)
    assert denied.status_code == 403

    plate.items = [{"id": "fin.order.add", "version": "1.0.0",
                    "updated_at": "2026-01-01T00:00:00Z"}]
    plate.fulls = {"fin.order.add": {"id": "fin.order.add", "version": "1.0.0",
                                     "request": {"fields": []}}}
    ok = await client.post("/api/adaptations/catalog/diff", headers=admin)
    assert ok.status_code == 200
    assert ok.json() == {"pending": [], "anomalies": [], "baselinedNow": 1}


async def test_diff_plate_unavailable_502(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    plate.down = True
    r = await client.post("/api/adaptations/catalog/diff", headers=admin)
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "plate_unavailable"


async def test_impact_readonly_and_admin_only(client, plate):
    await register_and_login(client, "boss", "bosspass123")
    member = await register_and_login(client, "peon", "peonpass123")
    denied = await client.get("/api/adaptations/impact",
                              params={"endpointId": "fin.order.add"},
                              headers=member)
    assert denied.status_code == 403
    admin = await register_and_login(client, "boss", "bosspass123")
    ok = await client.get("/api/adaptations/impact",
                          params={"endpointId": "fin.order.add"}, headers=admin)
    assert ok.status_code == 200
    assert ok.json() == []


# ─── 批次生命周期 API(Task 10)────────────────────────────────────
async def test_batch_lifecycle_api(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    await _api_seed_scenario()
    await _api_seed_stamp()
    _api_plate_ahead(plate)

    opened = await client.post("/api/adaptations/batches",
                               json={"endpointId": EP}, headers=admin)
    assert opened.status_code == 201
    detail = opened.json()
    assert detail["endpointId"] == EP
    assert detail["fromVersion"] == "1.0.0" and detail["toVersion"] == "1.1.0"
    assert detail["status"] == "open"
    assert detail["opCounts"] == {"pending": 3}

    for op in detail["ops"]:
        applied = await client.post(f"/api/adaptations/ops/{op['id']}/apply",
                                    headers=admin)
        assert applied.status_code == 200
        assert applied.json()["status"] == "applied"

    replay = await client.post(f"/api/adaptations/ops/{detail['ops'][0]['id']}/apply",
                               headers=admin)
    assert replay.status_code == 200 and replay.json()["status"] == "applied"

    final = await client.get(
        f"/api/adaptations/batches/{detail['batchId']}", headers=admin)
    assert final.status_code == 200
    assert final.json()["status"] == "completed"
    assert final.json()["opCounts"] == {"applied": 3}

    listed = await client.get("/api/adaptations/batches", headers=admin)
    assert listed.status_code == 200
    assert [b["batchId"] for b in listed.json()] == [detail["batchId"]]
    assert listed.json()[0]["opCounts"] == {"applied": 3}

    rolled = await client.post(
        f"/api/adaptations/batches/{detail['batchId']}/rollback", headers=admin)
    assert rolled.status_code == 409
    assert "batch_not_rollbackable" in rolled.json()["detail"]


async def test_batch_error_mappings(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    _api_plate_ahead(plate)

    no_baseline = await client.post("/api/adaptations/batches",
                                    json={"endpointId": EP}, headers=admin)
    assert no_baseline.status_code == 409
    assert "no_baseline" in no_baseline.json()["detail"]

    await _api_seed_stamp()
    plate.items = [{"id": EP, "version": "1.0.0", "updated_at": None}]  # 未前进
    plate.fulls = {EP: OLD_FULL}
    no_bump = await client.post("/api/adaptations/batches",
                                json={"endpointId": EP}, headers=admin)
    assert no_bump.status_code == 409
    assert "no_pending_change" in no_bump.json()["detail"]

    missing = await client.get("/api/adaptations/batches/bt-none",
                               headers=admin)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "bt-none"


async def test_manual_op_validation(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    await _api_seed_scenario()
    await _api_seed_stamp()
    _api_plate_ahead(plate)
    opened = await client.post("/api/adaptations/batches",
                               json={"endpointId": EP}, headers=admin)
    batch_id = opened.json()["batchId"]

    bad = await client.post(
        f"/api/adaptations/batches/{batch_id}/ops",
        json={"opType": "explode", "scenarioId": "sc-api", "payload": {}},
        headers=admin)
    assert bad.status_code == 400
    assert "bad_op_type" in bad.json()["detail"]

    no_ds = await client.post(
        f"/api/adaptations/batches/{batch_id}/ops",
        json={"opType": "renameDatasetColumn", "scenarioId": "sc-api",
              "payload": {"from": "amount", "to": "amt"}},
        headers=admin)
    assert no_ds.status_code == 400
    assert "op_needs_dataset" in no_ds.json()["detail"]

    ok = await client.post(
        f"/api/adaptations/batches/{batch_id}/ops",
        json={"opType": "renameVar", "scenarioId": "sc-api",
              "payload": {"from": "amount", "to": "amt"}},
        headers=admin)
    assert ok.status_code == 201
    body = ok.json()
    assert body["opType"] == "renameVar" and body["status"] == "pending"
    assert body["payload"] == {"from": "amount", "to": "amt"}


async def test_batch_routes_admin_only(client, plate):
    await register_and_login(client, "boss", "bosspass123")
    member = await register_and_login(client, "peon", "peonpass123")
    for method, url in [
        ("POST", "/api/adaptations/batches"),
        ("GET", "/api/adaptations/batches"),
        ("GET", "/api/adaptations/batches/bt-x"),
        ("POST", "/api/adaptations/batches/bt-x/ops"),
        ("POST", "/api/adaptations/ops/1/apply"),
        ("POST", "/api/adaptations/batches/bt-x/rollback"),
    ]:
        r = await client.request(method, url, headers=member)
        assert r.status_code == 403, (method, url, r.status_code)


# ─── unindexed-steps(P5 Task 1)──────────────────────────────────
UNBOUND_STEPS = [{
    "api": {"view_hints": {}, "headers": {}, "query": {}},
    "request": {"body": {"x": "1"}},
}]


async def _seed_unindexed_scenario(sid: str = "sc-unbound"):
    async with await _session() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft(sid, steps=UNBOUND_STEPS, vars_map={})),
            owner="alice", owner_id=1,
        )


async def test_unindexed_steps_lists_gap(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    await _api_seed_scenario()          # sc-api:步骤已挂 endpoint_id → 不在清单
    await _seed_unindexed_scenario()    # sc-unbound:缺 endpoint_id → 在清单
    r = await client.get("/api/adaptations/unindexed-steps", headers=admin)
    assert r.status_code == 200
    assert r.json() == [{"scenarioId": "sc-unbound", "stepIndex": 0,
                         "reason": "no_endpoint_id"}]


async def test_unindexed_steps_admin_only(client, plate):
    await register_and_login(client, "boss", "bosspass123")   # uid 1 admin
    member = await register_and_login(client, "peon", "peonpass123")
    denied = await client.get("/api/adaptations/unindexed-steps",
                              headers=member)
    assert denied.status_code == 403
