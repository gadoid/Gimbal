"""adaptations 路由 API 测试（RS3 后收窄）。

RS3 §5.10：按端点开批的旧流程（基线戳 / POST /batches / 草案展开）
已删除，本文件只覆盖存续的读面：catalog/diff 空报告、impact、
unindexed-steps。批次生命周期经 carry 批（见 test_carry_*）与新
RS4a 流程（随批次三重建）测试。
"""
from __future__ import annotations

from app.core import db as db_module
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store

from .helpers import make_draft, register_and_login

EP = "fin.order.add"


def _steps():
    return [{
        "call": {"view_hints": {"endpoint_id": EP}, "headers": {}},
        "request": {"body": {"amount": "${var.amount}"}},
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


async def _seed_unindexed_scenario(sid: str = "sc-unbound"):
    async with await _session() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft(sid, steps=[{
                    "call": {"headers": {}},          # 无 endpoint 锚点
                    "request": {"body": {"x": "1"}},
                }])
            ),
            owner="u1", owner_id=1,
        )


# ─── catalog/diff（空报告：机制已删，路由保留给旧客户端）─────────
async def test_diff_requires_login(client, plate):
    r = await client.post("/api/adaptations/catalog/diff")
    assert r.status_code == 401


async def test_diff_returns_empty_report(client, plate):
    member = await register_and_login(client, "peon", "peonpass123")
    r = await client.post("/api/adaptations/catalog/diff", headers=member)
    assert r.status_code == 200
    assert r.json() == {"pending": [], "anomalies": [], "baselinedNow": 0}


# ─── impact（admin 门控保留；读面无版本依赖）────────────────────
async def test_impact_admin_read_empty(client, plate):
    await register_and_login(client, "boss", "bosspass123")
    admin = await register_and_login(client, "boss", "bosspass123")
    r = await client.get("/api/adaptations/impact",
                         params={"endpointId": EP}, headers=admin)
    assert r.status_code == 200
    assert r.json() == []


# ─── unindexed-steps（CurrentUser；C10 只读警示）────────────────
async def test_unindexed_steps_lists_gap(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    await _api_seed_scenario()          # sc-api:步骤已挂 endpoint_id → 不在清单
    await _seed_unindexed_scenario()    # sc-unbound:缺 endpoint 锚点 → 在清单
    r = await client.get("/api/adaptations/unindexed-steps", headers=admin)
    assert r.status_code == 200
    assert r.json() == [{"scenarioId": "sc-unbound", "stepIndex": 0,
                         "reason": "no_endpoint_id"}]


async def test_unindexed_steps_member_accessible(client, plate):
    await register_and_login(client, "boss", "bosspass123")
    member = await register_and_login(client, "peon", "peonpass123")
    r = await client.get("/api/adaptations/unindexed-steps",
                         headers=member)
    assert r.status_code == 200
