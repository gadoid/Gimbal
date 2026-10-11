"""RS4a 新流程测试（Release v4.4 §5）:比较 → 保存检查 → 提交 → 回滚。

plate 侧(diff/lines/resolve/按修订 full/convert)以 monkeypatch 注入,
覆盖三组影响判定、保存检查五类阻断、R14 评审项、推荐规则、直接保存/
副本两条提交路径、最近一次回滚与副本删除语义。
"""
from __future__ import annotations

from copy import deepcopy

from app.core import db as db_module
from app.schemas.scenario_composer import ScenarioDraft
from app.services import adaptation_service, plate_client, scenario_store

from .helpers import make_draft, register_and_login

EP = "fin.settlement.create"
EP2 = "fin.settlement.query"


async def _seed(scenario_id: str, *, owner_id: int = 1, plate_ref="1.0#1"):
    steps = [
        {"kind": "step", "endpoint": EP, "call": {"protocol": "http",
         "service": "fin-service", "headers": {}},
         "request": {"kind": "request", "body": {"amount": 1}},
         "strategy": []},
    ]
    draft = make_draft(scenario_id, steps=steps, system=["fin"])
    if plate_ref:
        draft["definition"]["meta"]["plate"] = {"fin": plate_ref}
    async with db_module.SessionLocal() as s:
        await scenario_store.create(
            s, ScenarioDraft.model_validate(draft),
            owner=f"u{owner_id}", owner_id=owner_id)


def _full_item(paths=("amount",)):
    return {"id": EP, "request": {"declarations": [
        {"name": p, "path": f"$.{p}", "state": "form", "required": True}
        for p in paths
    ]}, "responses": {"200": {"declarations": [
        {"name": "code", "path": "$.code", "state": "form"}]}}}


# ─── 比较 ─────────────────────────────────────────────────────────

async def test_compare_groups_direct_field_structure(client, monkeypatch):
    await register_and_login(client, "afboss", "pw123456")
    user = await register_and_login(client, "afboss", "pw123456")
    await _seed("sc-af-1")

    async def fake_diff(system, from_ref, to_ref):
        return {"from": from_ref, "to": to_ref,
                "added": [], "removed": [f"endpoint.{EP2}"],
                "changed": {f"endpoint.{EP}": {"type": "endpoint",
                                               "parts": {"request": {}}}}}
    monkeypatch.setattr(adaptation_service, "plate_diff_for_adaptation",
                        fake_diff)
    r = await client.get("/api/adaptations/compare", headers=user,
                         params={"scenarioId": "sc-af-1", "target": "1.0#2"})
    assert r.status_code == 200, r.text
    item = r.json()["item"]
    assert item["from"] == "1.0#1" and item["to"] == "1.0#2"
    g = item["groups"]
    assert g["structure"] == []           # EP2 不在本场景步骤里
    assert g["field"] and g["field"][0]["endpoint"] == EP
    assert g["direct"] == []


# ─── 保存检查 ─────────────────────────────────────────────────────

