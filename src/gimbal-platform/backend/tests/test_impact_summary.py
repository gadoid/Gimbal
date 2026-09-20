"""impact_summary 本批影响面摘要(配套方案 §3.2,2026-09-20)。

核心口径:
* 服务归组 = pending 端点自身的目录 service(轻列表权威),不扫场景;
* caseCount = 倒排索引 distinct 场景(锚点行含);跨服务场景在多服务条
  各计一次,totals 去重;
* recentFailCount = 受影响场景最近一次执行终态 failed(全站跨 owner,
  不复用 /executions 的 owner 过滤;running/queued 的旧终态、canceled
  不算失败);
* 传入端点不在 plate 轻列表 → 不进任何服务条,也不计入 totals;
* 空 endpointIds → 全零(不炸)。
"""
from __future__ import annotations

from datetime import datetime

from app.core import db as db_module
from app.models.execution import Execution
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store

from .helpers import make_draft
from .test_carry_api import _admin

EP_A1 = "fin.order.add"     # fin-service,sc-sum-1 / sc-sum-2 引用
EP_A2 = "fin.order.get"     # fin-service,sc-sum-2 引用(锚点)
EP_B1 = "wms.stock.move"    # wms-service,sc-sum-3 引用
EP_GHOST = "gone.endpoint"  # 不在 plate 轻列表 → 不进摘要


async def _seed():
    async with db_module.SessionLocal() as s:
        await scenario_store.create(
            s, ScenarioDraft.model_validate(make_draft("sc-sum-1", steps=[
                {"api": {"view_hints": {"endpoint_id": EP_A1}, "headers": {}},
                 "request": {"body": {"amount": 1}}},
            ])), owner="alice", owner_id=1)
        await scenario_store.create(
            s, ScenarioDraft.model_validate(make_draft("sc-sum-2", steps=[
                {"api": {"view_hints": {"endpoint_id": EP_A1}, "headers": {}},
                 "request": {"body": {"amount": 2}}},
                {"api": {"view_hints": {"endpoint_id": EP_A2}, "headers": {}},
                 "request": {"body": {}}},
            ])), owner="bob", owner_id=2)
        await scenario_store.create(
            s, ScenarioDraft.model_validate(make_draft("sc-sum-3", steps=[
                {"api": {"view_hints": {"endpoint_id": EP_B1}, "headers": {}},
                 "request": {"body": {"sku": "x"}}},
            ])), owner="bob", owner_id=2)

        def _exec(sid: str, status: str, owner: int, *, passed=2, failed=0,
                  created=datetime(2026, 9, 10)):
            return Execution(scenario_id=sid, owner_id=owner, status=status,
                             total_runs=2, passed=passed, failed=failed,
                             created_at=created, finished_at=created)

        # sc-sum-1:旧 failed → 新 done(最近一次未失败)
        s.add(_exec("sc-sum-1", "failed", 1, failed=2, passed=0,
                    created=datetime(2026, 9, 8)))
        s.add(_exec("sc-sum-1", "done", 1, created=datetime(2026, 9, 10)))
        # sc-sum-2(他人场景,跨 owner 统计):最近一次 failed → 计失败
        s.add(_exec("sc-sum-2", "failed", 2, failed=1, passed=1,
                    created=datetime(2026, 9, 12)))
        # sc-sum-3:最近一次 canceled(灰)→ 不计失败
        s.add(_exec("sc-sum-3", "canceled", 2, created=datetime(2026, 9, 11)))
        await s.commit()


def _plate():
    return [
        {"id": EP_A1, "version": "2.0.0", "updated_at": None,
         "service": "fin-service"},
        {"id": EP_A2, "version": "2.0.0", "updated_at": None,
         "service": "fin-service"},
        {"id": EP_B1, "version": "2.0.0", "updated_at": None,
         "service": "wms-service"},
    ]


async def test_impact_summary_groups_by_endpoint_service(client, plate):
    await _seed()
    plate.items = _plate()
    admin = await _admin(client)
    r = await client.get("/api/adaptations/impact-summary", headers=admin,
                         params=[("endpointIds", EP_A1), ("endpointIds", EP_A2),
                                 ("endpointIds", EP_B1), ("endpointIds", EP_GHOST)])
    assert r.status_code == 200, r.text
    body = r.json()

    fin = next(s for s in body["services"] if s["name"] == "fin-service")
    assert fin["changeCount"] == 2          # EP_A1 + EP_A2
    assert fin["caseCount"] == 2            # sc-sum-1, sc-sum-2
    assert fin["recentFailCount"] == 1      # sc-sum-2 最近 failed(跨 owner)

    wms = next(s for s in body["services"] if s["name"] == "wms-service")
    assert wms["changeCount"] == 1
    assert wms["caseCount"] == 1
    assert wms["recentFailCount"] == 0      # 最近一次 canceled 不算

    # totals:ghost 不计;caseCount 跨服务去重;失败数同口径
    assert body["totals"] == {"changeCount": 3, "serviceCount": 2,
                              "caseCount": 3, "recentFailCount": 1}


async def test_impact_summary_empty_ids_returns_zeros(client, plate):
    plate.items = _plate()
    admin = await _admin(client)
    r = await client.get("/api/adaptations/impact-summary", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json() == {"services": [], "totals": {
        "changeCount": 0, "serviceCount": 0, "caseCount": 0,
        "recentFailCount": 0}}


async def test_impact_summary_member_forbidden(client, plate):
    from .test_scenario_visibility_and_copy import _member
    plate.items = _plate()
    member = await _member(client, "sum_mem")
    r = await client.get("/api/adaptations/impact-summary", headers=member,
                         params=[("endpointIds", EP_A1)])
    assert r.status_code == 403
