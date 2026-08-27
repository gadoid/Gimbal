"""倒排索引:解析规则 / 写路径挂钩 / 删除级联(spec §3.2)。"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models.scenario_endpoint_ref import ScenarioEndpointRef
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store
from tests.helpers import make_draft

STEPS = [{
    "api": {
        "view_hints": {"endpoint_id": "fin.order.add"},
        "headers": {"X-Token": "${var.tok}"},
    },
    "request": {"body": {
        "customer_id": "261",             # 直填 → via_var None
        "amount": "${var.amount}",        # 整串模板
        "mix": "p-${var.amount}-s",       # 内嵌模板
    }},
}, {
    # 无 view_hints.endpoint_id → 不进索引,进未索引报告
    "api": {"headers": {}}, "request": {"body": {"x": "1"}},
}]

STEPS2 = [{
    "api": {"view_hints": {"endpoint_id": "fin.order.add"}},
    "request": {"body": {"amount": 5}},   # 数值直填:非 str,via_var None
}]


def _draft(sid: str, steps: list) -> ScenarioDraft:
    return ScenarioDraft.model_validate(make_draft(sid, steps=steps))


async def _refs() -> set[tuple]:
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ScenarioEndpointRef))).scalars().all()
    return {(r.scenario_id, r.step_index, r.source, r.field_name,
             r.endpoint_id, r.via_var) for r in rows}


async def test_create_populates_index(fresh_db):
    async with db_module.SessionLocal() as s:
        await scenario_store.create(s, _draft("sc-ix", STEPS), owner="alice")
    assert await _refs() == {
        ("sc-ix", 0, "body", "customer_id", "fin.order.add", None),
        ("sc-ix", 0, "body", "amount", "fin.order.add", "amount"),
        ("sc-ix", 0, "body", "mix", "fin.order.add", "amount"),
        ("sc-ix", 0, "headers", "X-Token", "fin.order.add", "tok"),
    }  # step 1(无 endpoint_id)不产生行


async def test_update_replaces_index(fresh_db):
    async with db_module.SessionLocal() as s:
        await scenario_store.create(s, _draft("sc-ix", STEPS), owner="alice")
        await scenario_store.update(s, "sc-ix", _draft("sc-ix", STEPS2))
    assert await _refs() == {
        ("sc-ix", 0, "body", "amount", "fin.order.add", None),
    }


async def test_delete_clears_index(fresh_db):
    async with db_module.SessionLocal() as s:
        await scenario_store.create(s, _draft("sc-ix", STEPS), owner="alice")
        await scenario_store.delete(s, "sc-ix")
    assert await _refs() == set()


async def test_rebuild_equivalent_and_reports_unindexed(fresh_db):
    from app.services import endpoint_ref_index as idx

    async with db_module.SessionLocal() as s:
        await scenario_store.create(s, _draft("sc-ix", STEPS), owner="alice")
    before = await _refs()

    async with db_module.SessionLocal() as s:
        # 破坏派生层模拟灾后:清空索引行
        from sqlalchemy import delete as sa_delete
        await s.execute(sa_delete(ScenarioEndpointRef))
        await s.commit()
        report = await idx.rebuild(s)

    assert await _refs() == before            # rebuild 结果与逐行维护全等
    assert report["scenarios"] == 1
    assert report["refs"] == len(before)
    assert report["unindexed_steps"] == [
        {"scenario_id": "sc-ix", "step_index": 1, "reason": "no_endpoint_id"},
    ]


async def test_rebuild_idempotent(fresh_db):
    from app.services import endpoint_ref_index as idx

    async with db_module.SessionLocal() as s:
        await scenario_store.create(s, _draft("sc-ix", STEPS), owner="alice")
    async with db_module.SessionLocal() as s:
        r1 = await idx.rebuild(s)
        r2 = await idx.rebuild(s)
    assert (r1["refs"], len(r1["unindexed_steps"])) == (r2["refs"], len(r2["unindexed_steps"]))


async def test_unindexed_steps_reports_api_less_step(fresh_db):
    from app.services import endpoint_ref_index as idx

    steps = [
        {"api": {"view_hints": {"endpoint_id": "fin.order.add"}}},
        {"request": {"body": {"x": "1"}}},   # 无 api → 无 endpoint_id
    ]
    async with db_module.SessionLocal() as s:
        await scenario_store.create(s, _draft("sc-un", steps), owner="alice")
    async with db_module.SessionLocal() as s:
        report = await idx.unindexed_steps(s)
    assert report == [
        {"scenario_id": "sc-un", "step_index": 1, "reason": "no_endpoint_id"},
    ]
