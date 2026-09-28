"""P2-01/P2-02:单元级台账列 + 统一事件表(execution_events)。

覆盖:事件入库(标签列/证据体拆分/冲突跳过)、日志入库(负 seq 占位)、
组合筛选与 after_seq 续传、category 聚合、保留期清扫、ExecutionRow
新增单元列的存在性与缺省。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect, select

from app.core import db as db_module
from app.models.execution import (
    Execution, ExecutionEvent, ExecutionEventEvidence, ExecutionRow,
)
from app.services import execution_store


def _event(seq: int, **labels) -> dict:
    d = {
        "event_type": "step.end", "seq": seq,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "step_id": f"step-{seq:03d}", "status": "passed", "duration_ms": 3.0,
    }
    d.update(labels)
    return d


async def _mk_execution(db) -> int:
    ex = Execution(scenario_id="sc-ev", owner_name="t")
    db.add(ex)
    await db.commit()
    return ex.id


@pytest.fixture
async def db(fresh_db):
    async with db_module.SessionLocal() as session:
        yield session


class TestInsertAndQuery:

    async def test_events_inserted_with_labels(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [
            _event(1, unit="u-1", attempt="1.1", step="step-000",
                   module="fin", service="fin-svc", protocol="http"),
            _event(2, unit="u-1", attempt="1.1", step="step-001"),
        ])
        await db.commit()
        rows = await execution_store.query_events(db, eid)
        assert [r.seq for r in rows] == [1, 2]
        assert rows[0].kind == "event" and rows[0].event_type == "step.end"
        assert rows[0].unit == "u-1" and rows[0].module == "fin"
        assert rows[0].payload["step_id"] == "step-001"  # 夹具按 seq 生成

    async def test_call_exchange_evidence_split(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [{
            "event_type": "call.exchange", "seq": 3,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step_id": "step-000", "protocol": "http", "status": "passed",
            "duration_ms": 12.5,
            "result": {"protocol": "http",
                       "request": {"method": "POST", "url": "/api/x"},
                       "response": {"status": 200}},
        }])
        await db.commit()
        ev = (await db.execute(
            select(ExecutionEvent).where(ExecutionEvent.seq == 3))
        ).scalar_one()
        # 主表只留摘要,证据体不占 payload
        assert "POST" in ev.message and "/api/x" in ev.message
        assert "result" not in ev.payload
        evi = (await db.execute(
            select(ExecutionEventEvidence).where(
                ExecutionEventEvidence.seq == 3))).scalar_one()
        assert evi.evidence["response"]["status"] == 200

    async def test_conflict_seq_skipped(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [_event(1)])
        await db.commit()
        await execution_store.insert_events(db, eid, [_event(1)])  # 重放窗口
        await db.commit()
        rows = await execution_store.query_events(db, eid)
        assert len(rows) == 1

    async def test_logs_negative_seq_placeholder(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_logs(db, eid, [
            {"timestamp": datetime.now(timezone.utc).isoformat(),
             "level": "WARNING", "category": "scheduler",
             "message": "slow unit", "unit": "u-2"},
            {"timestamp": datetime.now(timezone.utc).isoformat(),
             "level": "INFO", "category": "core", "message": "done"},
        ], seq_base=0)
        await db.commit()
        rows = await execution_store.query_events(db, eid, kind="log")
        assert [r.seq for r in rows] == [-2, -1]
        assert rows[0].level == "WARNING" and rows[0].category == "scheduler"

    async def test_filters_and_after_seq(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [
            _event(1, category=None, module="fin", status="failed"),
            _event(2, module="logi", status="passed"),
            _event(3, module="fin", status="passed"),
        ])
        await db.commit()
        # 组合筛选:module + event_type;after_seq 续传
        rows = await execution_store.query_events(db, eid, module="fin")
        assert [r.seq for r in rows] == [1, 3]
        rows = await execution_store.query_events(db, eid, after_seq=1)
        assert [r.seq for r in rows] == [2, 3]
        # message 全文搜索(事件侧 message 为空 → 无命中;logs 侧有)
        assert await execution_store.query_events(db, eid, search="zzz") == []

    async def test_category_counts(self, db):
        eid = await _mk_execution(db)
        await execution_store.insert_events(db, eid, [_event(1), _event(2)])
        await execution_store.insert_logs(db, eid, [
            {"level": "WARNING", "category": "scheduler", "message": "m"},
            {"level": "INFO", "category": "scheduler", "message": "m2"},
        ], seq_base=0)
        await db.commit()
        counts = await execution_store.event_counts_by_category(db, eid)
        assert counts == {"(none)": 2, "scheduler": 2}


class TestRetention:

    async def test_purge_expired_events(self, db, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "EXEC_EVENTS_RETENTION_DAYS", 14)

        old = Execution(scenario_id="sc-old", owner_name="t",
                        finished_at=datetime.now(timezone.utc) - timedelta(days=30))
        fresh = Execution(scenario_id="sc-new", owner_name="t",
                          finished_at=datetime.now(timezone.utc))
        db.add_all([old, fresh])
        await db.commit()
        await execution_store.insert_events(db, old.id, [_event(1)])
        await execution_store.insert_events(db, fresh.id, [_event(1)])
        await db.commit()

        removed = await execution_store.purge_expired_events(db)
        await db.commit()
        assert removed >= 1
        assert await execution_store.query_events(db, old.id) == []
        assert len(await execution_store.query_events(db, fresh.id)) == 1
        # 台账主行不受影响(审计面)
        assert (await db.execute(select(Execution))).scalars().all().__len__() == 2

    async def test_purge_disabled_when_zero(self, db, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "EXEC_EVENTS_RETENTION_DAYS", 0)
        assert await execution_store.purge_expired_events(db) == 0


class TestUnitLedgerColumns:

    async def test_execution_row_has_unit_columns(self, db):
        eid = await _mk_execution(db)
        db.add(ExecutionRow(execution_id=eid, seq=1, status="passed",
                            unit_id="order#1", branch="main", attempts=3,
                            row_index=0, rep=0, case_dir=""))
        await db.commit()
        row = (await db.execute(select(ExecutionRow))).scalar_one()
        assert row.unit_id == "order#1"
        assert row.branch == "main" and row.attempts == 3

    def test_migration_columns_exist(self):
        """0008 迁移/模型双方的列面(fresh_db 的 create_all 即建表面来源)。"""
        from app.core.db import Base
        t = Base.metadata.tables["execution_rows"]
        assert {"unit_id", "branch", "attempts"} <= set(t.columns.keys())
        ev = Base.metadata.tables["execution_events"]
        assert {"execution_id", "seq", "kind", "category", "unit", "attempt",
                "step", "event_type", "message", "payload"} <= set(ev.columns.keys())
        evi = Base.metadata.tables["execution_event_evidence"]
        assert {"execution_id", "seq", "evidence"} <= set(evi.columns.keys())
