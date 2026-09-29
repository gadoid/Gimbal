"""C11(P3-01):执行队列语义 — 认领/租约/取消位/孤儿回收/重启恢复。

进程内注册表退役后的权威行为面；多 worker 不重复执行由
SKIP LOCKED(PG)保证,SQLite 测试链验证状态机本身。
"""
from __future__ import annotations

from datetime import timedelta

from app.core import db as db_module
from app.models.execution import Execution, ExecutionJob
from app.services import execution_queue as eq


async def _seed_exec(owner_id: int, status: str = "queued") -> int:
    from datetime import datetime, timezone

    async with db_module.SessionLocal() as s:
        ex = Execution(scenario_id="sc-q", owner_id=owner_id, status=status,
                       total_runs=1, config_json={})
        s.add(ex)
        await s.commit()
        return ex.id


async def _seed_job(execution_id: int, *, status: str = "queued",
                    attempts: int = 0, cancel: bool = False,
                    heartbeat=None, payload: dict | None = None) -> int:
    async with db_module.SessionLocal() as s:
        job = ExecutionJob(execution_id=execution_id, status=status,
                           kind="cases", attempts=attempts,
                           cancel_requested=cancel,
                           payload=payload or {"kind": "cases", "args": {}})
        s.add(job)
        await s.commit()
        return job.id


async def test_enqueue_claim_lifecycle(client):
    async with db_module.SessionLocal() as s:
        await eq.enqueue(s, 1, kind="cases",
                         payload={"kind": "cases", "args": {"n_runs": 3}})
        await s.commit()

        job = await eq.claim_next(s)
        assert job is not None
        assert job["execution_id"] == 1
        assert job["payload"]["args"]["n_runs"] == 3   # JSON 往返安全
        await s.commit()

        # 认领即 running + attempts+1;再认领无货(唯一 queued 已被占)
        assert await eq.claim_next(s) is None

        await eq.finish(s, job["id"], "done")
        await s.commit()
        assert await eq.claim_next(s) is None


async def test_claim_does_not_touch_running_or_done(client):
    """仅 queued 可认领(running/done/canceled 均不出货)。"""
    e1 = await _seed_exec(1, status="running")
    await _seed_job(e1, status="running", attempts=1)
    e2 = await _seed_exec(1, status="done")
    await _seed_job(e2, status="done", attempts=1)
    async with db_module.SessionLocal() as s:
        assert await eq.claim_next(s) is None


async def test_cancel_bit_and_hint(client):
    eid = await _seed_exec(1, status="running")
    await _seed_job(eid, status="running", attempts=1)
    async with db_module.SessionLocal() as s:
        assert await eq.request_cancel(s, eid) is True
        await s.commit()
        assert await eq.is_cancel_requested(s, eid) is True
        eq._cancel_hint.discard(eid)          # 退 hint 后 DB 位仍权威
        assert await eq.is_cancel_requested(s, eid) is True

        # 终态 job 不可取消
        job_id = (await s.execute(
            __import__("sqlalchemy").select(ExecutionJob.id)
            .where(ExecutionJob.execution_id == eid))).scalar_one()
        await eq.finish(s, job_id, "done")
        await s.commit()
        eq._cancel_hint.discard(eid)
        assert await eq.request_cancel(s, eid) is False


async def test_sweep_stale_requeues_under_attempts_cap(client):
    """租约过期的 running 孤儿:attempts 未超上限 → 回队重跑。"""
    eid = await _seed_exec(1, status="running")
    jid = await _seed_job(eid, status="running", attempts=1,
                          heartbeat=None)      # 无心跳 = 孤儿
    async with db_module.SessionLocal() as s:
        n = await eq.sweep_stale(s)
        await s.commit()
        assert n == 1
        job = await s.get(ExecutionJob, jid)
        assert job.status == "queued" and job.claimed_by is None


async def test_sweep_stale_fails_at_attempts_cap(client):
    eid = await _seed_exec(1, status="running")
    jid = await _seed_job(eid, status="running",
                          attempts=eq.MAX_ATTEMPTS)
    async with db_module.SessionLocal() as s:
        assert await eq.sweep_stale(s) == 1
        await s.commit()
        job = await s.get(ExecutionJob, jid)
        assert job.status == "failed"


async def test_startup_recovery_keeps_queued_and_fails_jobless(client, monkeypatch):
    """重启恢复:queued 任务继续执行(job 留存);无 job 的僵尸执行收口 failed。"""
    from app.services import run_dispatcher as rd

    e_live = await _seed_exec(1, status="queued")
    await _seed_job(e_live, status="queued")
    e_zombie = await _seed_exec(1, status="running")   # 无 job(0009 前遗留)

    stale, _ = await rd.startup_recovery()
    assert stale >= 1
    async with db_module.SessionLocal() as s:
        live = await s.get(Execution, e_live)
        zombie = await s.get(Execution, e_zombie)
        assert live.status == "queued"          # 排队任务不受影响
        assert zombie.status == "failed"
        cfg = zombie.config_json or {}
        assert cfg.get("reconciled", {}).get("reason") == \
            "backend restarted mid-dispatch"
