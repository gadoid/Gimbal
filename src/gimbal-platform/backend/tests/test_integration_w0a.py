"""W0a(个人侧方案 v1.4 §2):订阅知情同意 + 播种收口 + visibility 联动。

- ①收口:列表/详情/卡片 GET 无写入副作用;未订阅 run → 409;
  subscribe/退订幂等,重订须重新确认(指纹刷新);
- ③同意闸:owner 改 cron / 别名 base_url 变更 → 实例(订阅者与
  **owner 自有实例同受闸 —— AC-50 私有所有者自订阅覆盖**)
  paused/template_changed + 通知持有人;
  重新确认(再订阅)恢复;别名查询失败 → run=channel 收口,
  不翻 template_changed、不跳过比对(失败口径反例);
- ⑤联动:public→private → 非 owner 实例 paused/made_private + 通知,
  转回 public 不自动恢复;
- 未留指纹的存量/异常实例 → 按未确认处理(暂停待确认)。
"""
from __future__ import annotations
import pytest  # noqa: E402

from sqlalchemy import select

from app.core import db as db_module
from app.models.integration_task import IntegrationTask
from app.models.permission import Notification
from app.models import Service
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
    # S1.3:公共模板引用公共副本(<原 id>-public;夹具建场景即发布)
    body = {"name": "W0a", "scenarioId": f"{sid}-public",
            "identityMode": "personal",
            "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
            "visibility": "public"}
    body.update(over)
    return body


async def _mk_scenario(client, h, sid: str) -> None:
    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft(sid, steps=STEPS))
    assert r.status_code in (200, 201), r.text
    from .inbound_fixtures import publish_scenario

    await publish_scenario(sid)


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

    # owner 自有实例同受闸(AC-50 私有所有者自订阅覆盖):内容变更后
    # 照样 template_changed 暂停
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u1)
    assert r.status_code == 200, r.text
    inst1 = await _inst(tid, await _user_id("w0a_alice"))
    assert inst1.state == "paused"
    assert inst1.paused_reason == "template_changed"
    # owner 重新确认(再订阅)恢复
    r = await _subscribe(client, u1, tid)
    assert r.status_code == 200, r.text
    inst1 = await _inst(tid, await _user_id("w0a_alice"))
    assert inst1.state == "idle" and inst1.paused_reason == ""

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
    """G-F:部署地址变更 → 指纹翻转 → 订阅者实例待确认(authz M2a S6:
    地址只来自部署表,别名 base_url 已删)。"""
    u1 = await register_and_login(client, "w0a_c", "pw123456")
    u2 = await register_and_login(client, "w0a_d", "pw123456")
    await _mk_scenario(client, u1, "sc-w0b")
    tid = await _mk_task(client, u1, "sc-w0b")
    uid2 = await _user_id("w0a_d")

    from .helpers import seed_deployment
    async with db_module.SessionLocal() as db:
        db.add(Service(name="svc", system="svc", kind="plate"))
        await seed_deployment(db, "svc", "http://host-a")
        await db.commit()

    r = await _subscribe(client, u2, tid)
    assert r.status_code == 200, r.text
    fp0 = (await _inst(tid, uid2)).consent_fingerprint

    # 部署地址指向别的主机(G-F 向量)→ 下次执行前被闸
    async with db_module.SessionLocal() as db:
        await seed_deployment(db, "svc", "http://evil-host")
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



