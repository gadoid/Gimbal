"""批量提交测试(§5.3 直接切换多场景聚合)。"""
from __future__ import annotations

from app.core import db as db_module
from app.schemas.scenario_composer import ScenarioDraft
from app.services import plate_client, scenario_store

from .helpers import make_draft, register_and_login

EP = "fin.settlement.create"


async def _seed(sid: str):
    draft = make_draft(sid, steps=[
        {"kind": "step", "endpoint": EP,
         "call": {"protocol": "http", "service": "fin-service",
                  "headers": {}},
         "request": {"kind": "request", "body": {"amount": 1}},
         "strategy": []}], system=["fin"])
    draft["definition"]["meta"]["plate"] = {"fin": "1.0#1"}
    async with db_module.SessionLocal() as s:
        await scenario_store.create(
            s, ScenarioDraft.model_validate(draft), owner="b", owner_id=1)


async def test_submit_batch_two_scenarios(client, monkeypatch):
    await register_and_login(client, "bsboss", "pw123456")
    user = await register_and_login(client, "bsboss", "pw123456")
    await _seed("sc-bs-1")
    await _seed("sc-bs-2")

    async def fake_convert(trial):
        return {"consumer": "gimbal", "converted": {}}
    async def fake_full_at(eid, ref):
        return {"request": {"declarations": [
            {"name": "amount", "path": "$.amount", "type": "number",
             "required": True}]}}
    async def fake_diff(system, a, b):
        return {"from": a, "to": b, "added": [], "removed": [],
                "changed": {}}
    monkeypatch.setattr(plate_client, "convert", fake_convert)
    monkeypatch.setattr(plate_client, "get_endpoint_full_at", fake_full_at)
    from app.services import adaptation_service
    monkeypatch.setattr(adaptation_service, "plate_diff_for_adaptation",
                        fake_diff)

    r = await client.post("/api/adaptations/submit-batch", headers=user,
                          json={"scenarioIds": ["sc-bs-1", "sc-bs-2"],
                                "targetRevision": "1.0#2"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2 and body["succeeded"] == 2
    async with db_module.SessionLocal() as s:
        for sid in ("sc-bs-1", "sc-bs-2"):
            row = await scenario_store.get_row(s, sid)
            assert row.payload["definition"]["meta"]["plate"] == {"fin": "1.0#2"}
