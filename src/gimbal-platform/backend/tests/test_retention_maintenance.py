"""保留期维护(整体评审 2026-10-15 #2/#3)。

- 事件面分批清扫:多批次能清完、只清超期执行、证据体随之删除;
- case 案卷 / 按日 JSONL 清扫:按保留期判龄,未超期的保留;
- 维护任务已注册进后台任务表(此前事件清扫全仓零调用点)。
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models import Execution
from app.models.execution import ExecutionEvent, ExecutionEventEvidence
from app.services import execution_store, run_dispatcher


def _event(seq: int) -> dict:
    return {"event_type": "step.end", "seq": seq,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step_id": f"step-{seq:03d}", "status": "passed",
            "duration_ms": 3.0}


@pytest.fixture
async def db(fresh_db):
    from app.core import db as db_module
    async with db_module.SessionLocal() as s:
        yield s


async def test_purge_in_batches_until_done(db, monkeypatch):
    monkeypatch.setattr(settings, "EXEC_EVENTS_RETENTION_DAYS", 14)
    old_at = datetime.now(timezone.utc) - timedelta(days=30)
    olds = [Execution(scenario_id=f"sc-old-{i}", owner_name="t",
                      finished_at=old_at) for i in range(5)]
    fresh = Execution(scenario_id="sc-fresh", owner_name="t",
                      finished_at=datetime.now(timezone.utc))
    running = Execution(scenario_id="sc-running", owner_name="t",
                        finished_at=None)
    db.add_all([*olds, fresh, running])
    await db.commit()
    for ex in [*olds, fresh, running]:
        await execution_store.insert_events(
            db, ex.id, [_event(1), _event(2)])
    db.add(ExecutionEventEvidence(execution_id=olds[0].id, seq=1,
                                  evidence={"x": 1}))
    await db.commit()

    removed = await execution_store.purge_expired_events(
        db, batch_executions=2)          # 5 个超期执行 → 3 批
    assert removed == 10

    remaining = dict((await db.execute(
        select(ExecutionEvent.execution_id, func.count())
        .group_by(ExecutionEvent.execution_id))).all())
    assert remaining == {fresh.id: 2, running.id: 2}
    assert (await db.execute(select(func.count()).select_from(
        ExecutionEventEvidence))).scalar_one() == 0
    # 幂等:再跑一次无事可做
    assert await execution_store.purge_expired_events(db) == 0
    # 台账主行不受影响
    assert (await db.execute(select(func.count()).select_from(
        Execution))).scalar_one() == 7


def test_sweep_case_dirs_and_journals(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "CASE_RETENTION_DAYS", 14)
    monkeypatch.setattr(settings, "RUNS_JSONL_RETENTION_DAYS", 90)
    cases = tmp_path / "runs" / "cases"
    old_case, new_case = cases / "run-old", cases / "run-new"
    for d in (old_case, new_case):
        d.mkdir(parents=True)
        (d / "case.json").write_text("{}", encoding="utf-8")
    past = time.time() - 30 * 86400
    os.utime(old_case, (past, past))

    runs = tmp_path / "runs"
    old_j = runs / f"{(date.today() - timedelta(days=120)).isoformat()}.jsonl"
    new_j = runs / f"{date.today().isoformat()}.jsonl"
    other = runs / "notes.jsonl"
    for p in (old_j, new_j, other):
        p.write_text("{}\n", encoding="utf-8")
    # 追加写刷新 mtime 不影响判龄(按文件名日期)
    os.utime(old_j, None)

    assert run_dispatcher.sweep_stale_case_dirs() == 1
    assert not old_case.exists() and new_case.exists()
    assert run_dispatcher.sweep_stale_run_journals() == 1
    assert not old_j.exists() and new_j.exists() and other.exists()


def test_sweeps_disabled_when_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "RUNS_JSONL_RETENTION_DAYS", 0)
    runs = tmp_path / "runs"
    runs.mkdir()
    p = runs / "2000-01-01.jsonl"
    p.write_text("{}\n", encoding="utf-8")
    assert run_dispatcher.sweep_stale_run_journals() == 0
    assert p.exists()


async def test_maintenance_isolates_failures(fresh_db, monkeypatch):
    def boom() -> int:
        raise OSError("disk gone")

    monkeypatch.setattr(run_dispatcher, "sweep_stale_case_dirs", boom)
    monkeypatch.setattr(run_dispatcher, "sweep_stale_run_journals", lambda: 0)
    out = await run_dispatcher.run_retention_maintenance()
    assert out["case_dirs"] == -1          # 单项失败计 -1
    assert out["run_journals"] == 0
    assert out["events"] >= 0              # 其余项照跑


def test_retention_task_registered():
    """lifespan 的注册函数把保留期维护挂进后台任务表(此前零调用点)。"""
    from app.main import register_background_tasks
    from app.services import background_tasks
    register_background_tasks()
    assert {"draft-sweeper", "integration-scheduler",
            "retention-maintenance"} <= set(background_tasks.registered())