async def test_scheme_delete_recreate_same_content_reconfirms(client):
    """AC-50(复核 P1):删默认方案、以**相同业务 ID、名称、revision 和
    内容**在同一场景重建(设计 §22 验收矩阵指定向量)—— 内容七要素
    全同,但不可变 scheme_uid 换代 → 订阅指纹翻转 → 派发前暂停
    (template_changed,零派发)。覆盖私有所有者自订阅(本腿)与普通
    项目其他成员订阅(u2 腿);再订阅恢复(新身份知情)。"""
    u1 = await register_and_login(client, "w0a_g", "pw123456")
    u2 = await register_and_login(client, "w0a_h", "pw123456")
    await _mk_scenario(client, u1, "sc-w0d")
    tid = await _mk_task(client, u1, "sc-w0d")
    uid1 = await _user_id("w0a_g")
    uid2 = await _user_id("w0a_h")
    r = await _subscribe(client, u2, tid)
    assert r.status_code == 200, r.text
    fp0 = (await _inst(tid, uid2)).consent_fingerprint

    from app.models.composer_run_scheme import ComposerRunScheme

    async with db_module.SessionLocal() as s:
        from app.models.integration_task import IntegrationTask as _IT
        _scen_id = (await s.get(_IT, tid)).scenario_id   # 任务挂发布副本场景
        row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == _scen_id,
            ComposerRunScheme.is_default == True))).scalar_one()
        old_uid = row.scheme_uid
        # 设计指定向量:同业务 ID(scheme_id)、同名称、同 revision、
        # 同内容(绑定/数据集/组合位全同)—— 唯一约束随删行释放,重建
        # 行占回同一业务 ID,仅 uid 换代
        old = {"scheme_id": row.scheme_id,
               "scenario_id": row.scenario_id,
               "project_id": row.project_id, "name": row.name,
               "is_default": True, "payload": dict(row.payload or {}),
               "account_combo_id": row.account_combo_id,
               "repair_status": "ready", "revision": row.revision}
        await s.delete(row)
        await s.flush()
        clone = ComposerRunScheme(**old)
        s.add(clone)
        await s.commit()
        new_uid = clone.scheme_uid
    assert str(clone.scheme_id) == str(old["scheme_id"]), \
        "重建必须占回同一业务 ID(设计指定向量)"
    assert str(new_uid) != str(old_uid), "重建必须换代 uid(AC-50 前提)"

    # 成员订阅腿(普通项目其他成员):零派发暂停
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u2)
    assert r.status_code == 200, r.text
    inst = await _inst(tid, uid2)
    assert inst.state == "paused"
    assert inst.paused_reason == "template_changed"
    assert inst.consent_fingerprint == fp0     # 未确认前不刷新

    # 私有所有者自订阅腿(AC-50 指定覆盖):owner 实例同样暂停
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u1)
    assert r.status_code == 200, r.text
    inst1 = await _inst(tid, uid1)
    assert inst1.state == "paused"
    assert inst1.paused_reason == "template_changed"

    # 重新确认 = 再订阅:新身份被知情,恢复调度(两腿各恢复)
    for h, u_ in ((u2, uid2), (u1, uid1)):
        r = await _subscribe(client, h, tid)
        assert r.status_code == 200, r.text
        inst = await _inst(tid, u_)
        assert inst.state == "idle" and inst.paused_reason == ""


async def test_scheme_recreate_pauses_private_owner_self_subscription(client):
    """AC-50 私有所有者自订阅腿:私有模板(引用本人私有场景),删默认
    方案以同业务 ID 同内容重建 → owner 自有实例派发前暂停
    (template_changed;此前 owner 豁免的旧口径与验收矩阵冲突,已收口)。"""
    u1 = await register_and_login(client, "w0a_i", "pw123456")
    await _mk_scenario(client, u1, "sc-w0e")
    r = await client.post("/api/integration/tasks", headers=u1,
                          json=_task_body("sc-w0e", visibility="private",
                                          scenarioId="sc-w0e",
                                          identityMode="personal"))
    assert r.status_code in (200, 201), r.text
    tid = r.json()["id"]
    uid1 = await _user_id("w0a_i")

    from app.models.composer_run_scheme import ComposerRunScheme

    async with db_module.SessionLocal() as s:
        row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-w0e",
            ComposerRunScheme.is_default == True))).scalar_one()
        old = {"scheme_id": row.scheme_id,
               "scenario_id": row.scenario_id,
               "project_id": row.project_id, "name": row.name,
               "is_default": True, "payload": dict(row.payload or {}),
               "account_combo_id": row.account_combo_id,
               "repair_status": "ready", "revision": row.revision}
        await s.delete(row)
        await s.flush()
        s.add(ComposerRunScheme(**old))
        await s.commit()

    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u1)
    assert r.status_code == 200, r.text
    inst = await _inst(tid, uid1)
    assert inst.state == "paused"
    assert inst.paused_reason == "template_changed"
