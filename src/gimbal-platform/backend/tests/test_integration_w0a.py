"""W0a(个人侧方案 v1.4 §2):订阅知情同意 + 播种收口 + visibility 联动。

- ①收口:列表/详情/卡片 GET 无写入副作用;未订阅 run → 409;
  subscribe/退订幂等,重订须重新确认(指纹刷新);
- ③同意闸:owner 改 cron / 别名 base_url 变更 → 订阅者实例
  paused/template_changed + 通知持有人;owner 自有实例不受闸;
  重新确认(再订阅)恢复;别名查询失败 → run=channel 收口,
  不翻 template_changed、不跳过比对(失败口径反例);
- ⑤联动:public→private → 非 owner 实例 paused/made_private + 通知,
  转回 public 不自动恢复;
- 未留指纹的存量/异常实例 → 按未确认处理(暂停待确认)。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models.integration_task import IntegrationTask
from app.models.permission import Notification
from app.models.service_alias import ServiceAlias
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


def _task_body(sid: str, **over) -> dict:
    body = {"name": "W0a", "scenarioId": sid, "identityMode": "personal",
            "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
            "visibility": "public"}
    body.update(over)
    return body


async def _mk_scenario(client, h, sid: str) -> None:
    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft(sid, steps=STEPS))
    assert r.status_code in (200, 201), r.text


async def _mk_task(client, h, sid: str) -> int:
    r = await client.post("/api/integration/tasks", headers=h,
                          json=_task_body(sid))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _user_id(username: str) -> int:
    async with db_module.SessionLocal() as db:
        return (await db.execute(select(User).where(
            User.username == username))).scalars().one().id


async def _inst(tpl_id: int, holder: int) -> IntegrationTask | None:
    async with db_module.SessionLocal() as db:
        return (await db.execute(select(IntegrationTask).where(
            IntegrationTask.template_id == tpl_id,
            IntegrationTask.holder_id == holder))).scalar()


async def _notify_count(user_id: int, keyword: str) -> int:
    async with db_module.SessionLocal() as db:
        rows = (await db.execute(select(Notification).where(
            Notification.user_id == user_id))).scalars().all()
        return sum(1 for n in rows if keyword in (n.title or "")
                   or keyword in (n.body or ""))


async def test_subscribe_flow_and_gate(client):
    """收口 + 同意闸主链:409 → 摘要 → 订阅(指纹)→ owner 改 cron →
    template_changed 暂停+通知 → 再订阅恢复 → 退订删行。"""
    u1 = await register_and_login(client, "w0a_alice", "pw123456")
    u2 = await register_and_login(client, "w0a_bob", "pw123456")
    await _mk_scenario(client, u1, "sc-w0a")
    tid = await _mk_task(client, u1, "sc-w0a")
    uid2 = await _user_id("w0a_bob")

    # ①未订阅 run → 409;列表/卡片/详情 GET 不播种
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u2)
    assert r.status_code == 409 and "subscription_required" in r.text, r.text
    await client.get("/api/integration/tasks", headers=u2)
    await client.get(f"/api/integration/tasks/{tid}", headers=u2)
    await client.post("/api/integration/cards", headers=u2,
                      json={"ids": [f"fn:{tid}"]})
    assert await _inst(tid, uid2) is None

    # ③订阅摘要(结构信息)→ 订阅(指纹落底)
    r = await client.get(f"/api/integration/tasks/{tid}/subscription-summary",
                         headers=u2)
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["steps"] and view["steps"][0]["service"] == "svc"
    assert view["steps"][0]["readonly"] is True
    assert view["cron"] == "*/5 * * * *"
    r = await _subscribe(client, u2, tid)
    assert r.status_code == 200, r.text
    inst = await _inst(tid, uid2)
    assert inst is not None and inst.consent_fingerprint
    assert inst.consented_at is not None
    # 摘要指纹与实例指纹一致(同一投影)
    assert inst.consent_fingerprint == view["fingerprint"]

    # owner 改 cron → 订阅者下次执行被闸(template_changed + 通知)
    r = await client.patch(f"/api/integration/tasks/{tid}", headers=u1,
                           json={"triggerCron": "*/7 * * * *"})
    assert r.status_code == 200, r.text
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u2)
    assert r.status_code == 200, r.text
    inst = await _inst(tid, uid2)
    assert inst.state == "paused"
    assert inst.paused_reason == "template_changed"
    assert await _notify_count(uid2, "重新确认") >= 1

    # owner 自有实例不受闸(照常执行,无 template_changed)
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u1)
    assert r.status_code == 200, r.text
    inst1 = await _inst(tid, await _user_id("w0a_alice"))
    assert inst1.paused_reason != "template_changed"

    # 重新确认 = 再订阅:刷新指纹并恢复调度
    r = await _subscribe(client, u2, tid)
    assert r.status_code == 200, r.text
    inst = await _inst(tid, uid2)
    assert inst.state == "idle" and inst.paused_reason == ""

    # 退订(P-3)删行;重订幂等重建(重新确认)
    r = await client.delete(f"/api/integration/tasks/{tid}/subscription",
                            headers=u2)
    assert r.status_code == 204, r.text
    assert await _inst(tid, uid2) is None
    r = await _subscribe(client, u2, tid)
    assert r.status_code == 200, r.text
    assert (await _inst(tid, uid2)).consent_fingerprint


async def test_base_url_change_triggers_template_changed(client):
    """G-F:别名 base_url 变更 → 指纹翻转 → 订阅者实例待确认。"""
    u1 = await register_and_login(client, "w0a_c", "pw123456")
    u2 = await register_and_login(client, "w0a_d", "pw123456")
    await _mk_scenario(client, u1, "sc-w0b")
    tid = await _mk_task(client, u1, "sc-w0b")
    uid2 = await _user_id("w0a_d")

    async with db_module.SessionLocal() as db:
        db.add(ServiceAlias(alias_name="svc", base_service="svc",
                            base_url="http://host-a"))
        await db.commit()

    r = await _subscribe(client, u2, tid)
    assert r.status_code == 200, r.text
    fp0 = (await _inst(tid, uid2)).consent_fingerprint

    # 别名指向别的主机(G-F 向量)→ 下次执行前被闸
    async with db_module.SessionLocal() as db:
        row = await db.get(ServiceAlias, "svc")
        row.base_url = "http://evil-host"
        await db.commit()
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u2)
    assert r.status_code == 200, r.text
    inst = await _inst(tid, uid2)
    assert inst.state == "paused"
    assert inst.paused_reason == "template_changed"
    assert inst.consent_fingerprint == fp0   # 未确认前不刷新


async def test_alias_query_failure_is_channel_not_consent(client, monkeypatch):
    """失败口径反例:别名查询失败 → run=channel 普通失败收口,
    不翻 template_changed、不跳过比对(实例未 paused)。"""
    from app.services import integration_runner as ir

    u1 = await register_and_login(client, "w0a_e", "pw123456")
    u2 = await register_and_login(client, "w0a_f", "pw123456")
    await _mk_scenario(client, u1, "sc-w0c")
    tid = await _mk_task(client, u1, "sc-w0c")
    uid2 = await _user_id("w0a_f")
    await _subscribe(client, u2, tid)

    async def _boom(db, payload):
        raise RuntimeError("alias db down")

    monkeypatch.setattr(ir, "_alias_urls_of", _boom)
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u2)
    assert r.status_code == 200, r.text
    inst = await _inst(tid, uid2)
    assert inst.paused_reason != "template_changed"   # 不是同意闸
    assert inst.run_status == "channel"
    assert "服务地址解析失败" in (inst.last_error or "")
    assert inst.state != "paused"   # 普通失败不暂停


async def test_visibility_private_pauses_subscribers(client):
    """W0a⑤(G-C):public→private → 非 owner 实例暂停+通知,转回
    public 不自动恢复;owner 实例不受影响。"""
    u1 = await register_and_login(client, "w0a_g", "pw123456")
    u2 = await register_and_login(client, "w0a_h", "pw123456")
    await _mk_scenario(client, u1, "sc-w0d")
    tid = await _mk_task(client, u1, "sc-w0d")
    uid1 = await _user_id("w0a_g")
    uid2 = await _user_id("w0a_h")
    await _subscribe(client, u2, tid)

    r = await client.patch(f"/api/integration/tasks/{tid}", headers=u1,
                           json={"visibility": "private"})
    assert r.status_code == 200, r.text
    inst2 = await _inst(tid, uid2)
    assert inst2.state == "paused" and inst2.paused_reason == "made_private"
    assert await _notify_count(uid2, "私有") >= 1
    inst1 = await _inst(tid, uid1)
    assert inst1.state != "paused"

    # 转回 public:不自动恢复(需订阅者重新确认)
    r = await client.patch(f"/api/integration/tasks/{tid}", headers=u1,
                           json={"visibility": "public"})
    assert r.status_code == 200, r.text
    assert (await _inst(tid, uid2)).state == "paused"
    # 重新确认(再订阅)恢复
    r = await _subscribe(client, u2, tid)
    assert r.status_code == 200, r.text
    assert (await _inst(tid, uid2)).state == "idle"


async def test_unstamped_instance_treated_as_unconfirmed(client):
    """未留指纹的实例(存量残留/异常路径)→ 按未确认处理:暂停待确认。"""
    u1 = await register_and_login(client, "w0a_i", "pw123456")
    u2 = await register_and_login(client, "w0a_j", "pw123456")
    await _mk_scenario(client, u1, "sc-w0e")
    tid = await _mk_task(client, u1, "sc-w0e")
    uid2 = await _user_id("w0a_j")

    # 直插无指纹实例(模拟清理遗漏的存量行)
    async with db_module.SessionLocal() as db:
        db.add(IntegrationTask(
            name="legacy", owner_id=await _user_id("w0a_i"),
            template_id=tid, holder_id=uid2, state="idle", enabled=True))
        await db.commit()

    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u2)
    assert r.status_code == 200, r.text
    inst = await _inst(tid, uid2)
    assert inst.state == "paused" and inst.paused_reason == "template_changed"


async def test_platform_task_not_subscribable(client):
    """平台模式任务无订阅概念:subscribe/摘要 → 422 not_subscribable。"""
    u1 = await register_and_login(client, "w0a_k", "pw123456")
    await _mk_scenario(client, u1, "sc-w0f")
    r = await client.post("/api/integration/tasks", headers=u1, json=_task_body(
        "sc-w0f", identityMode="platform", visibility="private"))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    # 平台任务:前置摘要即 422(助手不适用),直连断言订阅闸
    r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                          headers=u1, json={"fingerprint": "x"})
    assert r.status_code == 422 and "not_subscribable" in r.text, r.text
    r = await client.get(f"/api/integration/tasks/{tid}/subscription-summary",
                         headers=u1)
    assert r.status_code == 422, r.text
