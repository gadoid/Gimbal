"""外部系统集成 P1:cron 解析 + 模板 CRUD/只读闸/手动执行 + 卡片批量。

- cron_expr:五段子集解析 + next_fire(分段跳、2/29 位面)+ 人话摘要;
- integration 路由:P1 只开放平台模式;只读闸(保存前 + 执行前);
  软删;冷却;平台凭证 admin 闸;
- integration_runner:is_scenario_read_only + state_vars 脱敏(E1)
  + on_change 只在翻转时落(评审 E7);
- 平台系统用户:登录拒绝(0015 闸)。
执行链(compose→convert→materialize→通道)在路由手动执行测试里以
打桩通道验证接线;gimbal 真执行由引擎侧测试覆盖(P1 不动执行器)。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core import db as db_module
from app.models.integration_task import IntegrationTask
from app.models.user import User
from app.services.cron_expr import CronError, next_fire, parse_cron
from tests.helpers import make_draft, register_and_login
from tests.test_scenario_composer_plate_integration import (  # noqa: F401
    plate_mock,
)

STEPS_GET = [{
    "kind": "step", "description": "探活",
    "call": {"service": "platform.health", "method": "GET", "path": "/api/health"},
    "request": {"kind": "request", "body": {}},
    "strategy": [],
}]
STEPS_POST = [{
    "kind": "step", "description": "下单",
    "call": {"service": "fin.order", "method": "POST", "path": "/x"},
    "request": {"kind": "request", "body": {"amount": 1}},
    "strategy": [],
}]


def _task_body(sid: str, **over) -> dict:
    body = {
        "name": "保活探针", "scenarioId": sid, "identityMode": "platform",
        "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
        "visibility": "private",
    }
    body.update(over)
    return body


async def _mk_scenario(client: AsyncClient, h: dict, sid: str,
                       steps: list) -> None:
    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft(sid, steps=steps))
    assert r.status_code in (200, 201), r.text


async def _seed_platform_user() -> None:
    from app.core.security import hash_password
    async with db_module.SessionLocal() as db:
        exists = (await db.execute(
            select(User).where(User.is_system == True))).scalar()  # noqa: E712
        if exists is None:
            db.add(User(
                username="__platform__", display_name="平台系统",
                password_hash=hash_password("x"), is_system=True))
            await db.commit()


# ── cron_expr ────────────────────────────────────────────────────

class TestCronExpr:
    def test_every_n_minutes(self):
        m, h, dom, mon, dow = parse_cron("*/5 * * * *")
        assert m == {0, 5, 10, 55} | {x for x in range(0, 60, 5)}
        assert h == set(range(24))

    def test_range_step_and_list(self):
        m, h, *_ = parse_cron("0,30 8-18/2 * * 1-5")
        assert m == {0, 30}
        assert h == {8, 10, 12, 14, 16, 18}

    def test_invalid_shapes(self):
        for bad in ["* * * *", "*/0 * * * *", "61 * * * *", "0 25 * * *",
                    "a * * * *", "5-1 * * * *"]:
            with pytest.raises(CronError):
                parse_cron(bad)

    def test_next_fire_steps(self):
        t = datetime(2026, 10, 9, 10, 2)
        assert next_fire("*/5 * * * *", t) == datetime(2026, 10, 9, 10, 5)
        assert next_fire("*/5 * * * *", datetime(2026, 10, 9, 10, 5)) \
            == datetime(2026, 10, 9, 10, 10)
        # 日/周位面:10-09(周五)不命中周日-only → 跳到 10-11
        assert next_fire("0 9 * * 0", datetime(2026, 10, 9, 10)) \
            == datetime(2026, 10, 11, 9, 0)
        # 月位面:2/29 只在闰年(2028)
        t2 = datetime(2027, 1, 1, 0, 0)
        assert next_fire("0 0 29 2 *", t2) == datetime(2028, 2, 29, 0, 0)


# ── 只读护栏 + E1 脱敏 ──────────────────────────────────────────

class TestReadOnlyAndScrub:
    @pytest.mark.asyncio
    async def test_read_only_check(self):
        from app.services.integration_runner import is_scenario_read_only
        payload_get = {"definition": {"steps": STEPS_GET}}
        ok, offenders = await is_scenario_read_only(payload_get)
        assert ok and not offenders
        payload_post = {"definition": {"steps": STEPS_GET + STEPS_POST}}
        ok, offenders = await is_scenario_read_only(payload_post)
        assert not ok and any("POST" in o for o in offenders)

    @pytest.mark.asyncio
    async def test_read_only_anchored_method_from_plate(self, monkeypatch):
        """Release 6.2:锚点步骤不存 method —— 只读闸从 plate 契约解析;
        契约不可得即 fail-closed(不得放行)。"""
        from types import SimpleNamespace

        from app.services import plate_client
        from app.services.integration_runner import is_scenario_read_only

        anchored = {"kind": "step", "call": {"service": "fin"},
                    "request": {"kind": "request", "body": {}},
                    "strategy": []}

        async def fake_full(eid: str, **kw):
            method = "GET" if "report" in eid else "POST"
            return SimpleNamespace(item={"binding": {"method": method}})

        monkeypatch.setattr(plate_client, "get_endpoint_full", fake_full)
        ok, offenders = await is_scenario_read_only({"definition": {"steps": [
            {**anchored, "endpoint": "fin.report.page"}]}})
        assert ok and not offenders
        ok, offenders = await is_scenario_read_only({"definition": {"steps": [
            {**anchored, "endpoint": "fin.order.add"}]}})
        assert not ok and any("POST" in o for o in offenders)

        async def none_full(eid: str, **kw):
            return SimpleNamespace(item=None)

        monkeypatch.setattr(plate_client, "get_endpoint_full", none_full)
        ok, offenders = await is_scenario_read_only({"definition": {"steps": [
            {**anchored, "endpoint": "fin.report.page"}]}})
        assert not ok and any("未知" in o for o in offenders)

    def test_scrub_sensitive_keys(self):
        from app.services.integration_runner import _scrub
        data = {"token": "abc", "nested": {"accessToken": "x", "ok": 1}}
        _scrub(data)
        assert data["token"] == "***"
        assert data["nested"]["accessToken"] == "***"
        assert data["nested"]["ok"] == 1


# ── 路由:模板 CRUD / 只读闸 / 软删 / 凭证闸 ─────────────────────

@pytest.mark.asyncio
class TestIntegrationRouter:
    async def test_platform_user_cannot_login(self, client):
        await _seed_platform_user()
        r = await client.post("/api/auth/login", json={
            "username": "__platform__", "password": "x"})
        assert r.status_code == 401

    async def test_platform_user_hidden_from_lists(self, client):
        h = await register_and_login(client, "ig_list", "ig_listpass123")
        await _seed_platform_user()
        r = await client.get("/api/users", headers=h)
        assert all(u["username"] != "__platform__"
                   for u in r.json()["items"])

    async def test_create_rejects_write_scenario_and_bad_cron(self, client):
        h = await register_and_login(client, "ig_mk", "ig_mkpass123")
        await _mk_scenario(client, h, "sc-ig-post", STEPS_POST)
        # 写场景 → 只读闸拒
        r = await client.post("/api/integration/tasks", headers=h,
                              json=_task_body("sc-ig-post"))
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "not_read_only"
        # cron 坏 → 拒
        await _mk_scenario(client, h, "sc-ig-get", STEPS_GET)
        r = await client.post("/api/integration/tasks", headers=h,
                              json=_task_body("sc-ig-get", triggerCron="bad"))
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "cron_invalid"
        # Y3:个人模式已解禁(201);坏 identityMode 仍 422
        r = await client.post("/api/integration/tasks", headers=h,
                              json=_task_body("sc-ig-get", identityMode="personal"))
        assert r.status_code == 201, r.text
        r = await client.post("/api/integration/tasks", headers=h,
                              json=_task_body("sc-ig-get", identityMode="bogus"))
        assert r.status_code == 422
        # 他人场景 → 拒
        h2 = await register_and_login(client, "ig_mk2", "ig_mk2pass123")
        r = await client.post("/api/integration/tasks", headers=h2,
                              json=_task_body("sc-ig-get"))
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "scenario_not_owned"

    async def test_create_ok_and_instance_seeded(self, client):
        await _seed_platform_user()
        h = await register_and_login(client, "ig_ok", "ig_okpass123")
        await _mk_scenario(client, h, "sc-ig-ok", STEPS_GET)
        r = await client.post("/api/integration/tasks", headers=h,
                              json=_task_body("sc-ig-ok", visibility="public"))
        assert r.status_code == 201, r.text
        out = r.json()
        assert out["identityMode"] == "platform"
        assert out["cronText"].startswith("每 5 分钟")
        assert out["instance"]["state"] in ("idle", "none")

    async def test_soft_delete_and_visibility(self, client):
        await _seed_platform_user()
        h = await register_and_login(client, "ig_del", "ig_delpass123")
        await _mk_scenario(client, h, "sc-ig-del", STEPS_GET)
        r = await client.post("/api/integration/tasks", headers=h,
                              json=_task_body("sc-ig-del", visibility="public"))
        tid = r.json()["id"]
        # 其他人可见公共模板
        h2 = await register_and_login(client, "ig_del2", "ig_del2pass123")
        r = await client.get("/api/integration/tasks", headers=h2)
        assert any(t["id"] == tid for t in r.json()["items"])
        # 非 owner/admin 改/删 → 403
        r = await client.delete(f"/api/integration/tasks/{tid}", headers=h2)
        assert r.status_code == 403
        # owner 软删 → 双方都不可见
        r = await client.delete(f"/api/integration/tasks/{tid}", headers=h)
        assert r.status_code == 200
        for hh in (h, h2):
            r = await client.get("/api/integration/tasks", headers=hh)
            assert all(t["id"] != tid for t in r.json()["items"])

    async def test_cards_batch_removed_for_strangers(self, client):
        await _seed_platform_user()
        h = await register_and_login(client, "ig_card", "ig_cardpass123")
        await _mk_scenario(client, h, "sc-ig-card", STEPS_GET)
        r = await client.post("/api/integration/tasks", headers=h,
                              json=_task_body("sc-ig-card"))
        tid = r.json()["id"]
        # 本人批量取卡 → idle;陌生人 → removed(私有模板)
        r = await client.post("/api/integration/cards", headers=h,
                              json={"ids": [f"fn:{tid}", "notfn", "fn:x"]})
        items = {i["id"]: i for i in r.json()["items"]}
        assert items[f"fn:{tid}"]["state"] in ("idle", "none", "running")
        h2 = await register_and_login(client, "ig_card2", "ig_card2pass123")
        r = await client.post("/api/integration/cards", headers=h2,
                              json={"ids": [f"fn:{tid}"]})
        assert r.json()["items"][0]["state"] == "removed"

    async def test_platform_credentials_admin_gate(self, client):
        await _seed_platform_user()
        # 首个真人注册者成为 admin(系统用户不计 —— 整体评审 2026-10-15
        # 首个 admin 引导修复);先占掉首位,ig_cred 才是普通用户
        await register_and_login(client, "ig_first", "ig_firstpass123")
        h = await register_and_login(client, "ig_cred", "ig_credpass123")
        r = await client.get("/api/integration/platform-credentials", headers=h)
        assert r.status_code == 403
        # 提权 admin(测试内直改库)
        async with db_module.SessionLocal() as db:
            u = (await db.execute(select(User).where(
                User.username == "ig_cred"))).scalar()
            u.role = "admin"
            await db.commit()
        r = await client.post("/api/integration/platform-credentials",
                              headers=h, json={
                                  "alias": "gitlab-bot", "url": "https://git.example",
                                  "username": "bot", "password": "secret"})
        assert r.status_code == 201, r.text
        r = await client.get("/api/integration/platform-credentials", headers=h)
        row = next(c for c in r.json()["items"] if c["alias"] == "gitlab-bot")
        assert row["username"] == "bot"      # 解密回显(admin 面)
        # 凭证确实挂在平台系统用户名下
        async with db_module.SessionLocal() as db:
            from app.models.auth_session import AuthSession
            owner = (await db.execute(select(AuthSession.owner_id).where(
                AuthSession.alias == "gitlab-bot"))).scalar()
            sysid = (await db.execute(select(User.id).where(
                User.is_system == True))).scalar()  # noqa: E712
        assert owner == sysid

    async def test_manual_run_happy_path(self, client, monkeypatch):
        """手动执行:打桩通道 + 真 plate convert(测试环境 plate_mock/
        convert 透传由 conftest 决定;这里直接双桩走通接线)。"""
        await _seed_platform_user()
        h = await register_and_login(client, "ig_run", "ig_runpass123")
        await _mk_scenario(client, h, "sc-ig-run", STEPS_GET)
        r = await client.post("/api/integration/tasks", headers=h,
                              json=_task_body("sc-ig-run"))
        tid = r.json()["id"]

        # 桩:plate convert 透传 + 通道回 passed
        from app.services import plate_client as pc
        from app.services import integration_runner as ir

        async def _fake_convert(scenario):
            return {"consumer": "platform", "converted": dict(scenario)}
        monkeypatch.setattr(pc, "convert", _fake_convert)

        class _FakeResult:
            # I2:与 LaunchResult 真实字段对齐(launch_status/exit_code/
            # details;旧 run_result counts-only 投影没有 status/details)
            launch_status = "ok"
            exit_code = 0
            error = ""
            # G2/Y2:outputs = details[].outputs(执行器已脱敏);顶层
            # token 形态不再进 last_outputs(载荷不是业务输出)
            details = [{"scenario_id": "sc-ka", "outputs": {
                "token": "should-be-scrubbed",
                "order_id": "O1"}}]

        class _FakeChannels:
            async def run_case(self, case_path):
                return _FakeResult()

            async def reap_idle(self):
                return 0

        monkeypatch.setattr(ir, "channels", _FakeChannels())
        # materialize 原样(不依赖真实 services 物化细节)
        monkeypatch.setattr(
            ir, "materialize_run_copy",
            lambda converted, **kw: dict(converted))

        r = await client.post(f"/api/integration/tasks/{tid}/run", headers=h)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["result"]["status"] == "passed"
        # I3.5:旧 lastStatus 出参已删,新字段判 run/check
        assert out["instance"]["runStatus"] == "ok"
        assert out["instance"]["checkStatus"] == "none"
        # E1:outputs 内敏感键被脱敏
        async with db_module.SessionLocal() as db:
            inst = (await db.execute(select(IntegrationTask).where(
                IntegrationTask.template_id == tid))).scalar()
            assert inst.last_outputs["token"] == "***"
            assert inst.last_outputs["order_id"] == "O1"
        # 冷却:60s 内再点 → 409
        r = await client.post(f"/api/integration/tasks/{tid}/run", headers=h)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "cooldown"

    async def test_manual_run_rejects_working_preview(self, client, plate_mock):
        """A-4/W6(版本模型 §6):任一受管系统 working(含未钉修订)→
        409 拒触发;钉定后过闸(只验闸,不验执行)。"""
        await _seed_platform_user()
        h = await register_and_login(client, "ig_wp", "ig_wppass123")
        anchored = [{
            "kind": "step", "description": "查单",
            "endpoint": "fin.orders.get",
            "call": {"service": "fin.order", "method": "GET", "path": "/o"},
            "request": {"kind": "request", "body": {}},
            "strategy": [],
        }]
        # C-1/C-2 后 make_draft 缺省声明 working → 保存剥离 call.method →
        # Y5 只读闸的 method 权威 = plate 工作面(/full);注入条目供判定。
        plate_mock.fulls["fin.orders.get"] = {"binding": {"method": "GET"}}
        await _mk_scenario(client, h, "sc-ig-wp", anchored)
        tid = (await client.post("/api/integration/tasks", headers=h,
                                 json=_task_body("sc-ig-wp"))).json()["id"]

        # 未钉修订(锚点系统缺声明)→ 409 working_preview
        r = await client.post(f"/api/integration/tasks/{tid}/run", headers=h)
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "working_preview"

        # 显式 working → 同样 409
        d = make_draft("sc-ig-wp", steps=anchored, plate={"fin": "working"})
        assert (await client.put(
            "/api/scenarios/sc-ig-wp", headers=h, json=d)).status_code == 200
        r = await client.post(f"/api/integration/tasks/{tid}/run", headers=h)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "working_preview"

        # 钉定 → 过闸(后续执行成败与本闸无关,只断言不再是 working_preview)
        d = make_draft("sc-ig-wp", steps=anchored, plate={"fin": "1.0#1"})
        assert (await client.put(
            "/api/scenarios/sc-ig-wp", headers=h, json=d)).status_code == 200
        r = await client.post(f"/api/integration/tasks/{tid}/run", headers=h)
        assert not (r.status_code == 409 and
                    r.json()["detail"]["code"] == "working_preview"), r.text

    async def test_runner_internal_gate_fails_working_scenario(self, client, plate_mock):
        """A-4/W6 调度路径兜底闸:绕过路由直调 run_instance,场景 working
        → 实例 failed + 文案指路(外部服务/无锚点不受影响)。"""
        await _seed_platform_user()
        h = await register_and_login(client, "ig_wp2", "ig_wp2pass123")
        anchored = [{
            "kind": "step", "description": "查单",
            "endpoint": "fin.orders.get",
            "call": {"service": "fin.order", "method": "GET", "path": "/o"},
            "request": {"kind": "request", "body": {}},
            "strategy": [],
        }]
        plate_mock.fulls["fin.orders.get"] = {"binding": {"method": "GET"}}
        await _mk_scenario(client, h, "sc-ig-wp2", anchored)
        await client.post("/api/integration/tasks", headers=h,
                          json=_task_body("sc-ig-wp2"))
        from app.services import integration_runner as ir
        async with db_module.SessionLocal() as db:
            tpl = (await db.execute(select(IntegrationTask).where(
                IntegrationTask.scenario_id == "sc-ig-wp2",
                IntegrationTask.template_id.is_(None)))).scalar_one()
            inst = await ir.ensure_instance(tpl)
            out = await ir.run_instance(inst.id)
        assert out["status"] == "failed"
        assert "拒绝触发" in (out.get("error") or "")

    async def test_runner_readonly_gate_plate_unreachable_closes_channel(
            self, client, plate_mock, monkeypatch):
        """合入评估 §2-3:钉定修订场景只读闸的 /full?ref= 取数
        (get_endpoint_full_at 连接失败/5xx 即抛)遇 plate 不可达时收口
        run=channel + 固定前缀 —— 裸抛会被 _spawn 吞成 warning,实例
        卡 running 到租约回收。working 声明走 fail-soft 的
        get_endpoint_full(item=None → 「未知方法」offender),本就收口。"""
        await _seed_platform_user()
        h = await register_and_login(client, "ig_pdown", "ig_pdown123")
        anchored = [{
            "kind": "step", "description": "查单",
            "endpoint": "fin.orders.get",
            "call": {"service": "fin.order", "method": "GET", "path": "/o"},
            "request": {"kind": "request", "body": {}},
            "strategy": [],
        }]
        plate_mock.fulls["fin.orders.get"] = {"binding": {"method": "GET"}}
        pinned = make_draft("sc-ig-pdown", steps=anchored,
                            plate={"fin": "1.0#1"})
        assert (await client.post(
            "/api/scenarios", headers=h, json=pinned)).status_code in (200, 201)
        await client.post("/api/integration/tasks", headers=h,
                          json=_task_body("sc-ig-pdown"))
        from app.services import integration_runner as ir
        from app.services import plate_client

        async def _unreachable(endpoint_id, ref, **kw):
            raise plate_client.PlateUnavailableError(
                f"plate_unavailable: connection refused ({endpoint_id}@{ref})")

        monkeypatch.setattr(plate_client, "get_endpoint_full_at", _unreachable)
        async with db_module.SessionLocal() as db:
            tpl = (await db.execute(select(IntegrationTask).where(
                IntegrationTask.scenario_id == "sc-ig-pdown",
                IntegrationTask.template_id.is_(None)))).scalar_one()
            inst = await ir.ensure_instance(tpl)
            out = await ir.run_instance(inst.id)
        assert out["status"] == "failed"
        assert (out.get("error") or "") == "只读检查未通过: plate 不可达"
        async with db_module.SessionLocal() as db:
            row = await db.get(IntegrationTask, inst.id)
            assert row.run_status == "channel"
            assert row.state == "idle"   # 收口,不再卡 running
            assert row.last_error == "只读检查未通过: plate 不可达"


# ── Y2(G7):auth 类失败暂停实例 + 凭证复活钩子 ────────────────────

async def test_auth_failure_pauses_instance_and_revives(client):
    """error_kind=auth → _finish 暂停(paused/auth_failed,不重试);
    revive_paused_instances 恢复 idle;manual 暂停不受影响。"""
    from datetime import datetime, timezone

    from app.core import db as db_module
    from app.models.integration_task import IntegrationTask
    from app.services import integration_runner as ir

    admin = await register_and_login(client, "authrev_admin", "pw123456")
    uid = 1
    # PG 强制 holder 外键 —— uid+1 的对照实例持有人垫底
    from tests.helpers import ensure_fk_users
    async with db_module.SessionLocal() as s:
        await ensure_fk_users(s, uid + 1)

    async with db_module.SessionLocal() as s:
        s.add(IntegrationTask(
            name="平台探针", owner_id=uid, visibility="public",
            identity_mode="platform", scenario_id="sc-x",
            target_system="fin", trigger_cron="*/5 * * * *",
            result_policy="latest", template_id=None))
        await s.commit()
        tpl_id = (await s.execute(
            __import__("sqlalchemy").select(IntegrationTask.id).order_by(
                IntegrationTask.id.desc()))).scalars().first()
        s.add(IntegrationTask(
            name="平台探针", owner_id=uid, holder_id=uid, template_id=tpl_id,
            enabled=True, state="idle",
            next_run_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        # manual 暂停的对照实例
        s.add(IntegrationTask(
            name="手动暂停", owner_id=uid, holder_id=uid + 1,
            template_id=tpl_id,
            enabled=True, state="paused", paused_reason="manual"))
        await s.commit()
        # 精确取目标实例(holder=uid 的"平台探针"),不按最新 id(后插
        # 的 manual 行会抢位)
        from sqlalchemy import select as _sel
        inst_id = (await s.execute(_sel(IntegrationTask.id).where(
            IntegrationTask.template_id == tpl_id,
            IntegrationTask.holder_id == uid))).scalars().first()

    async with db_module.SessionLocal() as s:
        inst = await s.get(IntegrationTask, inst_id)
        tpl = await s.get(IntegrationTask, tpl_id)
        out = await ir._finish(s, inst, tpl, "auth", "401 Unauthorized")
        assert out["status"] == "failed"          # D11 投影:auth → failed
        assert inst.state == "paused" and inst.paused_reason == "auth_failed"
        assert inst.fail_streak == 1
        assert inst.run_status == "auth"

    # 复活:平台凭证信号(平台模式不过滤 user_id)
    assert await ir.revive_paused_instances(user_id=99) >= 1
    async with db_module.SessionLocal() as s:
        inst = await s.get(IntegrationTask, inst_id)
        assert inst.state == "idle" and inst.paused_reason in (None, "")
        # manual 暂停不受影响
        manual = (await s.execute(
            __import__("sqlalchemy").select(IntegrationTask).where(
                IntegrationTask.paused_reason == "manual"))).scalars().first()
        assert manual is not None and manual.state == "paused"

    _ = admin


async def test_non_auth_failure_keeps_running(client):
    """普通失败不暂停(照常 idle,fail_streak 累计)——P1 行为不变。"""
    from app.core import db as db_module
    from app.models.integration_task import IntegrationTask
    from app.services import integration_runner as ir

    await register_and_login(client, "authrev2_admin", "pw123456")
    async with db_module.SessionLocal() as s:
        s.add(IntegrationTask(
            name="普通失败", owner_id=1, visibility="public",
            identity_mode="platform", scenario_id="sc-x",
            target_system="fin", trigger_cron="*/5 * * * *",
            result_policy="latest"))
        await s.commit()
        tpl_id = (await s.execute(
            __import__("sqlalchemy").select(IntegrationTask.id).order_by(
                IntegrationTask.id.desc()))).scalars().first()
        s.add(IntegrationTask(
            name="普通失败", owner_id=1, holder_id=1, template_id=tpl_id,
            enabled=True, state="idle"))
        await s.commit()
        inst_id = (await s.execute(
            __import__("sqlalchemy").select(IntegrationTask.id).order_by(
                IntegrationTask.id.desc()))).scalars().first()

    async with db_module.SessionLocal() as s:
        inst = await s.get(IntegrationTask, inst_id)
        tpl = await s.get(IntegrationTask, tpl_id)
        await ir._finish(s, inst, tpl, "transport", "connect refused")
        assert inst.state == "idle" and inst.paused_reason in (None, "")
        assert inst.run_status == "transport"


# ── Y5:只读闸 ext: 锚点分支 ──────────────────────────────────────

async def test_read_only_gate_ext_anchor(client):
    """ext: 锚点步骤 method 出外部目录:GET 放行;POST 拒;条目缺
    fail-closed;ext 步骤带存储 method 的直接用(手写调用同款)。"""
    from app.core import db as db_module
    from app.models.external_endpoint import ExternalEndpoint
    from app.models.service_alias import ServiceAlias
    from app.services.integration_runner import is_scenario_read_only

    await register_and_login(client, "gate_admin", "pw123456")
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="gitlab-g", base_service="gitlab",
                           base_url="https://git", kind="external"))
        # PG 强制 external_endpoints.alias_name 外键 —— 别名先落库
        await s.flush()
        s.add(ExternalEndpoint(alias_name="gitlab-g", name="mr-list",
                               title="MR", method="GET", path="/mr"))
        s.add(ExternalEndpoint(alias_name="gitlab-g", name="mr-create",
                               title="建MR", method="POST",
                               path="/mr", request_schema=None))
        await s.commit()

    def _payload(ep: str | None) -> dict:
        step = {"kind": "step",
                "call": {"protocol": "http", "service": "gitlab-g",
                         "headers": {}},
                "request": {"kind": "request", "body": {}}, "strategy": []}
        if ep:
            step["endpoint"] = ep
        return {"definition": {"meta": {"name": "n"}, "steps": [step]}}

    # b2-11(归一 v1.0 §2.1/C5):ext: DB 分支已删 —— 过渡期口径(§3.5):
    # 目录不再被读;无内联 method 的 ext: 一律 fail-closed;
    # 带内联 method 按方法判定(GET 放行/POST 拒)。
    ok, offenders = await is_scenario_read_only(_payload("ext:gitlab-g.mr-list"))
    assert not ok and offenders, "无内联 method → fail-closed"

    p = _payload("ext:gitlab-g.mr-list")
    p["definition"]["steps"][0]["call"]["method"] = "GET"
    ok, _ = await is_scenario_read_only(p)
    assert ok

    p = _payload("ext:gitlab-g.mr-create")
    p["definition"]["steps"][0]["call"]["method"] = "POST"
    ok, offenders = await is_scenario_read_only(p)
    assert not ok and "POST" in offenders[0]


# ── Y3:个人模式(写操作放行/订阅实例/无冷却/missing_credential)────

async def test_personal_mode_lifecycle(client):
    """Y3 核心链:personal 模板建即有 owner 订阅实例;另一用户首次
    触发 = 订阅即建;写操作(POST 步骤)个人模式放行;无冷却。"""
    from app.core import db as db_module
    from sqlalchemy import select as _sel

    u1 = await register_and_login(client, "p1_alice", "pw123456")
    u2 = await register_and_login(client, "p1_bob", "pw123456")

    # 个人模板:场景带 POST 步骤(平台模式会拒)→ 201
    draft = make_draft("sc-p1", steps=[{
        "kind": "step",
        "call": {"protocol": "http", "service": "svc",
                 "method": "POST", "path": "/push", "headers": {}},
        "request": {"kind": "request", "body": {}}, "strategy": []}])
    r = await client.post("/api/scenarios", headers=u1, json=draft)
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/integration/tasks", headers=u1, json=_task_body(
        "sc-p1", identityMode="personal", visibility="public"))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    async with db_module.SessionLocal() as s:
        from app.models.integration_task import IntegrationTask
        rows = (await s.execute(_sel(IntegrationTask).where(
            IntegrationTask.template_id == tid))).scalars().all()
        # 创建即订阅:owner 的实例在(个人模式不建平台实例)
        assert len(rows) == 1 and rows[0].holder_id is not None

    # u2 首次立即执行 = 订阅即建(不等通道真跑,断实例已建)
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u2)
    assert r.status_code in (200, 500), r.text   # 无凭证/场景细节失败皆可
    async with db_module.SessionLocal() as s:
        from app.models.integration_task import IntegrationTask
        rows = (await s.execute(_sel(IntegrationTask).where(
            IntegrationTask.template_id == tid))).scalars().all()
        assert len(rows) == 2                     # u1 + u2 各一份


async def test_personal_manual_run_no_cooldown(client, monkeypatch):
    """个人模式手动执行无冷却(方案 §3 操作表);平台模式 60s 冷却不变。"""
    from app.services import integration_runner as ir

    u = await register_and_login(client, "p2_alice", "pw123456")
    draft = make_draft("sc-p2", steps=[{
        "kind": "step",
        "call": {"protocol": "http", "service": "svc",
                 "method": "GET", "path": "/x", "headers": {}},
        "request": {"kind": "request", "body": {}}, "strategy": []}])
    await client.post("/api/scenarios", headers=u, json=draft)
    r = await client.post("/api/integration/tasks", headers=u, json=_task_body(
        "sc-p2", identityMode="personal"))
    tid = r.json()["id"]

    calls = {"n": 0}

    async def _fake_run(inst_id):
        calls["n"] += 1
        # 模拟 _finish 收口:state 回 idle(真链路在独立会话回写)
        from app.core import db as _dbm
        from app.models.integration_task import IntegrationTask as _IT
        async with _dbm.SessionLocal() as s:
            row = await s.get(_IT, inst_id)
            if row is not None:
                row.state = "idle"
                await s.commit()
        return {"status": "passed", "durationMs": 1, "error": ""}

    monkeypatch.setattr(ir, "run_instance", _fake_run)
    for _ in range(2):                       # 连点两次
        r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u)
        assert r.status_code == 200, r.text
    assert calls["n"] == 2                   # 无冷却,两次都跑


async def test_missing_credential_pauses_and_revives(client, monkeypatch):
    """Y3/方案 §8:场景引 ${auth.*} 而订阅者无该凭证 → 实例
    paused/missing_credential;凭证补齐(复活钩子)→ idle。"""
    from app.core import db as db_module
    from sqlalchemy import select as _sel
    from app.models.integration_task import IntegrationTask
    from app.services import integration_runner as ir

    u = await register_and_login(client, "p3_alice", "pw123456")
    draft = make_draft("sc-p3", steps=[{
        "kind": "step",
        "call": {"protocol": "http", "service": "svc",
                 "method": "GET", "path": "/x",
                 "headers": {"Authorization": "${auth.gitlab.token}"}},
        "request": {"kind": "request", "body": {}}, "strategy": []}])
    await client.post("/api/scenarios", headers=u, json=draft)
    r = await client.post("/api/integration/tasks", headers=u, json=_task_body(
        "sc-p3", identityMode="personal"))
    tid = r.json()["id"]

    # run_instance 真跑(resolve 解不到凭证 → missing_credential);
    # plate/通道不真发(precheck 之前就停在凭证段)
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u)
    assert r.status_code == 200, r.text          # run_instance 内部收口

    async with db_module.SessionLocal() as s:
        inst = (await s.execute(_sel(IntegrationTask).where(
            IntegrationTask.template_id == tid))).scalars().one()
        assert inst.state == "paused"
        assert inst.paused_reason == "missing_credential"

    # 凭证补齐 → 复活
    assert await ir.revive_paused_instances(user_id=1) >= 1
    async with db_module.SessionLocal() as s:
        s.expire_all()
        inst = (await s.execute(_sel(IntegrationTask).where(
            IntegrationTask.template_id == tid))).scalars().one()
        assert inst.state == "idle"


# ── Y4:state_mapping 跨次游标 + cards 输出投影 ────────────────────

async def test_state_mapping_cursor_roundtrip(client, monkeypatch):
    """state_mapping 命中的输出回写 state_vars;下次执行注入为变量
    (调用点合并 —— 数据集行覆盖优先)。"""
    from app.core import db as db_module
    from sqlalchemy import select as _sel
    from app.models.integration_task import IntegrationTask
    from app.services import integration_runner as ir

    u = await register_and_login(client, "p4_alice", "pw123456")
    draft = make_draft("sc-p4", steps=[{
        "kind": "step",
        "call": {"protocol": "http", "service": "svc",
                 "method": "GET", "path": "/x", "headers": {}},
        "request": {"kind": "request", "body": {}}, "strategy": []}])
    await client.post("/api/scenarios", headers=u, json=draft)
    r = await client.post("/api/integration/tasks", headers=u, json=_task_body(
        "sc-p4", identityMode="personal"))
    tid = r.json()["id"]

    async with db_module.SessionLocal() as s:
        tpl = await s.get(IntegrationTask, tid)
        tpl.state_mapping = {"updated_at": "since"}   # 输出键 → 状态键
        await s.commit()

    # 直接驱动 _finish:命中键回写、未命中不动
    async with db_module.SessionLocal() as s:
        inst = (await s.execute(_sel(IntegrationTask).where(
            IntegrationTask.template_id == tid))).scalars().one()
        tpl = await s.get(IntegrationTask, tid)
        await ir._finish(s, inst, tpl, "ok", "",
                         check_status="pass",
                         outputs={"updated_at": "2026-10-12T10:00:00Z",
                                  "other": "x"})
        assert inst.state_vars == {"since": "2026-10-12T10:00:00Z"}

    # 注入链:run_instance 的组合调用点合并 state_vars(经通道产物断言)
    seen: dict = {}

    class _FakeResult:
        launch_status = "ok"
        exit_code = 0
        error = ""
        details = [{"scenario_id": "sc-p4", "outputs": {
            "updated_at": "2026-10-12T11:00:00Z"}}]

    class _FakeChannels:
        async def run_case(self, case_path):
            import json as _json
            seen["case"] = _json.loads(
                case_path.read_text(encoding="utf-8"))
            return _FakeResult()

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import plate_client as pc
    monkeypatch.setattr(ir, "channels", _FakeChannels())
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=u)
    assert r.status_code == 200, r.text
    # case.json 的 config.vars 带游标(since 注入)
    vars_ = (seen.get("case") or {}).get("config", {}).get("vars", {})
    assert vars_.get("since") == "2026-10-12T10:00:00Z"
    # 新输出回写推进游标
    async with db_module.SessionLocal() as s:
        s.expire_all()
        inst = (await s.execute(_sel(IntegrationTask).where(
            IntegrationTask.template_id == tid))).scalars().one()
        assert inst.state_vars == {"since": "2026-10-12T11:00:00Z"}


async def test_cards_output_projection(client):
    """cards 出参带 outputs:output_mapping 投影;空 mapping = 全量。"""
    await _seed_platform_user()
    u = await register_and_login(client, "p5_alice", "pw123456")
    draft = make_draft("sc-p5", steps=[{
        "kind": "step",
        "call": {"protocol": "http", "service": "svc",
                 "method": "GET", "path": "/x", "headers": {}},
        "request": {"kind": "request", "body": {}}, "strategy": []}])
    await client.post("/api/scenarios", headers=u, json=draft)
    r = await client.post("/api/integration/tasks", headers=u,
                          json=_task_body("sc-p5"))
    tid = r.json()["id"]

    from app.core import db as db_module
    from sqlalchemy import select as _sel
    from app.models.integration_task import IntegrationTask
    async with db_module.SessionLocal() as s:
        inst = (await s.execute(_sel(IntegrationTask).where(
            IntegrationTask.template_id == tid))).scalars().one()
        inst.last_outputs = {"mr_count": 7, "build": "ok", "secret": "***"}
        tpl = await s.get(IntegrationTask, tid)
        tpl.output_mapping = {"mr_count": "待评审数"}
        await s.commit()

    r = await client.post("/api/integration/cards", headers=u,
                          json={"ids": [f"fn:{tid}"]})
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert item["outputs"] == {"待评审数": 7}   # mapping 投影

    async with db_module.SessionLocal() as s:
        tpl = await s.get(IntegrationTask, tid)
        tpl.output_mapping = {}
        await s.commit()
    r = await client.post("/api/integration/cards", headers=u,
                          json={"ids": [f"fn:{tid}"]})
    assert r.json()["items"][0]["outputs"] == {
        "mr_count": 7, "build": "ok", "secret": "***"}   # 空 = 全量
