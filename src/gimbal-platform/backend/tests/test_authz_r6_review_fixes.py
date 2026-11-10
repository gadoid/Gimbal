"""评审第六轮必修项回归(2026-11-11,r6 review)。

* 二.2 按值掩码端到端守卫:**真实引擎子进程**(`gimbal run launch -o
  jsonl`,不 mock)跑一个把凭证模板放进普通键名字段 / 查询参数的步骤
  —— 落库的 execution_events(含 step.start.strategy_spec / call.
  exchange / step.end 与 kind=log 日志)与 execution_steps.
  call_summary 一律搜不到明文;掩码确实启用(***redacted*** 在场,
  防空转通过)。出口统一收口 = 引擎 EventBus.publish 逐字段 egress_
  mask + loguru patcher,新增事件字段不再漏。
* 小项:项目凭证密码 ≥6 位(短于 6 不受按值掩码保护)→ 422。
* (二.1 数据集行键并回的删/插/重排用例在 test_authz_r5_review_fixes
  的 TestDataSetMemberListingAndSensitiveKeep 内。)
"""
from __future__ import annotations

import asyncio
import json

import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models.auth_session import AuthSession

from .helpers import make_draft, register_and_login
from .test_authz_s8_project_credentials import _mk_project, _uid
from .test_scenario_composer_plate_integration import (  # noqa: F401
    PlateMock,
    plate_mock,
)


class TestProjectCredentialPasswordFloor:
    async def test_create_and_patch_min_length(self, client):
        h_a = await register_and_login(client, "r6_ca", "pw123456")
        pid = await _mk_project("r6-cred", members={"r6_ca": "admin"})
        base = f"/api/projects/{pid}/credentials"
        body = {"alias": "qa1", "url": "http://a", "username": "u1",
                "system": "fin"}
        r = await client.post(base, headers=h_a,
                              json={**body, "password": "p1234"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "password_too_short_for_masking"
        r = await client.post(base, headers=h_a,
                              json={**body, "password": "p123456"})
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        assert (await client.patch(f"{base}/{cid}", headers=h_a,
                                   json={"password": "p1234"}
                                   )).status_code == 422


class TestValueMaskingEndToEnd:
    """真实引擎执行 → 平台三张落库面(事件/步骤/日志)搜不到明文。"""

    async def test_events_steps_logs_have_no_plaintext(self, client,
                                                       plate_mock):
        plate_mock.behaviour = "echo"
        secret = "ProjPw-Zx81Qv77"
        h = await register_and_login(client, "r6_mk", "pw123456")
        uid = await _uid("r6_mk")
        # 个人槽位绑定:静态令牌(url 空 → password 兼作 token,免登录流)
        async with db_module.SessionLocal() as db:
            db.add(AuthSession(owner_id=uid, alias="qa1", slot="qa1",
                               url="", system="fin-svc",
                               username_enc=fernet_encrypt("u1"),
                               password_enc=fernet_encrypt(secret),
                               is_default=True))
            await db.commit()
        draft = make_draft("sc-r6-mask")
        # 死端口(127.0.0.1:9)直连地址:连接即刻拒绝 → 步骤失败,但
        # step.start / call.exchange / step.end / 日志全链照发
        draft["definition"]["config"]["services"] = {
            "fin-svc": "http://127.0.0.1:9/x"}
        draft["definition"]["steps"] = [{
            "kind": "step", "description": "掩码探针",
            "call": {"protocol": "http", "service": "fin-svc",
                     "method": "POST", "path": "/q?memo=${auth.qa1.password}",
                     "headers": {}},
            "request": {"kind": "request", "body": {
                "password": "${auth.qa1.password}",   # 键名敏感
                "note": "${auth.qa1.password}"}},      # 键名普通(绕过面)
            "strategy": []}]
        r = await client.post("/api/scenarios", headers=h, json=draft)
        assert r.status_code in (200, 201), r.text
        r = await client.post("/api/runs", headers=h,
                              json={"scenarioId": "sc-r6-mask"})
        assert r.status_code == 201, r.text
        eid = r.json()["executionId"]

        from app.models.execution import Execution

        async def _terminal() -> bool:
            async with db_module.SessionLocal() as db:
                ex = await db.get(Execution, eid)
                return (ex is not None
                        and ex.status in ("done", "failed", "canceled"))

        for _ in range(1200):     # 真实子进程:给足 60s
            if await _terminal():
                break
            await asyncio.sleep(0.05)
        else:
            raise AssertionError("执行未在 60s 内终态(真实引擎子进程)")

        from app.models.execution import ExecutionEvent, ExecutionStep

        async with db_module.SessionLocal() as db:
            events = (await db.execute(sa.select(
                ExecutionEvent.kind, ExecutionEvent.payload).where(
                ExecutionEvent.execution_id == eid))).all()
            steps = (await db.execute(sa.select(
                ExecutionStep.call_summary).where(
                ExecutionStep.execution_id == eid))).scalars().all()

        assert events, "事件未落库(执行链异常)"
        blob = "\n".join(f"{k}:{json.dumps(p, ensure_ascii=False)}"
                         for k, p in events)
        # ① 三张面都搜不到明文
        assert secret not in blob, [p for k, p in events if secret in
                                    json.dumps(p)]
        assert all(secret not in (s or "") for s in steps)
        # ② 掩码确实启用(防「没带秘密跑了个空」的空转通过):
        #    step.start.strategy_spec 的 password 键被键名脱敏
        assert "***redacted***" in blob
        # ③ 日志面在场且同样干净(CallExecutor URL / 提取 / 断言日志)
        assert any(k == "log" for k, _ in events)
        log_blob = "\n".join(json.dumps(p, ensure_ascii=False)
                             for k, p in events if k == "log")
        assert secret not in log_blob
