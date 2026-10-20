"""W2 后端面(个人侧方案 §2):模板删除通知持有人(G-E)。"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models.permission import Notification
from app.models.user import User
from tests.helpers import make_draft, register_and_login
from tests.test_scenario_composer_plate_integration import (  # noqa: F401
    plate_mock,
)

async def _subscribe(client, h, tid: int):
    """显式订阅 —— 先取摘要回传 fingerprint(P2.2 必填,缺失 422)。"""
    fp = (await client.get(
        f"/api/integration/tasks/{tid}/subscription-summary",
        headers=h)).json()["fingerprint"]
    return await client.post(
        f"/api/integration/tasks/{tid}/subscribe",
        headers=h, json={"fingerprint": fp})



STEPS = [{
    "kind": "step", "description": "探活",
    "call": {"protocol": "http", "service": "svc",
             "method": "GET", "path": "/x", "headers": {}},
    "request": {"kind": "request", "body": {}}, "strategy": [],
}]


async def test_delete_notifies_subscribers(client):
    """G-E:owner 删除个人模板 → 订阅者收到人话通知(不再是只见「过期」)。"""
    u1 = await register_and_login(client, "w2_a", "pw123456")
    u2 = await register_and_login(client, "w2_b", "pw123456")
    r = await client.post("/api/scenarios", headers=u1,
                          json=make_draft("sc-w2", steps=STEPS))
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/integration/tasks", headers=u1, json={
        "name": "W2", "scenarioId": "sc-w2", "identityMode": "personal",
        "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
        "visibility": "public"})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    r = await _subscribe(client, u2, tid)
    assert r.status_code == 200, r.text

    async with db_module.SessionLocal() as db:
        uid2 = (await db.execute(select(User).where(
            User.username == "w2_b"))).scalars().one().id
        rows_before = (await db.execute(select(Notification).where(
            Notification.user_id == uid2))).scalars().all()

    r = await client.delete(f"/api/integration/tasks/{tid}", headers=u1)
    assert r.status_code == 200, r.text

    async with db_module.SessionLocal() as db:
        rows = (await db.execute(select(Notification).where(
            Notification.user_id == uid2))).scalars().all()
    assert len(rows) == len(rows_before) + 1
    assert "已删除" in (rows[-1].title or "")
