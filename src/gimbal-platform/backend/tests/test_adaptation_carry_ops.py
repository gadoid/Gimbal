"""CARRY_OPS 值表批(spec §7)— 开批/快照/应用/回滚;场景定义零变化。

偏差记录(相对 task brief,详见 task-12-report.md):
* 用户名 "carry-bob" 违反 ^[A-Za-z0-9_]+$ → "carry_bob"(预裁定);
* 场景造数用 make_draft(ScenarioMeta 必填 meta 字段,且响应读形无
  顶层 scenarioId 键 → 取 meta.scenarioId);
* rollback 测试补第二条 pending op:既有不变量 rollback_batch 仅接受
  open/applying(单 op 应用完即 completed → batch_not_rollbackable 409)。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models import AdaptationOp, ComposerScenario
from app.services import carry_store

from .helpers import make_draft
from .test_carry_api import _admin


async def _open_carry_batch(client, admin, service=None):
    r = await client.post("/api/adaptations/carry-batches", headers=admin,
                          json={"service": service})
    assert r.status_code == 201, r.text
    return r.json()["batchId"]


async def _add_op(client, admin, batch_id, op_type, payload):
    r = await client.post(f"/api/adaptations/batches/{batch_id}/ops",
                          headers=admin,
                          json={"opType": op_type, "payload": payload})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_carry_ops_apply_and_snapshot(client):
    admin = await _admin(client)
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.old": "v1"}, "alice")
        await db.commit()

    batch_id = await _open_carry_batch(client, admin, "fin-service")
    op1 = await _add_op(client, admin, batch_id, "renameCarryPath",
                        {"service": "fin-service", "from": "$.old",
                         "to": "$.new"})
    op2 = await _add_op(client, admin, batch_id, "addCarryBinding",
                        {"service": None, "path": "$.appCode",
                         "value": "TRACE-V2"})

    for op_id in (op1, op2):
        r = await client.post(f"/api/adaptations/ops/{op_id}/apply",
                              headers=admin)
        assert r.status_code == 200, r.text

    async with db_module.SessionLocal() as db:
        assert await carry_store.get_bindings(db, "fin-service") == {"$.new": "v1"}
        assert await carry_store.get_defaults(db) == {"$.appCode": "TRACE-V2"}
        # 场景零触碰(D1):op 不寻址任何场景
        assert (await db.execute(select(ComposerScenario))).scalars().all() == []


async def test_carry_batch_rollback_restores(client):
    admin = await _admin(client)
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.old": "v1"}, "alice")
        await db.commit()

    batch_id = await _open_carry_batch(client, admin, "fin-service")
    op_id = await _add_op(client, admin, batch_id, "renameCarryPath",
                          {"service": "fin-service", "from": "$.old",
                           "to": "$.new"})
    # 留一条 pending:单 op 批应用完即 completed,rollback 只接受
    # open/applying(既有不变量 test_rollback_only_open_or_applying)
    await _add_op(client, admin, batch_id, "addCarryBinding",
                  {"service": "fin-service", "path": "$.keep",
                   "value": "pending"})
    await client.post(f"/api/adaptations/ops/{op_id}/apply", headers=admin)

    r = await client.post(f"/api/adaptations/batches/{batch_id}/rollback",
                          headers=admin)
    assert r.status_code == 200, r.text
    async with db_module.SessionLocal() as db:
        assert await carry_store.get_bindings(db, "fin-service") == {"$.old": "v1"}
        statuses = {o.status for o in (await db.execute(
            select(AdaptationOp))).scalars()}
    assert statuses == {"applied", "skipped"}  # pending → skipped by rollback


async def test_carry_batch_never_touches_scenarios(client):
    """D1 红利断言:carry 批前后场景定义零变化。"""
    admin = await _admin(client)
    bob_headers = await _member_headers(client)
    r = await client.post("/api/scenarios", headers=bob_headers,
                          json=make_draft("sc-carry-zero"))
    assert r.status_code == 201, r.text
    sid = r.json()["meta"]["scenarioId"]
    async with db_module.SessionLocal() as db:
        before = (await db.execute(
            select(ComposerScenario).where(
                ComposerScenario.scenario_id == sid))).scalar_one().payload

    batch_id = await _open_carry_batch(client, admin)
    op_id = await _add_op(client, admin, batch_id, "addCarryBinding",
                          {"service": None, "path": "$.x", "value": "1"})
    await client.post(f"/api/adaptations/ops/{op_id}/apply", headers=admin)

    async with db_module.SessionLocal() as db:
        after = (await db.execute(
            select(ComposerScenario).where(
                ComposerScenario.scenario_id == sid))).scalar_one().payload
    assert before == after


async def _member_headers(client):
    from .test_scenario_visibility_and_copy import _member
    return await _member(client, "carry_bob")
