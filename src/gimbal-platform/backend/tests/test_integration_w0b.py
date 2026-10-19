"""W0b(个人侧方案 v1.4 §2):④消费面字段(authAliases /
missingCredentials / subscribed,任务行与卡片) + ⑥订阅者自管
(pause/resume,paused/manual;复活钩子不覆盖 manual)。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models.auth_session import AuthSession
from app.models.integration_task import IntegrationTask
from app.models.user import User
from tests.helpers import make_draft, register_and_login
from tests.test_scenario_composer_plate_integration import (  # noqa: F401
    plate_mock,
)

AUTH_STEPS = [{
    "kind": "step", "description": "拉取",
    "call": {"protocol": "http", "service": "svc",
             "method": "GET", "path": "/x",
             "headers": {"Authorization": "${auth.gitlab.token}"}},
    "request": {"kind": "request", "body": {}}, "strategy": [],
}]


async def _user_id(username: str) -> int:
    async with db_module.SessionLocal() as db:
        return (await db.execute(select(User).where(
            User.username == username))).scalars().one().id


async def _inst(tpl_id: int, holder: int) -> IntegrationTask | None:
    async with db_module.SessionLocal() as db:
        return (await db.execute(select(IntegrationTask).where(
            IntegrationTask.template_id == tpl_id,
            IntegrationTask.holder_id == holder))).scalar()


async def _mk_task(client, h, sid: str, **over) -> int:
    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft(sid, steps=AUTH_STEPS))
    assert r.status_code in (200, 201), r.text
    body = {"name": "W0b", "scenarioId": sid, "identityMode": "personal",
            "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
            "visibility": "public"}
    body.update(over)
    r = await client.post("/api/integration/tasks", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _item(client, h, tid: int) -> dict:
    r = await client.get("/api/integration/tasks", headers=h)
    assert r.status_code == 200, r.text
    return next(t for t in r.json()["items"] if t["id"] == tid)


async def test_consumer_fields_lifecycle(client):
    """④:未订阅 authAliases 可见 / 订阅后 subscribed+missing /
    补凭证后 missing 清空。"""
    u1 = await register_and_login(client, "w0b_a", "pw123456")
    u2 = await register_and_login(client, "w0b_b", "pw123456")
    tid = await _mk_task(client, u1, "sc-w0b1")
    uid2 = await _user_id("w0b_b")

    item = await _item(client, u2, tid)
    assert item["authAliases"] == ["gitlab"]
    assert item["subscribed"] is False
    assert item["instance"] is None

    r = await client.post(f"/api/integration/tasks/{tid}/subscribe", headers=u2)
    assert r.status_code == 200, r.text
    item = await _item(client, u2, tid)
    assert item["subscribed"] is True
    assert item["instance"]["missingCredentials"] == ["gitlab"]

    async with db_module.SessionLocal() as db:
        db.add(AuthSession(
            owner_id=uid2, alias="gitlab", url="http://127.0.0.1:1",
            username_enc=fernet_encrypt("u"),
            password_enc=fernet_encrypt("p")))
        await db.commit()
    r = await client.get(f"/api/integration/tasks/{tid}", headers=u2)
    assert r.status_code == 200, r.text
    assert r.json()["instance"]["missingCredentials"] == []


async def test_platform_task_fields(client):
    """④:平台模式任务 authAliases 照出、subscribed 恒 False。"""
    u1 = await register_and_login(client, "w0b_c", "pw123456")
    tid = await _mk_task(client, u1, "sc-w0b2",
                         identityMode="platform", visibility="private")
    item = await _item(client, u1, tid)
    assert item["authAliases"] == ["gitlab"]
    assert item["subscribed"] is False


async def test_cards_carry_consumer_fields(client):
    """④:卡片出参带 authAliases / missingCredentials(W3 凭证引导)。"""
    u1 = await register_and_login(client, "w0b_d", "pw123456")
    u2 = await register_and_login(client, "w0b_e", "pw123456")
    tid = await _mk_task(client, u1, "sc-w0b3")
    r = await client.post(f"/api/integration/tasks/{tid}/subscribe", headers=u2)
    assert r.status_code == 200, r.text
    r = await client.post("/api/integration/cards", headers=u2,
                          json={"ids": [f"fn:{tid}"]})
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert item["authAliases"] == ["gitlab"]
    assert item["missingCredentials"] == ["gitlab"]


async def test_pause_resume_and_revive_scope(client):
    """⑥:自暂停 manual / 复活钩子不覆盖 manual / resume 仅 manual
    可恢复(template_changed → 409 引导重新订阅)/ 未订阅 404。"""
    from app.services import integration_runner as ir

    u1 = await register_and_login(client, "w0b_f", "pw123456")
    u2 = await register_and_login(client, "w0b_g", "pw123456")
    u3 = await register_and_login(client, "w0b_h", "pw123456")
    tid = await _mk_task(client, u1, "sc-w0b4")
    uid2 = await _user_id("w0b_g")
    await client.post(f"/api/integration/tasks/{tid}/subscribe", headers=u2)

    # 未订阅者自管 → 404
    r = await client.post(
        f"/api/integration/tasks/{tid}/subscription/pause", headers=u3)
    assert r.status_code == 404, r.text

    # 自暂停 → paused/manual;凭证复活钩子不覆盖 manual
    r = await client.post(
        f"/api/integration/tasks/{tid}/subscription/pause", headers=u2)
    assert r.status_code == 200, r.text
    inst = await _inst(tid, uid2)
    assert inst.state == "paused" and inst.paused_reason == "manual"
    await ir.revive_paused_instances(user_id=uid2)
    inst = await _inst(tid, uid2)
    assert inst.paused_reason == "manual"

    # resume 恢复;idle 再 resume 幂等
    r = await client.post(
        f"/api/integration/tasks/{tid}/subscription/resume", headers=u2)
    assert r.status_code == 200, r.text
    assert (await _inst(tid, uid2)).state == "idle"
    r = await client.post(
        f"/api/integration/tasks/{tid}/subscription/resume", headers=u2)
    assert r.status_code == 200, r.text

    # template_changed 暂停不能 resume(引导重新订阅确认)
    r = await client.patch(f"/api/integration/tasks/{tid}", headers=u1,
                           json={"triggerCron": "*/7 * * * *"})
    assert r.status_code == 200, r.text
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u2)
    assert r.status_code == 200, r.text
    assert (await _inst(tid, uid2)).paused_reason == "template_changed"
    r = await client.post(
        f"/api/integration/tasks/{tid}/subscription/resume", headers=u2)
    assert r.status_code == 409 and "resume_not_allowed" in r.text, r.text
    # 重新订阅确认后再自管一轮
    r = await client.post(f"/api/integration/tasks/{tid}/subscribe", headers=u2)
    assert r.status_code == 200, r.text
    assert (await _inst(tid, uid2)).state == "idle"
