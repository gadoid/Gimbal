"""清账向导盘点端点(阶段 3;``GET /admin/cleanup-survey``,admin 只读)。

三面 live 聚合 = enforce 就绪清单:

* 未登记引用场景(保存/导入闸同一提取器)—— 登记条目后行消失;
* 明文快照场景(键名 only;``referencedKeys`` = 被步骤引用的键,
  须先登记同名条目再清,否则执行面悬空);
* 方案绑定目标未登记(写面闸历史存量面)。

门:member 403(AdminUser);清账操作不经本端点(登记走
POST /service-aliases,清快照走属主保存链 —— W3 admin 无旁路)。
"""
from __future__ import annotations

import pytest

from app.core import db as db_module
from app.models.composer_scenario import ComposerScenario
from app.services.scenario_store import definition_from_payload

from .helpers import role_headers


def _steps(ref: str) -> list[dict]:
    """fin-service 步骤 + ``${auth.<ref>.token}`` 模板引用。"""
    return [{
        "kind": "step", "endpoint": "fin.orders.get",
        "call": {"service": "fin-service", "method": "GET", "path": "/o",
                 "headers": {"Authorization": f"${{auth.{ref}.token}}"}},
        "request": {"kind": "request", "body": {}}, "strategy": [],
    }]


async def _mk_scenario(sid: str, definition: dict) -> None:
    """直插场景行(容器形态,不走保存闸 —— 盘点测的是存量)。"""
    async with db_module.SessionLocal() as s:
        s.add(ComposerScenario(   # name = 生成列(meta.name),不可直插
            scenario_id=sid, owner_name="seed", owner_id=None,
            payload={"definition": definition}))
        await s.commit()


@pytest.mark.asyncio
async def test_survey_member_403(client):
    """member → 403(AdminUser 门)。"""
    h = await role_headers(client, "survey-m", role="user")
    r = await client.get("/api/admin/cleanup-survey", headers=h)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_survey_aggregates_three_faces(client):
    """三面聚合:未登记引用行 + 快照行(referencedKeys 判定)+ 绑定行;
    登记条目后未登记面清零(register route 同款写面)。"""
    from sqlalchemy import select

    admin = await role_headers(client, "survey-admin", role="super_admin")
    await _mk_scenario("sc-survey-ref", {
        "meta": {"scenarioId": "sc-survey-ref", "name": "引用场景",
                 "system": ["fin"]},
        "steps": _steps("sb"),
        "config": {"users": {}},
    })
    await _mk_scenario("sc-survey-snap", {
        "meta": {"scenarioId": "sc-survey-snap", "name": "快照场景",
                 "system": ["fin"]},
        "steps": _steps("codfish2"),  # 快照键同时被步骤引用
        "config": {"users": {"codfish2": {"username": "u", "password": "p"}}},
    })
    await _mk_scenario("sc-survey-clean", {
        "meta": {"scenarioId": "sc-survey-clean", "name": "干净场景",
                 "system": ["fin"]},
        "steps": _steps("sb"),
        "config": {"users": {}},
    })

    r = await client.get("/api/admin/cleanup-survey", headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gateMode"] in ("off", "audit", "enforce")
    unreg = {row["scenarioId"]: row for row in body["unregistered"]}
    # sb 未登记 → 两个引用场景都上榜;干净场景因引用未登记名同样上榜
    # (盘点只报事实 —— 它与引用场景的差别不在本面,清账后同消)
    assert set(unreg) == {"sc-survey-ref", "sc-survey-snap", "sc-survey-clean"}
    assert unreg["sc-survey-ref"]["refs"] == ["sb"]

    snap = {row["scenarioId"]: row for row in body["snapshots"]}
    assert set(snap) == {"sc-survey-snap"}
    # 只列键名,不出值
    assert snap["sc-survey-snap"]["keys"] == ["codfish2"]
    assert snap["sc-survey-snap"]["referencedKeys"] == ["codfish2"]
    assert "password" not in str(body)

    # 登记 sb + codfish2 条目(既有 Admin+ 写面,与向导登记同一 API;
    # plate 强约束 = base 落已知服务集 → 先补主档服务行)
    from sqlalchemy import select as sa_select
    from app.models import Environment, Service
    async with db_module.SessionLocal() as s:
        env_id = (await s.execute(sa_select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        for svc in ("sb", "codfish2"):
            if (await s.execute(sa_select(Service.id).where(
                    Service.name == svc))).scalar_one_or_none() is None:
                s.add(Service(name=svc, system=svc, kind="plate"))
        if env_id is None:   # 空环境库:盘点测自带默认环境
            s.add(Environment(name="测试", is_default=True))
        await s.commit()
        env_id = (await s.execute(sa_select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
    for alias in ("sb", "codfish2"):
        rr = await client.post("/api/service-aliases", headers=admin, json={
            "alias_name": alias, "kind": "plate",
            "base_service": alias, "env_id": env_id, "ref_mode": "default"})
        assert rr.status_code in (200, 201), rr.text

    r = await client.get("/api/admin/cleanup-survey", headers=admin)
    body = r.json()
    assert body["unregistered"] == []
    # 快照行不随登记消失 —— 清账第二步(属主保存链显式清空)的活
    assert [row["scenarioId"] for row in body["snapshots"]] == \
        ["sc-survey-snap"]


@pytest.mark.asyncio
async def test_snapshot_unreferenced_key_flags_empty(client):
    """快照键无步骤引用 → referencedKeys 空(可直接清,不悬空)。"""
    await _mk_scenario("sc-survey-snap2", {
        "meta": {"scenarioId": "sc-survey-snap2", "name": "纯快照",
                 "system": ["fin"]},
        "steps": _steps("sb"),  # sb 未登记(引用面),快照键 ghost-x 无引用
        "config": {"users": {"ghost-x": {"username": "u", "password": "p"}}},
    })
    admin = await role_headers(client, "survey-admin2", role="super_admin")
    r = await client.get("/api/admin/cleanup-survey", headers=admin)
    assert r.status_code == 200, r.text
    snap = {row["scenarioId"]: row for row in r.json()["snapshots"]}
    assert snap["sc-survey-snap2"]["keys"] == ["ghost-x"]
    assert snap["sc-survey-snap2"]["referencedKeys"] == []
