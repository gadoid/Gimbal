"""复盘轮(2026-09-29)修复钉子:

* ②-5 搜索:q 检索面含 system(「公共场景搜索异常」根因——占位符宣称
  按系统搜,SQL/Python 两侧检索面都不含 system 列);
* ②-4 通知分页:page_size snake 参数生效(此前 camel 被忽略落默认 50,
  「每页 10 实显 13」);
* ②-3 时间线:执行事件携带 scenarioName(快照列;空回退 scenarioId)。
"""
from __future__ import annotations

from tests.helpers import make_draft, register_and_login


async def _publish(client, h, sid: str, name: str, systems: list[str]) -> None:
    draft = make_draft(sid, steps=[{
        "id": "s1", "kind": "step",
        "call": {"kind": "call", "protocol": "http", "service": "svc",
                 "method": "GET", "path": "/p"},
        "request": {"kind": "request", "body": {}},
        "strategy": [],
    }])
    draft["definition"]["meta"]["name"] = name
    draft["definition"]["meta"]["system"] = systems
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text
    r = await client.post(f"/api/scenarios/{sid}/publish", headers=h)
    assert r.status_code == 200, r.text


async def test_public_search_matches_system(client):
    """按系统值搜索必须命中(占位符:「按名 / 模块 / 系统 / … 搜索」)。"""
    h = await register_and_login(client, "retro1", "pw123456")
    await _publish(client, h, "sc-retro-a", "甲场景", ["unique-sys-x"])
    for q in ("unique-sys-x", "甲场景"):
        r = await client.get("/api/scenarios", headers=h,
                             params={"visibility": "public", "q": q})
        assert r.status_code == 200
        ids = [i["meta"]["scenarioId"] for i in r.json()["items"]]
        assert "sc-retro-a" in ids, (q, ids)


async def test_notifications_page_size_param_honored(client):
    """page_size(而非被忽略的 camel 键)生效:14 条通知,每页 10 → 首 10。"""
    from app.core import db as db_module
    from app.models.permission import Notification
    from datetime import datetime, timezone

    h = await register_and_login(client, "retro2", "pw123456")
    # register_and_login 建的是最新用户;直接向其灌 14 条
    from sqlalchemy import select
    from app.models.user import User
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(select(User.id)
                               .where(User.username == "retro2"))).scalar_one()
        for i in range(14):
            s.add(Notification(user_id=uid, type="run.finished",
                               title=f"n{i}", body="", link=""))
        await s.commit()

    r = await client.get("/api/notifications", headers=h,
                         params={"page": 1, "page_size": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 14
    assert len(body["items"]) == 10, len(body["items"])
    assert body["page"] == 1 and body["pageSize"] == 10


async def test_activity_execution_event_carries_scenario_name(client):
    """执行事件带 scenarioName;历史行(空快照)为 None → 前端回退 id。"""
    from app.core import db as db_module
    from app.models.execution import Execution
    from app.models.user import User
    from sqlalchemy import select

    h = await register_and_login(client, "retro3", "pw123456")
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(select(User.id)
                               .where(User.username == "retro3"))).scalar_one()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        s.add(Execution(scenario_id="sc-named", owner_id=uid, status="done",
                        total_runs=1, passed=1, scenario_name="下单场景",
                        started_at=now, finished_at=now, config_json={}))
        await s.commit()

    r = await client.get("/api/activity", headers=h)
    assert r.status_code == 200
    exec_events = [e for e in r.json()["events"] if e["kind"] == "execution"]
    assert any(e.get("scenarioName") == "下单场景"
               and e.get("scenarioId") == "sc-named" for e in exec_events), exec_events
