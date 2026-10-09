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
    def test_read_only_check(self):
        from app.services.integration_runner import is_scenario_read_only
        payload_get = {"definition": {"steps": STEPS_GET}}
        ok, offenders = is_scenario_read_only(payload_get)
        assert ok and not offenders
        payload_post = {"definition": {"steps": STEPS_GET + STEPS_POST}}
        ok, offenders = is_scenario_read_only(payload_post)
        assert not ok and any("POST" in o for o in offenders)

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
        # 个人模式 → P1 未开放
        r = await client.post("/api/integration/tasks", headers=h,
                              json=_task_body("sc-ig-get", identityMode="personal"))
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
            launch_status = "ok"
            run_result = {"status": "passed", "token": "should-be-scrubbed"}

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
        assert out["instance"]["lastStatus"] == "passed"
        # E1:outputs 内敏感键被脱敏
        async with db_module.SessionLocal() as db:
            inst = (await db.execute(select(IntegrationTask).where(
                IntegrationTask.template_id == tid))).scalar()
            assert inst.last_outputs["token"] == "***"
        # 冷却:60s 内再点 → 409
        r = await client.post(f"/api/integration/tasks/{tid}/run", headers=h)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "cooldown"
