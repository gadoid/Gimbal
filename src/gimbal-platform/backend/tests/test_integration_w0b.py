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

async def _subscribe(client, h, tid: int):
    """显式订阅 —— 先取摘要回传 fingerprint(P2.2 必填,缺失 422)。"""
    fp = (await client.get(
        f"/api/integration/tasks/{tid}/subscription-summary",
        headers=h)).json()["fingerprint"]
    return await client.post(
        f"/api/integration/tasks/{tid}/subscribe",
        headers=h, json={"fingerprint": fp})



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

    r = await _subscribe(client, u2, tid)
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
    r = await _subscribe(client, u2, tid)
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
    await _subscribe(client, u2, tid)

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
    r = await _subscribe(client, u2, tid)
    assert r.status_code == 200, r.text
    assert (await _inst(tid, uid2)).state == "idle"


async def test_fail_streak_auto_pause_and_resume(client):
    """W4:连续失败达 FAIL_STREAK_AUTO_PAUSE(5)自动退回
    paused/fail_streak 并通知持有人;阈值前照常 idle;「启动」恢复
    即清零计数;复活钩子不覆盖 fail_streak。"""
    from app.models.permission import Notification
    from app.services import integration_runner as ir

    u1 = await register_and_login(client, "w0b_i", "pw123456")
    u2 = await register_and_login(client, "w0b_j", "pw123456")
    tid = await _mk_task(client, u1, "sc-w0b5")
    uid2 = await _user_id("w0b_j")
    await _subscribe(client, u2, tid)
    inst_id = (await _inst(tid, uid2)).id

    async def set_streak(n: int):
        async with db_module.SessionLocal() as s:
            row = await s.get(IntegrationTask, inst_id)
            row.fail_streak = n
            await s.commit()

    async def run_fail():
        async with db_module.SessionLocal() as s:
            await ir._finish(s, await s.get(IntegrationTask, inst_id),
                             await s.get(IntegrationTask, tid),
                             "transport", "网络连不通")

    # 阈值前(第 4 次)照常 idle、不暂停
    await set_streak(3)
    await run_fail()
    inst = await _inst(tid, uid2)
    assert inst.state == "idle" and inst.fail_streak == 4

    # 第 5 次 → 自动暂停(fail_streak)+ 通知持有人
    await run_fail()
    inst = await _inst(tid, uid2)
    assert inst.state == "paused" and inst.paused_reason == "fail_streak"
    assert inst.fail_streak == 5 and inst.run_status == "transport"
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(Notification).where(
            Notification.user_id == uid2))).scalars().all()
    assert any("连续失败" in n.title and "自动暂停" in n.title
               for n in rows), [n.title for n in rows]

    # 复活钩子(凭证面)不覆盖 fail_streak
    await ir.revive_paused_instances(user_id=uid2)
    inst = await _inst(tid, uid2)
    assert inst.state == "paused" and inst.paused_reason == "fail_streak"

    # 「启动」恢复:idle + 计数清零 + 下拍即跑
    r = await client.post(
        f"/api/integration/tasks/{tid}/subscription/resume", headers=u2)
    assert r.status_code == 200, r.text
    inst = await _inst(tid, uid2)
    assert inst.state == "idle" and inst.paused_reason in ("", None)
    assert inst.fail_streak == 0 and inst.next_run_at is not None


async def test_pause_resume_platform_and_owner_rows(client):
    """W4:平台模式暂停/恢复对 owner/admin 开放(操作平台唯一实例,
    其余用户 403);个人模式 owner 自有实例同走订阅面端点 —— 集成页
    owner 行的暂停/恢复按钮即此口径。"""
    from tests.test_integration import _seed_platform_user

    await _seed_platform_user()
    from app.services import integration_runner as ir

    u1 = await register_and_login(client, "w0b_k", "pw123456")
    u2 = await register_and_login(client, "w0b_l", "pw123456")
    tid_p = await _mk_task(client, u1, "sc-w0b6",
                           identityMode="platform", visibility="public")
    async with db_module.SessionLocal() as s:
        await ir.ensure_instance(await s.get(IntegrationTask, tid_p))

    async def _pinst() -> IntegrationTask | None:
        async with db_module.SessionLocal() as s:
            return (await s.execute(select(IntegrationTask).where(
                IntegrationTask.template_id == tid_p,
                IntegrationTask.holder_id.is_not(None),
            ).order_by(IntegrationTask.id))).scalars().first()

    # 普通用户(可见但非 owner/admin)→ 403;暂停/恢复同口径
    r = await client.post(
        f"/api/integration/tasks/{tid_p}/subscription/pause", headers=u2)
    assert r.status_code == 403, r.text
    r = await client.post(
        f"/api/integration/tasks/{tid_p}/subscription/resume", headers=u2)
    assert r.status_code == 403, r.text

    # owner 暂停/恢复平台唯一实例
    r = await client.post(
        f"/api/integration/tasks/{tid_p}/subscription/pause", headers=u1)
    assert r.status_code == 200, r.text
    inst = await _pinst()
    assert inst is not None
    assert inst.state == "paused" and inst.paused_reason == "manual"
    r = await client.post(
        f"/api/integration/tasks/{tid_p}/subscription/resume", headers=u1)
    assert r.status_code == 200, r.text
    inst = await _pinst()
    assert inst.state == "idle" and inst.paused_reason in ("", None)

    # 个人模式 owner 行:创建即播种自有实例,暂停/恢复直达
    tid_o = await _mk_task(client, u1, "sc-w0b7")
    uid1 = await _user_id("w0b_k")
    r = await client.post(
        f"/api/integration/tasks/{tid_o}/subscription/pause", headers=u1)
    assert r.status_code == 200, r.text
    inst = await _inst(tid_o, uid1)
    assert inst.state == "paused" and inst.paused_reason == "manual"
    r = await client.post(
        f"/api/integration/tasks/{tid_o}/subscription/resume", headers=u1)
    assert r.status_code == 200, r.text
    assert (await _inst(tid_o, uid1)).state == "idle"
