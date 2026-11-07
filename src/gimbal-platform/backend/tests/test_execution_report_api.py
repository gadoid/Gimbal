"""B4/B5(2026-11-06 日志报告整理):执行报告与批次汇总 API。

* GET /executions/{id}/report:概览 / 分组步骤表 / 失败聚焦,数据只来自
  步骤表与行台账——事件清扫后报告不变;可见性同执行详情;只认 JWT。
* GET /executions/batch-summary?batchId=:成员清单 + 计数,不可见成员剔除。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from app.core import db as db_module
from app.models.execution import Execution, ExecutionEvent, ExecutionRow
from app.models.user import User
from app.services import execution_store
from tests.helpers import register_and_login


def _step_end(seq, *, row_seq=0, step_id="step-000", status="passed",
              unit="sc-r", attempt="1.1", **extra):
    d = {
        "event_type": "step.end", "seq": seq,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "step_id": step_id, "unit": unit, "attempt": attempt,
        "scenario_id": unit, "status": status, "duration_ms": 10.0,
        "step_name": step_id, "description": f"desc {step_id}",
        "call_summary": f"GET http://h/{step_id}",
        "assertion_count": 1, "assertion_passed": 1 if status == "passed" else 0,
        "assertions": [{"name": "$.x", "target": "$.x", "operator": "eq",
                        "expected": "8", "actual": "8" if status == "passed" else "7",
                        "passed": status == "passed",
                        "message": "ok" if status == "passed"
                        else "FAIL: actual '7', expected eq '8'"}],
        "extracts": [{"target": "oid", "value": "7"}],
        "row_seq": row_seq,
    }
    d.update(extra)
    return d


async def _me(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.select(User.id).where(
            User.username == username))).scalar_one()


async def _seed(owner_id: int, *, status="failed", batch_id=None) -> int:
    async with db_module.SessionLocal() as s:
        ex = Execution(scenario_id="sc-r", scenario_name="报告场景",
                       owner_id=owner_id, owner_name="t", status=status,
                       total_runs=2, passed=1, failed=1, batch_id=batch_id,
                       started_at=datetime.now(timezone.utc) - timedelta(seconds=3),
                       finished_at=datetime.now(timezone.utc))
        s.add(ex)
        await s.commit()
        eid = ex.id
        s.add_all([
            ExecutionRow(execution_id=eid, seq=0, status="passed",
                         case_dir="case-000-baseline-r0", unit_id="sc-r"),
            ExecutionRow(execution_id=eid, seq=1, status="failed",
                         case_dir="case-001-baseline-r1", unit_id="sc-r",
                         server_slot=1),
        ])
        await s.commit()
        fe = {"request": {"method": "GET", "url": "http://h/step-001",
                          "headers": {"Authorization": "***redacted***"}},
              "response": {"status": 200, "body": {"id": "7"}}}
        await execution_store.insert_events(s, eid, [
            _step_end(1, row_seq=0),
            _step_end(2, row_seq=0, step_id="step-001"),
            _step_end(3, row_seq=1),
            _step_end(4, row_seq=1, step_id="step-001", status="failed",
                      failure_evidence=fe,
                      error_brief="[verifying] FAIL: actual '7', expected eq '8'"),
        ])
        await s.commit()
        return eid


class TestReport:

    async def test_report_shape_and_failure_focus(self, client):
        headers = await register_and_login(client)
        eid = await _seed(await _me("alice"))
        r = await client.get(f"/api/executions/{eid}/report", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["hasStepData"] is True
        assert body["execution"]["scenarioName"] == "报告场景"
        assert body["execution"]["durationMs"] >= 2000
        assert body["summary"] == {
            "steps": 4, "stepsPassed": 3, "stepsFailed": 1, "stepsOther": 0,
            "assertions": 4, "assertionsPassed": 3}
        groups = body["groups"]
        assert [g["rowSeq"] for g in groups] == [0, 1]
        assert [s["stepId"] for s in groups[1]["steps"]] == ["step-000", "step-001"]
        assert groups[1]["serverSlot"] == 1
        f = body["failure"]
        assert f["rowSeq"] == 1 and f["stepId"] == "step-001"
        assert f["description"] == "desc step-001"
        assert f["failedAssertions"][0]["actual"] == "7"
        assert f["evidence"]["request"]["headers"]["Authorization"] == "***redacted***"
        assert f["evidence"]["response"]["body"] == {"id": "7"}

    async def test_report_survives_event_purge(self, client):
        headers = await register_and_login(client)
        eid = await _seed(await _me("alice"))
        async with db_module.SessionLocal() as s:
            await s.execute(sa.delete(ExecutionEvent).where(
                ExecutionEvent.execution_id == eid))
            await s.commit()
        r = await client.get(f"/api/executions/{eid}/report", headers=headers)
        assert r.status_code == 200
        assert r.json()["failure"]["evidence"]["response"]["status"] == 200

    async def test_report_without_steps(self, client):
        headers = await register_and_login(client)
        async with db_module.SessionLocal() as s:
            ex = Execution(scenario_id="sc-old", owner_id=await _me("alice"),
                           owner_name="t", status="passed")
            s.add(ex)
            await s.commit()
            eid = ex.id
        r = await client.get(f"/api/executions/{eid}/report", headers=headers)
        assert r.status_code == 200
        b = r.json()
        assert b["hasStepData"] is False and b["failure"] is None

    async def test_report_hidden_from_other_user(self, client):
        await register_and_login(client)
        eid = await _seed(await _me("alice"))
        bob = await register_and_login(client, "bob", "bobpass12345")
        r = await client.get(f"/api/executions/{eid}/report", headers=bob)
        assert r.status_code == 404
        # authz W4:负例扩展到 admin/super_admin 主体(执行只认属主)
        from tests.helpers import role_headers

        for role in ("admin", "super_admin"):
            h = await role_headers(client, f"rp_{role}", role=role)
            r2 = await client.get(
                f"/api/executions/{eid}/report", headers=h)
            assert r2.status_code == 404, role


    async def test_report_rejects_access_token(self, client):
        """B4 按 v4 §2.2 只认 JWT:访问令牌(Authization Bearer 明文)
        打报告接口 → 401,authz W4 前后不变(钉契约)。"""
        from .inbound_fixtures import mk_token

        await register_and_login(client)
        eid = await _seed(await _me("alice"))
        uid = await _me("alice")
        _tid, plain = await mk_token(user_id=uid)
        r = await client.get(
            f"/api/executions/{eid}/report",
            headers={"Authorization": f"Bearer {plain}"})
        assert r.status_code == 401, r.text


class TestBatchSummary:

    async def test_batch_summary_counts_visible_members(self, client):
        # 首个注册用户是 admin(全局可读);先占掉,alice/bob 为普通用户
        await register_and_login(client, "root", "rootpass12345")
        headers = await register_and_login(client)
        me = await _me("alice")
        await _seed(me, status="failed", batch_id="b-1")
        await _seed(me, status="passed", batch_id="b-1")
        bob = await register_and_login(client, "bob", "bobpass12345")
        await _seed(await _me("bob"), status="passed", batch_id="b-1")

        r = await client.get("/api/executions/batch-summary",
                             params={"batchId": "b-1"}, headers=headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["total"] == 2                      # bob 的成员对 alice 不可见
        assert b["counts"] == {"failed": 1, "passed": 1}
        assert b["active"] is False and b["finishedAt"]
        assert {m["status"] for m in b["members"]} == {"failed", "passed"}

        r2 = await client.get("/api/executions/batch-summary",
                              params={"batchId": "b-1"}, headers=bob)
        assert r2.json()["total"] == 1
        root = await register_and_login(client, "root", "rootpass12345")
        r3 = await client.get("/api/executions/batch-summary",
                              params={"batchId": "b-1"}, headers=root)
        # authz W4:root(首注 super_admin)对他人批次不再可读 —— 自己
        # 的成员为 0 → 404(全局可读旁路已删,admin 排查走审计)
        assert r3.status_code == 404

    async def test_batch_summary_unknown_404(self, client):
        headers = await register_and_login(client)
        r = await client.get("/api/executions/batch-summary",
                             params={"batchId": "nope"}, headers=headers)
        assert r.status_code == 404