async def test_save_check_ok_and_recommend_direct(client, monkeypatch):
    await register_and_login(client, "afboss2", "pw123456")
    user = await register_and_login(client, "afboss2", "pw123456")
    await _seed("sc-af-2")

    async def fake_convert(trial):
        return {"consumer": "gimbal", "converted": {}}
    async def fake_full_at(eid, ref):
        return _full_item()
    monkeypatch.setattr(plate_client, "convert", fake_convert)
    monkeypatch.setattr(plate_client, "get_endpoint_full_at", fake_full_at)

    r = await client.post("/api/adaptations/save-check", headers=user,
                          json={"scenarioId": "sc-af-2",
                                "targetRevision": "1.0#2"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["blocking_issues"] == [] and body["review_items"] == []
    assert body["recommendation"] == "direct"   # 无环境、无他人引用、非 working


async def test_save_check_blocks_extra_field_and_review_item(
    client, monkeypatch,
):
    await register_and_login(client, "afboss3", "pw123456")
    user = await register_and_login(client, "afboss3", "pw123456")
    await _seed("sc-af-3")
    # 注入一个 body 有但目标声明没有的字段 + 一个根段消失的注册表条目
    async with db_module.SessionLocal() as s:
        row = await scenario_store.get_row(s, "sc-af-3")
        payload = deepcopy(row.payload)
        payload["definition"]["steps"][0]["request"]["body"]["ghost"] = "x"
        payload["assertion_registry"] = {"entries": [{
            "id": "e1", "name": "n",
            "path": {"stepIndex": 0, "source": "response",
                     "jsonpath": "$.gone"}, "value": 1, "asserts": []}]}
        row.payload = payload
        await s.commit()

    async def fake_convert(trial):
        return {"consumer": "gimbal", "converted": {}}
    async def fake_full_at(eid, ref):
        return _full_item(("amount",))   # 不含 ghost/gone
    monkeypatch.setattr(plate_client, "convert", fake_convert)
    monkeypatch.setattr(plate_client, "get_endpoint_full_at", fake_full_at)

    r = await client.post("/api/adaptations/save-check", headers=user,
                          json={"scenarioId": "sc-af-3",
                                "targetRevision": "1.0#2"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    codes = {i["code"] for i in body["blocking_issues"]}
    assert "extra_field" in codes
    assert body["review_items"] and body["review_items"][0]["entry"] == "e1"


# ─── 提交 ─────────────────────────────────────────────────────────

def _patch_flow_ok(monkeypatch):
    async def fake_convert(trial):
        return {"consumer": "gimbal", "converted": {}}
    async def fake_full_at(eid, ref):
        return _full_item()
    monkeypatch.setattr(plate_client, "convert", fake_convert)
    monkeypatch.setattr(plate_client, "get_endpoint_full_at", fake_full_at)


async def test_submit_direct_updates_plate_and_audits(client, monkeypatch):
    from app.models.adaptation_batch import AdaptationBatch

    await register_and_login(client, "afboss4", "pw123456")
    user = await register_and_login(client, "afboss4", "pw123456")
    await _seed("sc-af-4")
    _patch_flow_ok(monkeypatch)

    r = await client.post("/api/adaptations/submit", headers=user, json={
        "scenarioId": "sc-af-4", "ops": [], "targetRevision": "1.0#2",
        "saveMode": "direct"})
    assert r.status_code == 200, r.text
    assert r.json()["save_mode"] == "direct"

    async with db_module.SessionLocal() as s:
        row = await scenario_store.get_row(s, "sc-af-4")
        plate = (row.payload["definition"]["meta"].get("plate"))
        assert plate == {"fin": "1.0#2"}
        from sqlalchemy import select
        batch = (await s.execute(select(AdaptationBatch).where(
            AdaptationBatch.batch_id == r.json()["batch_id"])
        )).scalar_one()
        assert batch.kind == "correction"      # 同线 1.0
        assert batch.save_mode == "direct" and batch.status == "completed"
        assert batch.scope == ["sc-af-4"]

    # 活动流:scenario.version_change 已落账
    from app.models.activity_event import ActivityEvent
    async with db_module.SessionLocal() as s:
        acts = (await s.execute(select(ActivityEvent).where(
            ActivityEvent.kind == "scenario.version_change")
        )).scalars().all()
        assert any(a.resource_id == "sc-af-4" for a in acts)


async def test_submit_blocked_by_review_items(client, monkeypatch):
    await register_and_login(client, "afboss5", "pw123456")
    user = await register_and_login(client, "afboss5", "pw123456")
    await _seed("sc-af-5")
    async with db_module.SessionLocal() as s:
        row = await scenario_store.get_row(s, "sc-af-5")
        payload = deepcopy(row.payload)
        payload["assertion_registry"] = {"entries": [{
            "id": "r1", "name": "n",
            "path": {"stepIndex": 0, "source": "response",
                     "jsonpath": "$.gone"}, "value": 1, "asserts": []}]}
        row.payload = payload
        await s.commit()
    _patch_flow_ok(monkeypatch)

    r = await client.post("/api/adaptations/submit", headers=user, json={
        "scenarioId": "sc-af-5", "ops": [], "targetRevision": "1.0#2",
        "saveMode": "direct"})
    assert r.status_code == 409
    assert "review_items_unconfirmed" in r.text

    # 确认后放行(R14)
    r = await client.post("/api/adaptations/submit", headers=user, json={
        "scenarioId": "sc-af-5", "ops": [], "targetRevision": "1.0#2",
        "saveMode": "direct", "reviewConfirmed": True})
    assert r.status_code == 200, r.text


async def test_submit_r22_non_owner_403(client, monkeypatch):
    await register_and_login(client, "afboss6", "pw123456")   # admin
    member = await register_and_login(client, "afm6", "pw123456")
    await _seed("sc-af-6", owner_id=1)          # 属主是 admin(uid 1)
    _patch_flow_ok(monkeypatch)
    r = await client.post("/api/adaptations/submit", headers=member, json={
        "scenarioId": "sc-af-6", "ops": [], "targetRevision": "1.0#2",
        "saveMode": "direct"})
    assert r.status_code == 403


# ─── 回滚(最近一次 + 副本删除)─────────────────────────────────────

async def test_rollback_restores_and_enforces_latest(client, monkeypatch):
    await register_and_login(client, "afboss7", "pw123456")
    user = await register_and_login(client, "afboss7", "pw123456")
    await _seed("sc-af-7")
    _patch_flow_ok(monkeypatch)

    r1 = await client.post("/api/adaptations/submit", headers=user, json={
        "scenarioId": "sc-af-7", "ops": [], "targetRevision": "1.0#2",
        "saveMode": "direct"})
    b1 = r1.json()["batch_id"]
    r2 = await client.post("/api/adaptations/submit", headers=user, json={
        "scenarioId": "sc-af-7", "ops": [], "targetRevision": "1.0#3",
        "saveMode": "direct"})
    b2 = r2.json()["batch_id"]

    # 回滚较早的 b1 → 拒绝(栈序,须先回滚 b2)
    r = await client.post(f"/api/adaptations/batches/{b1}/rollback",
                          headers=user)
    assert r.status_code == 409
    assert "not_latest" in r.text

    # 回滚最近的 b2 → meta.plate 还原为 1.0#2
    r = await client.post(f"/api/adaptations/batches/{b2}/rollback",
                          headers=user)
    assert r.status_code == 200, r.text
    async with db_module.SessionLocal() as s:
        row = await scenario_store.get_row(s, "sc-af-7")
        assert row.payload["definition"]["meta"]["plate"] == {"fin": "1.0#2"}


async def test_submit_copy_rollback_deletes_copy(client, monkeypatch):
    await register_and_login(client, "afboss8", "pw123456")
    user = await register_and_login(client, "afboss8", "pw123456")
    await _seed("sc-af-8")
    _patch_flow_ok(monkeypatch)

    r = await client.post("/api/adaptations/submit", headers=user, json={
        "scenarioId": "sc-af-8", "ops": [], "targetRevision": "2.0#1",
        "saveMode": "copy"})
    assert r.status_code == 200, r.text
    new_id = r.json()["new_scenario_id"]
    batch_id = r.json()["batch_id"]

    async with db_module.SessionLocal() as s:
        assert await scenario_store.get_row(s, new_id) is not None
    r = await client.post(f"/api/adaptations/batches/{batch_id}/rollback",
                          headers=user)
    assert r.status_code == 200, r.text
    async with db_module.SessionLocal() as s:
        assert await scenario_store.get_row(s, new_id) is None   # 副本已删
        # 原场景不动
        row = await scenario_store.get_row(s, "sc-af-8")
        assert row.payload["definition"]["meta"]["plate"] == {"fin": "1.0#1"}


# ─── 陈旧清单 ─────────────────────────────────────────────────────

async def test_stale_lists_working_and_new_line(client, monkeypatch):
    await register_and_login(client, "afboss9", "pw123456")
    user = await register_and_login(client, "afboss9", "pw123456")
    await _seed("sc-af-9", plate_ref=None)          # working
    await _seed("sc-af-10", plate_ref="1.0#1")      # 有新线

    async def fake_lines(system_id):
        return [{"line": "1.0", "latest": "1.0#1"},
                {"line": "2.0", "latest": "2.0#3"}]
    monkeypatch.setattr(plate_client, "list_lines", fake_lines)

    r = await client.get("/api/adaptations/stale", headers=user,
                         params={"scope": "mine"})
    assert r.status_code == 200, r.text
    items = {i["scenario_id"]: i["reasons"] for i in r.json()["items"]}
    assert any("版本声明" in x for x in items["sc-af-9"])
    assert any("新版本线" in x for x in items["sc-af-10"])
