"""订阅知情同意修复轮(P1/P2.1/P2.2/P2.3/P3.1)。

- P1:锚点步骤的 method/path 在存储面被 strip_binding_fields 剥掉
  (钉定系统),订阅摘要改按 plate 取 binding(钉修订按修订),readonly
  并入 query_safe(POST + query_safe = 读;无标记 = 写)—— 真实第三方
  场景(全锚点)的弹窗不再「空白 + 全标写」;
- P2.1:内容指纹投影纳入 meta.plate —— 主人换修订(1.0#1 → 1.0#2,
  步骤不变)触发订阅者 template_changed 重新确认;
- P2.2:subscribe 回传摘要 fingerprint,与当前内容不一致 → 409
  consent_stale(确认的必须是订阅者看到的那份内容);
- P2.3:转私有后非 owner 实例的两条漏网路径(运行中回 idle 再被调度
  认领 / 凭证复活钩子拉回调度)由执行闸兜住 → paused/made_private
  (转私有后订阅者不可见,HTTP 面已 404,漏网面在调度器 —— 绕过路由
  直调 run_instance,同 test_runner_internal_gate_fails_working_scenario);
- P3.1:保存端 kind 预检走 30s TTL 目录缓存(catalog 行带 kind),
  不再每次保存逐系统 HTTP(以「目录 kind 与 /api/system kind 冲突时
  以目录为准」证缓存路径)。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models.composer_scenario import ComposerScenario
from app.models.integration_task import IntegrationTask
from app.models.user import User
from tests.helpers import make_draft, register_and_login
from tests.test_scenario_composer_plate_integration import (  # noqa: F401
    plate_mock,
)

# 钉定系统的锚点步骤:草稿带内联 method/path(保存时被 strip 剥掉,
# 即 P1 的复现前提 —— 存储里只剩场景自有字段)。
ANCHORED_STEPS = [
    {"kind": "step", "description": "搜索", "endpoint": "jira.search",
     "call": {"service": "jira-svc", "method": "POST",
              "path": "/rest/api/2/search"},
     "request": {"kind": "request", "body": {}}, "strategy": []},
    {"kind": "step", "description": "建单", "endpoint": "jira.createIssue",
     "call": {"service": "jira-svc", "method": "POST",
              "path": "/rest/api/2/issue"},
     "request": {"kind": "request", "body": {}}, "strategy": []},
]

FULLS = {
    "jira.search": {
        "binding": {"method": "POST", "path": "/rest/api/2/search"},
        "metadata": {"query_safe": True}},
    "jira.createIssue": {
        "binding": {"method": "POST", "path": "/rest/api/2/issue"}},
}


def _task_body(sid: str, **over) -> dict:
    body = {"name": "fixes", "scenarioId": sid, "identityMode": "personal",
            "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
            "visibility": "public"}
    body.update(over)
    return body


async def _mk_scenario(client, h, sid: str, plate: dict) -> None:
    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft(sid, steps=ANCHORED_STEPS,
                                          plate=plate, system=["jira"]))
    assert r.status_code in (200, 201), r.text


async def _user_id(username: str) -> int:
    async with db_module.SessionLocal() as db:
        return (await db.execute(select(User).where(
            User.username == username))).scalars().one().id


async def _inst(tpl_id: int, holder: int) -> IntegrationTask | None:
    async with db_module.SessionLocal() as db:
        return (await db.execute(select(IntegrationTask).where(
            IntegrationTask.template_id == tpl_id,
            IntegrationTask.holder_id == holder))).scalar()


async def test_summary_fetches_binding_for_anchored_steps(
    client, plate_mock,
):
    """P1:锚点步骤存储无 method/path,摘要按钉修订从 plate 取 binding,
    readonly 含 query_safe(搜索 POST 但只读)。"""
    plate_mock.fulls.update(FULLS)
    u1 = await register_and_login(client, "fix_a", "pw123456")
    u2 = await register_and_login(client, "fix_b", "pw123456")
    await _mk_scenario(client, u1, "sc-fix1", {"jira": "1.0#1"})
    tid = (await client.post("/api/integration/tasks", headers=u1,
                             json=_task_body("sc-fix1"))).json()["id"]

    # 复现前提:钉定系统的锚点步骤,存储面 method/path 已被剥掉
    async with db_module.SessionLocal() as db:
        row = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-fix1"))).scalar()
        call = row.payload["definition"]["steps"][0]["call"]
        assert "method" not in call and "path" not in call

    r = await client.get(
        f"/api/integration/tasks/{tid}/subscription-summary", headers=u2)
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["steps"][0] == {
        "service": "jira-svc", "method": "POST",
        "path": "/rest/api/2/search", "endpoint": "jira.search",
        "readonly": True,      # query_safe:POST 也可只读
    }
    assert view["steps"][1] == {
        "service": "jira-svc", "method": "POST",
        "path": "/rest/api/2/issue", "endpoint": "jira.createIssue",
        "readonly": False,     # POST 无 query_safe → 写
    }


async def test_fingerprint_covers_meta_plate(client, plate_mock):
    """P2.1:主人换修订(步骤不变)→ 指纹翻转 → 订阅者待重新确认。"""
    plate_mock.fulls.update(FULLS)
    u1 = await register_and_login(client, "fix_c", "pw123456")
    u2 = await register_and_login(client, "fix_d", "pw123456")
    await _mk_scenario(client, u1, "sc-fix2", {"jira": "1.0#1"})
    tid = (await client.post("/api/integration/tasks", headers=u1,
                             json=_task_body("sc-fix2"))).json()["id"]
    uid2 = await _user_id("fix_d")
    await client.post(f"/api/integration/tasks/{tid}/subscribe", headers=u2)

    # 换修订:1.0 线第二个修订(校验面需要),步骤原样
    plate_mock.lines = {"jira": [{"line": "1.0", "revisions": 2,
                                  "latest": "1.0#2"}]}
    r = await client.put("/api/scenarios/sc-fix2", headers=u1, json=make_draft(
        "sc-fix2", steps=ANCHORED_STEPS, plate={"jira": "1.0#2"},
        system=["jira"]))
    assert r.status_code == 200, r.text

    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u2)
    assert r.status_code == 200, r.text
    inst = await _inst(tid, uid2)
    assert inst.state == "paused"
    assert inst.paused_reason == "template_changed"


async def test_subscribe_with_stale_fingerprint_409(client, plate_mock):
    """P2.2:摘要之后内容变了 → 回传旧指纹 409 consent_stale;重拉摘要
    后新指纹通过。"""
    plate_mock.fulls.update(FULLS)
    u1 = await register_and_login(client, "fix_e", "pw123456")
    u2 = await register_and_login(client, "fix_f", "pw123456")
    await _mk_scenario(client, u1, "sc-fix3", {"jira": "1.0#1"})
    tid = (await client.post("/api/integration/tasks", headers=u1,
                             json=_task_body("sc-fix3"))).json()["id"]
    uid2 = await _user_id("fix_f")

    fp1 = (await client.get(
        f"/api/integration/tasks/{tid}/subscription-summary",
        headers=u2)).json()["fingerprint"]
    # 摘要看完后主人改内容(cron 入指纹投影)
    r = await client.patch(f"/api/integration/tasks/{tid}", headers=u1,
                           json={"triggerCron": "*/7 * * * *"})
    assert r.status_code == 200, r.text

    r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                          headers=u2, json={"fingerprint": fp1})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "consent_stale"
    assert await _inst(tid, uid2) is None   # 409 不留半确认实例行

    fp2 = (await client.get(
        f"/api/integration/tasks/{tid}/subscription-summary",
        headers=u2)).json()["fingerprint"]
    assert fp2 != fp1
    r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                          headers=u2, json={"fingerprint": fp2})
    assert r.status_code == 200, r.text
    assert (await _inst(tid, uid2)).consent_fingerprint == fp2


async def test_made_private_gate_covers_leak_paths(client, plate_mock):
    """P2.3:转私有后,运行中回 idle 再被调度/凭证复活拉回的两条漏网
    路径由执行闸兜住 → paused/made_private(联动暂停 = 提前通知)。"""
    from app.services import integration_runner as ir

    plate_mock.fulls.update(FULLS)
    u1 = await register_and_login(client, "fix_g", "pw123456")
    u2 = await register_and_login(client, "fix_h", "pw123456")
    await _mk_scenario(client, u1, "sc-fix4", {"jira": "1.0#1"})
    tid = (await client.post("/api/integration/tasks", headers=u1,
                             json=_task_body("sc-fix4"))).json()["id"]
    uid2 = await _user_id("fix_h")
    await client.post(f"/api/integration/tasks/{tid}/subscribe", headers=u2)
    inst_id = (await _inst(tid, uid2)).id

    r = await client.patch(f"/api/integration/tasks/{tid}", headers=u1,
                           json={"visibility": "private"})
    assert r.status_code == 200, r.text

    # 漏网路径①:转私有那一刻在跑,回 idle 后再次被认领执行
    # (HTTP 面订阅者已 404 不可见,漏网面在调度器 → 直调 run_instance)
    async with db_module.SessionLocal() as db:
        row = await db.get(IntegrationTask, inst_id)
        row.state = "idle"      # 模拟运行结束回 idle
        await db.commit()
    await ir.run_instance(inst_id)
    inst = await _inst(tid, uid2)
    assert inst.state == "paused" and inst.paused_reason == "made_private"

    # 漏网路径②:缺凭证暂停的实例,订阅者补凭证 → 复活钩子只看暂停
    # 原因拉回 idle,下拍即撞同一道闸
    async with db_module.SessionLocal() as db:
        row = await db.get(IntegrationTask, inst_id)
        row.state = "paused"
        row.paused_reason = "missing_credential"
        await db.commit()
    assert await ir.revive_paused_instances(uid2) == 1
    assert (await _inst(tid, uid2)).state == "idle"   # 复活钩子确实拉回了
    await ir.run_instance(inst_id)
    inst = await _inst(tid, uid2)
    assert inst.state == "paused" and inst.paused_reason == "made_private"


async def test_save_kind_precheck_uses_catalog_cache(
    client, plate_mock,
):
    """P3.1:kind 预检先读目录缓存 —— 目录行 kind=integration 而
    /api/system 回 sut(若走 HTTP 会被拒),声明 integration 保存成功
    即证缓存路径;目录 kind=sut 的系统声明 integration 仍拒。"""
    # 目录(b2-7 唯一访问件,30s TTL):jira 行带 kind=integration,
    # fin 行带 kind=sut;HTTP 面 system_kinds 故意与之冲突。
    plate_mock.services = [
        {"name": "jira-svc", "system": "jira", "kind": "integration"},
        {"name": "fin-svc", "system": "fin", "kind": "sut"},
    ]
    plate_mock.system_kinds = {"jira": "sut", "fin": "sut"}
    u = await register_and_login(client, "fix_i", "pw123456")

    steps = [{
        "kind": "step", "description": "x", "endpoint": "jira.search",
        "call": {"service": "jira-svc"},
        "request": {"kind": "request", "body": {}}, "strategy": [],
    }]
    r = await client.post("/api/scenarios", headers=u, json=make_draft(
        "sc-fix5", steps=steps, plate={"jira": "integration"},
        system=["jira"]))
    assert r.status_code in (200, 201), r.text   # 目录 kind 放行(非 HTTP)

    steps_fin = [{
        "kind": "step", "description": "x", "endpoint": "fin.a",
        "call": {"service": "fin-svc"},
        "request": {"kind": "request", "body": {}}, "strategy": [],
    }]
    r = await client.post("/api/scenarios", headers=u, json=make_draft(
        "sc-fix6", steps=steps_fin, plate={"fin": "integration"}))
    assert r.status_code == 422, r.text   # 目录 kind=sut → 拒(缓存口径仍拒)
    assert "meta_plate_invalid_ref" in r.text
