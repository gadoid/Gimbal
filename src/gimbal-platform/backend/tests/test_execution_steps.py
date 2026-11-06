"""B3/B6(2026-11-06 日志报告整理):步骤结果落库 + server 槽位。

* step.end → execution_steps(同一事件入库事务内 upsert);
* 逐行链按 row_seq 归属,graph 链 row_seq=-1 按 unit 归属;
* attempt 进唯一键:重试的每次尝试各占一行;
* 失败证据只进步骤表,不在事件 payload 里重复;
* 执行删除 CASCADE;事件保留期清扫不动步骤表;
* execution_rows.server_slot 列存在并经行 API 透出。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.core import db as db_module
from app.models.execution import (
    Execution, ExecutionEvent, ExecutionRow, ExecutionStep,
)
from app.services import execution_store


def _step_end(seq: int, *, step_id="step-000", status="passed", unit="sc-1",
              attempt="1.1", row_seq=None, **extra) -> dict:
    d = {
        "event_type": "step.end", "seq": seq,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "step_id": step_id, "step": step_id, "unit": unit, "attempt": attempt,
        "scenario_id": unit, "status": status, "duration_ms": 12.5,
        "step_name": step_id, "description": "查订单",
        "call_summary": "GET http://h/orders/7",
        "assertion_count": 2, "assertion_passed": 1 if status != "passed" else 2,
        "assertions": [
            {"name": "$.call.response.status", "target": "$.call.response.status",
             "operator": "eq", "expected": 200, "actual": 200, "passed": True,
             "message": "PASS: 200 eq 200"},
            {"name": "$.call.response.body.id", "target": "$.call.response.body.id",
             "operator": "eq", "expected": "8", "actual": "7",
             "passed": status == "passed",
             "message": "FAIL: actual '7', expected eq '8'"},
        ],
        "extracts": [{"target": "oid", "value": "7"}],
    }
    if row_seq is not None:
        d["row_seq"] = row_seq
    d.update(extra)
    return d


async def _mk_execution(db) -> int:
    ex = Execution(scenario_id="sc-1", owner_name="t")
    db.add(ex)
    await db.commit()
    return ex.id


@pytest.fixture
async def db(fresh_db):
    async with db_module.SessionLocal() as session:
        yield session


async def _steps(db, eid):
    return (await db.execute(
        select(ExecutionStep).where(ExecutionStep.execution_id == eid)
        .order_by(ExecutionStep.row_seq, ExecutionStep.attempt,
                  ExecutionStep.event_seq))).scalars().all()


class TestStepIngest:

    async def test_step_end_becomes_step_row(self, db):
        eid = await _mk_execution(db)
        fe = {"request": {"method": "GET", "url": "http://h/orders/7",
                          "headers": {"Authorization": "***redacted***"}},
              "response": {"status": 200, "body": {"id": "7"}}}
        await execution_store.insert_events(db, eid, [
            _step_end(5, status="failed", row_seq=0, failure_evidence=fe,
                      error_brief="[verifying] FAIL: actual '7', expected eq '8'"),
        ])
        await db.commit()
        (st,) = await _steps(db, eid)
        assert st.row_seq == 0 and st.unit == "sc-1" and st.attempt == "1.1"
        assert st.step_id == "step-000" and st.event_seq == 5
        assert st.status == "failed" and st.description == "查订单"
        assert st.call_summary == "GET http://h/orders/7"
        assert st.assertion_count == 2 and st.assertion_passed == 1
        assert st.assertions[1]["actual"] == "7"
        assert st.extracts == [{"target": "oid", "value": "7"}]
        assert st.failure_evidence["response"]["body"] == {"id": "7"}
        assert st.error.startswith("[verifying] FAIL")

        # 事件表照常入库,但不重复存失败证据,也不带注入的 row_seq
        ev = (await db.execute(select(ExecutionEvent).where(
            ExecutionEvent.execution_id == eid))).scalars().one()
        assert ev.event_type == "step.end"
        assert "failure_evidence" not in ev.payload
        assert "row_seq" not in ev.payload
        assert ev.payload["assertions"][1]["expected"] == "8"

    async def test_rows_and_attempts_are_distinct_keys(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [
            # 同场景两行(数据集两行):unit 相同,靠 row_seq 区分
            _step_end(1, row_seq=0),
            _step_end(2, row_seq=1),
            # 第 0 行重试:attempt 不同,不覆盖首次失败
            _step_end(3, row_seq=0, attempt="1.2", status="passed"),
        ])
        await db.commit()
        got = [(s.row_seq, s.attempt) for s in await _steps(db, eid)]
        assert got == [(0, "1.1"), (0, "1.2"), (1, "1.1")]

    async def test_graph_chain_without_row_seq(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [
            _step_end(1, unit="u-login"),
            _step_end(2, unit="u-order"),
        ])
        await db.commit()
        steps = await _steps(db, eid)
        assert {(s.row_seq, s.unit) for s in steps} == {(-1, "u-login"), (-1, "u-order")}

    async def test_replay_same_key_updates_in_place(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [
            _step_end(1, row_seq=0, status="failed")])
        await db.commit()
        # 恢复重跑重放同一步骤(新 seq、新结果)→ 覆盖,不新增
        await execution_store.insert_events(db, eid, [
            _step_end(9, row_seq=0, status="passed")])
        await db.commit()
        (st,) = await _steps(db, eid)
        assert st.status == "passed" and st.event_seq == 9

    async def test_same_batch_duplicate_key_does_not_crash(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [
            _step_end(1, row_seq=0, status="failed"),
            _step_end(2, row_seq=0, status="passed"),
        ])
        await db.commit()
        (st,) = await _steps(db, eid)
        assert st.status == "passed"

    async def test_legacy_step_end_without_report_fields(self, db):
        """旧引擎的 step.end(无报告面字段)照样落一行,字段取缺省。"""
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [{
            "event_type": "step.end", "seq": 1, "step_id": "step-000",
            "status": "passed", "duration_ms": 1.0, "scenario_id": "sc-1",
        }])
        await db.commit()
        (st,) = await _steps(db, eid)
        assert st.assertions == [] and st.extracts == []
        assert st.failure_evidence is None and st.call_summary == ""


class TestStepLifecycle:

    async def test_cascade_on_execution_delete(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [_step_end(1, row_seq=0)])
        await db.commit()
        await db.execute(delete(Execution).where(Execution.id == eid))
        await db.commit()
        assert await _steps(db, eid) == []

    async def test_event_retention_sweep_keeps_steps(self, db, monkeypatch):
        from app.core.config import settings
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [_step_end(1, row_seq=0)])
        ex = await db.get(Execution, eid)
        ex.finished_at = datetime.now(timezone.utc) - timedelta(days=60)
        ex.status = "failed"
        await db.commit()
        monkeypatch.setattr(settings, "EXEC_EVENTS_RETENTION_DAYS", 14)
        await execution_store.purge_expired_events(db)
        evs = (await db.execute(select(ExecutionEvent).where(
            ExecutionEvent.execution_id == eid))).scalars().all()
        assert evs == []
        assert len(await _steps(db, eid)) == 1


class TestServerSlot:

    async def test_row_server_slot_column(self, db):
        eid = await _mk_execution(db)
        db.add(ExecutionRow(execution_id=eid, seq=0, status="passed",
                            case_dir="case-000-baseline-r0", server_slot=2))
        await db.commit()
        from app.services import run_dispatcher
        items, total = await run_dispatcher.execution_rows_page(
            db, eid, page=1, page_size=10)
        assert total == 1 and items[0]["serverSlot"] == 2

    async def test_pool_stamps_slot_on_result(self):
        from app.services.gimbal_launcher import LaunchResult
        from app.services.gimbal_server_session import ServerSessionPool

        class _FakeSession:
            def __init__(self, slot):
                self.slot = slot

            async def run_case(self, case_path, **kw):
                return LaunchResult(launch_status="ok", exit_code=0)

        pool = ServerSessionPool(size=1)
        pool._idle.put_nowait(_FakeSession(3))
        pool._started = 1
        res = await pool.run_case("x.json")
        assert res.server_slot == 3


class TestStepErrorFill:

    async def test_error_taken_from_step_failed_in_same_batch(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [
            {"event_type": "step.failed", "seq": 1, "step_id": "step-000",
             "unit": "sc-1", "attempt": "1.1",
             "error": "[verifying] FAIL: actual '7', expected eq '8'", "phase": "failed"},
            _step_end(2, row_seq=0, status="failed"),
        ])
        await db.commit()
        (st,) = await _steps(db, eid)
        assert st.error == "[verifying] FAIL: actual '7', expected eq '8'"
