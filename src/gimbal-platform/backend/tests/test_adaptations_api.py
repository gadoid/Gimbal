"""adaptations 路由 API 测试:admin 门控(403/401)、diff 502、impact 只读。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core import db as db_module
from app.models.catalog_version import CatalogVersion
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store

from .helpers import make_draft, register_and_login

EP = "fin.order.add"

# OLD_FULL:基线戳的 spec_json 快照(declarations 形状,与现拉 /full 同构)
OLD_FULL = {
    "id": EP, "version": "1.0.0",
    "request": {"declarations": [
        {"name": "amount", "channel": "binding"},
        {"name": "legacy_field", "channel": "binding"},
        {"name": "settle_type", "channel": "binding", "enum": ["1", "2"]},
    ]},
}
# NEW_FULL:现拉 plate /full(declarations binding 通道)
NEW_FULL = {
    "id": EP, "version": "1.1.0",
    "request": {"declarations": [
        {"name": "amount", "channel": "binding"},
        {"name": "extra", "channel": "binding", "default": "E"},
        {"name": "settle_type", "channel": "binding", "enum": ["2", "3"]},
    ]},
}


def _steps():
    return [{
        "api": {"view_hints": {"endpoint_id": EP}, "headers": {}},
        "request": {"body": {"amount": "${var.amount}", "legacy_field": "L",
                             "settle_type": "1"}},
    }]


async def _session():
    return db_module.SessionLocal()


async def _api_seed_scenario(sid: str = "sc-api", owner_id: int = 1):
    async with await _session() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft(sid, steps=_steps(), vars_map={"amount": 100})
            ),
            owner=f"u{owner_id}", owner_id=owner_id,
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
                                     "request": {"declarations": []}}}
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

    # 场景类 op 漏传 scenarioId → op_needs_scenario(而非 KeyError→误导 404)
    no_sc = await client.post(
        f"/api/adaptations/batches/{batch_id}/ops",
        json={"opType": "renameVar",
              "payload": {"from": "amount", "to": "amt"}},
        headers=admin)
    assert no_sc.status_code == 400
    assert "op_needs_scenario" in no_sc.json()["detail"]

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
    "api": {"view_hints": {}, "headers": {}},
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


# ─── batches scope=mine(P5 Task 2,C13 owner 视图)───────────────
async def _open_batch_ok(client, headers) -> dict:
    r = await client.post("/api/adaptations/batches",
                          json={"endpointId": EP}, headers=headers)
    assert r.status_code == 201
    return r.json()


async def test_batches_scope_mine_lists_owned(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")   # uid 1
    member = await register_and_login(client, "peon", "peonpass123")  # uid 2
    await _api_seed_scenario("sc-peon", owner_id=2)
    await _api_seed_stamp()
    _api_plate_ahead(plate)
    detail = await _open_batch_ok(client, admin)

    mine = await client.get("/api/adaptations/batches",
                            params={"scope": "mine"}, headers=member)
    assert mine.status_code == 200
    assert [b["batchId"] for b in mine.json()] == [detail["batchId"]]
    # owner 视图不泄漏场景细节,但批次元数据 + opCounts 可见(知情)
    assert mine.json()[0]["opCounts"] == {"pending": 3}


async def test_batches_scope_mine_excludes_others(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    member = await register_and_login(client, "peon", "peonpass123")
    await _api_seed_scenario("sc-alice", owner_id=1)   # admin 自己的场景
    await _api_seed_stamp()
    _api_plate_ahead(plate)
    await _open_batch_ok(client, admin)

    mine = await client.get("/api/adaptations/batches",
                            params={"scope": "mine"}, headers=member)
    assert mine.status_code == 200
    assert mine.json() == []


async def test_batches_member_without_scope_403_admin_full(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    member = await register_and_login(client, "peon", "peonpass123")
    await _api_seed_scenario()
    await _api_seed_stamp()
    _api_plate_ahead(plate)
    detail = await _open_batch_ok(client, admin)

    denied = await client.get("/api/adaptations/batches", headers=member)
    assert denied.status_code == 403
    assert "admin_only" in denied.json()["detail"]

    full = await client.get("/api/adaptations/batches", headers=admin)
    assert full.status_code == 200
    assert [b["batchId"] for b in full.json()] == [detail["batchId"]]


# ─── skip / patch op(P5 Task 3)─────────────────────────────────
async def _opened_with_ops(client, plate) -> tuple[dict, str]:
    admin = await register_and_login(client, "boss", "bosspass123")
    await _api_seed_scenario()
    await _api_seed_stamp()
    _api_plate_ahead(plate)
    detail = await _open_batch_ok(client, admin)
    return detail, admin


async def test_skip_marks_skipped_and_idempotent(client, plate):
    detail, admin = await _opened_with_ops(client, plate)
    op = detail["ops"][0]

    first = await client.post(f"/api/adaptations/ops/{op['id']}/skip",
                              headers=admin)
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "skipped"
    assert body["note"] == "skipped by operator"

    again = await client.post(f"/api/adaptations/ops/{op['id']}/skip",
                              headers=admin)
    assert again.status_code == 200          # 幂等:skipped 再调原样返回
    assert again.json()["status"] == "skipped"

    mid = await client.get(
        f"/api/adaptations/batches/{detail['batchId']}", headers=admin)
    assert mid.json()["status"] == "open"    # 还有 2 条 pending → 不收敛
    assert mid.json()["opCounts"] == {"pending": 2, "skipped": 1}


async def test_skip_op_error_mappings(client, plate):
    detail, admin = await _opened_with_ops(client, plate)
    applied_op = detail["ops"][0]
    await client.post(f"/api/adaptations/ops/{applied_op['id']}/apply",
                      headers=admin)

    conflict = await client.post(
        f"/api/adaptations/ops/{applied_op['id']}/skip", headers=admin)
    assert conflict.status_code == 409
    assert "op_not_applicable" in conflict.json()["detail"]

    missing = await client.post("/api/adaptations/ops/99999/skip",
                                headers=admin)
    assert missing.status_code == 404

    member = await register_and_login(client, "peon", "peonpass123")  # uid 2
    denied = await client.post(
        f"/api/adaptations/ops/{detail['ops'][1]['id']}/skip", headers=member)
    assert denied.status_code == 403


async def test_skip_last_pending_completes_batch(client, plate):
    detail, admin = await _opened_with_ops(client, plate)
    for op in detail["ops"]:                 # 3 条全跳 → 跳过也是决策
        r = await client.post(f"/api/adaptations/ops/{op['id']}/skip",
                              headers=admin)
        assert r.status_code == 200

    final = await client.get(
        f"/api/adaptations/batches/{detail['batchId']}", headers=admin)
    assert final.json()["status"] == "completed"
    assert final.json()["opCounts"] == {"skipped": 3}

    async with await _session() as s:        # 推戳:stamp 前进到 1.1.0
        stamp = (await s.execute(
            select(CatalogVersion).where(CatalogVersion.endpoint_id == EP)
        )).scalar_one()
        assert stamp.version == "1.1.0"


async def test_patch_replaces_payload_and_strips_op_key(client, plate):
    detail, admin = await _opened_with_ops(client, plate)
    map_op = next(o for o in detail["ops"] if o["opType"] == "mapValue")
    assert map_op["payload"]["map"] == {}    # 骨架:map 为空,等补值

    r = await client.patch(
        f"/api/adaptations/ops/{map_op['id']}",
        json={"payload": {"op": "mapValue", "step": 0,
                          "field": "settle_type", "map": {"1": "2"}}},
        headers=admin)
    assert r.status_code == 200
    assert r.json()["payload"] == {"step": 0, "field": "settle_type",
                                   "map": {"1": "2"}}   # "op" 键被剥

    reread = await client.get(
        f"/api/adaptations/batches/{detail['batchId']}", headers=admin)
    persisted = next(o for o in reread.json()["ops"] if o["id"] == map_op["id"])
    assert persisted["payload"]["map"] == {"1": "2"}


async def test_patch_non_pending_409(client, plate):
    detail, admin = await _opened_with_ops(client, plate)
    applied_op = detail["ops"][0]
    await client.post(f"/api/adaptations/ops/{applied_op['id']}/apply",
                      headers=admin)

    r = await client.patch(
        f"/api/adaptations/ops/{applied_op['id']}",
        json={"payload": {"step": 0, "field": "x"}}, headers=admin)
    assert r.status_code == 409
    assert "op_not_applicable" in r.json()["detail"]
