"""S9 入库链路自监控与完整性计数(结构化日志设计 §5 S9)。

覆盖:
- 终态后 ``Execution.config_json.ingest_stats`` 含五项计数,且与
  实际入库行数/泵侧丢弃对账吻合;
- 尾部仅丢弃行的执行(不进缓冲的 below_level/unparsable)终值仍完整
  (泵侧计数脏即写 + finalize 无条件写);
- 溢出丢最旧计数;flush 失败双写(事件面 ingest.flush_failed + 后端
  日志)与重试后快照收敛;
- jsonb_set 键级原子更新:与既有写入者(counterDrift)共存不覆盖。
"""
from __future__ import annotations

import json as _json

import sqlalchemy as sa

from app.core import db as db_module
from app.models.execution import Execution, ExecutionEvent as EE


def _logline(level: str = "INFO", message: str = "hi", **extra) -> dict:
    d = {"timestamp": "2026-10-14T01:00:00+00:00", "level": level,
         "logger": "gimbal.core.x", "category": "core",
         "message": message}
    d.update(extra)
    return d


async def _seed_execution(config_json: dict | None = None) -> int:
    async with db_module.SessionLocal() as s:
        ex = Execution(scenario_id="sc-stats", owner_name="t", status="running",
                       total_runs=1, config_json=config_json or {})
        s.add(ex)
        await s.commit()
        return ex.id


async def _read_stats(eid: int) -> "tuple[dict, dict]":
    async with db_module.SessionLocal() as s:
        ex = await s.get(Execution, eid)
        n_logs = (await s.execute(
            sa.select(sa.func.count()).where(
                EE.execution_id == eid, EE.kind == "log"))).scalar()
        return dict(ex.config_json or {}), n_logs


class TestIngestStats:

    async def test_finalize_writes_five_counters_reconciled(self, fresh_db):
        from app.services.run_dispatcher import _EventIngester

        eid = await _seed_execution()
        ing = _EventIngester(db_module.SessionLocal, eid)
        ing.start()
        ing.on_log(_logline(message="l1"))
        ing.on_log(_logline(message="l2", level="WARNING"))
        # 泵侧丢弃计数(模拟 stderr 泵直接递增同一 dict)
        ing.pump_counters["logs_dropped_unparsable"] += 3
        ing.pump_counters["logs_below_level"] += 1
        await ing.finalize()

        cfg, n_logs = await _read_stats(eid)
        stats = cfg.get("ingest_stats")
        assert stats == {
            "logs_ingested": 2,
            "logs_dropped_unparsable": 3,
            "logs_below_level": 1,
            "flush_errors": 0,
            "logs_dropped_overflow": 0,
        }
        # 对账:入库行数 = ingested(无溢出/失败);丢弃在泵侧另计
        assert n_logs == 2

    async def test_tail_of_dropped_only_lines_still_writes_snapshot(self, fresh_db):
        """尾部只剩丢弃行(不进缓冲):finalize 无条件写,终值不缺。"""
        from app.services.run_dispatcher import _EventIngester

        eid = await _seed_execution()
        ing = _EventIngester(db_module.SessionLocal, eid)
        ing.start()
        ing.pump_counters["logs_below_level"] += 7
        await ing.finalize()

        cfg, n_logs = await _read_stats(eid)
        assert n_logs == 0
        assert cfg["ingest_stats"]["logs_below_level"] == 7
        assert cfg["ingest_stats"]["logs_ingested"] == 0

    async def test_overflow_drop_counter(self, fresh_db):
        from app.services.run_dispatcher import _EventIngester

        eid = await _seed_execution()
        ing = _EventIngester(db_module.SessionLocal, eid)
        ing._LOGS_BUF_CAP = 3
        ing.start()
        for i in range(5):
            ing.on_log(_logline(message=f"l{i}"))
        await ing.finalize()

        cfg, n_logs = await _read_stats(eid)
        assert ing.logs_dropped_overflow == 2
        assert cfg["ingest_stats"]["logs_dropped_overflow"] == 2
        assert n_logs == 3   # 丢最旧保最新

    async def test_jsonb_set_keeps_sibling_keys(self, fresh_db):
        """键级原子更新:counterDrift 等既有写入者不被整体覆盖。"""
        from app.services.run_dispatcher import _EventIngester

        eid = await _seed_execution(config_json={"counterDrift": True})
        ing = _EventIngester(db_module.SessionLocal, eid)
        ing.on_log(_logline(message="l1"))
        await ing.finalize()
        cfg, _ = await _read_stats(eid)
        assert cfg["counterDrift"] is True
        assert "ingest_stats" in cfg

    async def test_flush_failure_dual_write_then_recover(self, fresh_db, monkeypatch):
        """flush 失败:计数 + 事件面 ingest.flush_failed + 后端日志;
        回填重试成功后快照收敛(含 flush_errors 终值)。"""
        from loguru import logger as _lu

        from app.services import execution_store
        from app.services.run_dispatcher import _EventIngester

        eid = await _seed_execution()
        ing = _EventIngester(db_module.SessionLocal, eid)
        ing.start()
        ing.on_log(_logline(message="l1"))

        logs: list[str] = []
        sink_id = _lu.add(logs.append, level="INFO")
        orig = execution_store.insert_logs
        calls = {"n": 0}

        async def flaky(db, execution_id, rows, *, seq_base):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("db down")
            return await orig(db, execution_id, rows, seq_base=seq_base)

        monkeypatch.setattr(execution_store, "insert_logs", flaky)
        try:
            await ing._flush()   # 第一次:失败回填
        finally:
            _lu.remove(sink_id)
            monkeypatch.setattr(execution_store, "insert_logs", orig)

        assert ing.flush_errors == 1
        # 后端日志面(DB 不可用时唯一幸存面):logger.error 落一条失败记录
        assert any("event flush 1/1 failed" in ln for ln in logs)
        assert len(ing._logs) == 1 and not ing._pending   # 回填不丢
        assert ing._events and ing._events[0]["event_type"] == "ingest.flush_failed"

        await ing.finalize()   # 重试成功

        cfg, n_logs = await _read_stats(eid)
        assert cfg["ingest_stats"]["flush_errors"] == 1
        # 日志行与 flush_failed 事件都入库
        assert n_logs == 1
        async with db_module.SessionLocal() as s:
            ets = [r[0] for r in (await s.execute(
                sa.select(EE.event_type).where(
                    EE.execution_id == eid, EE.kind == "event"))).all()]
        assert "ingest.flush_failed" in ets


class TestPumpCounters:

    async def test_pump_counts_dropped_and_below(self):
        from app.services.gimbal_server_session import _pump_stderr

        class _Fake:
            def __init__(self, lines):
                self._l = [x.encode() + b"\n" for x in lines]

            async def readline(self):
                return self._l.pop(0) if self._l else b""

        counters = {"logs_dropped_unparsable": 0, "logs_below_level": 0}
        got: list[dict] = []
        await _pump_stderr(_Fake([
            _json.dumps(_logline(message="keep")),
            _json.dumps(_logline(level="DEBUG", message="below")),
            "plain non-json",
            '{"broken json',
            _json.dumps({"no_level": True}),
        ]), None, got.append, "INFO", counters)

        assert [d["message"] for d in got] == ["keep"]
        assert counters["logs_below_level"] == 1
        assert counters["logs_dropped_unparsable"] == 3
