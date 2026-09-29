"""services/execution_queue.py — C11（P3-01）：执行任务持久化队列。

POST /api/runs 只入队；本模块的 worker 循环认领并驱动执行
（run_dispatcher 的 _fanout/_fanout_graph 是任务体）。

多 worker 正确性：PG 上 ``FOR UPDATE SKIP LOCKED`` 认领——两个 worker
同抢一行时只有一个 UPDATE 成功；SQLite（测试链）无 SKIP LOCKED，退化为
普通子查询（单连接测试无并发抢占面）。

重启恢复：``queued`` 任务原样等待认领；``running`` 且租约过期的孤儿由
sweep_stale 回收（attempts 未超上限 → 回队重跑；超上限 → 失败收口，
执行链不可假设幂等——重复下单面）。优雅关闭时 worker 释放当前任务
（回队、attempts 不变）。

取消：``cancel_requested`` DB 位（进程内 _cancel_requested 集合退役）；
worker 在行边界/任务起点查询并收敛为 canceled 终态。
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text, update

from ..core.config import settings
from ..models.execution import ExecutionJob

logger = logging.getLogger(__name__)

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"

# 运行中租约（秒）：heartbeat 周期 = 租约/3；超过租约未续 = 孤儿
LEASE_SEC = float(getattr(settings, "EXEC_JOB_LEASE_SEC", 120.0))
# 认领次数上限（含首次）：孤儿回收超过即失败收口
MAX_ATTEMPTS = int(getattr(settings, "EXEC_JOB_MAX_ATTEMPTS", 2))

_workers: set[asyncio.Task] = set()
_stopping = False
# 本进程正在执行的任务 id 集（优雅关闭/测试 teardown 的「在途」观测面）
_busy: set[int] = set()
# 取消快速通道（advisory cache）：权威在 DB 位;同进程写入即时可见
# （路由与 worker 同进程的开发/测试拓扑下消除 0.5s 轮询延迟——
# 快执行会在轮询节拍前自然跑完）。fanout teardown 出清。
_cancel_hint: set[int] = set()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── 入队 / 认领 / 终态 ────────────────────────────────────────

async def enqueue(db, execution_id: int, *, kind: str, payload: dict) -> None:
    """入队并提交（请求级 get_db 不代提交——与 _create_execution 同款
    服务内自决 commit；失败整个请求 500，不留「有执行无任务」的半态）。"""
    db.add(ExecutionJob(execution_id=execution_id, kind=kind,
                        status="queued", payload=payload))
    await db.commit()


async def claim_next(db) -> Optional[dict]:
    """认领下一个 queued 任务（attempts+1、租约起点）；无任务返回 None。

    PG 用 FOR UPDATE SKIP LOCKED（并发安全）；SQLite 无该语法。
    返回 job 的 dict 快照（id/execution_id/kind/payload/attempts）。
    """
    bind = db.get_bind()
    dialect = bind.dialect.name
    skip = "FOR UPDATE SKIP LOCKED" if dialect == "postgresql" else ""
    stmt = text(f"""
        UPDATE execution_jobs
           SET status = 'running',
               claimed_by = :worker,
               claimed_at = :now,
               heartbeat_at = :now,
               attempts = attempts + 1
         WHERE id = (
               SELECT id FROM execution_jobs
                WHERE status = 'queued'
                ORDER BY id
                LIMIT 1
               {skip}
         )
        RETURNING id, execution_id, kind, payload, attempts
    """)
    row = (await db.execute(stmt, {"worker": WORKER_ID, "now": _utcnow()})).first()
    if row is None:
        return None
    payload = row[3]
    if isinstance(payload, str):   # SQLite:原生 RETURNING 绕过 JSON 类型解析
        import json as _json
        payload = _json.loads(payload)
    return {"id": row[0], "execution_id": row[1], "kind": row[2],
            "payload": payload or {}, "attempts": row[4]}


async def heartbeat(db, job_id: int) -> None:
    await db.execute(
        update(ExecutionJob)
        .where(ExecutionJob.id == job_id)
        .values(heartbeat_at=_utcnow(), claimed_by=WORKER_ID))


async def finish(db, job_id: int, status: str,
                 last_error: str | None = None) -> None:
    await db.execute(
        update(ExecutionJob)
        .where(ExecutionJob.id == job_id)
        .values(status=status, heartbeat_at=_utcnow(),
                last_error=last_error))


async def release(db, job_id: int, *, reason: str = "") -> None:
    """释放回队（优雅关闭/取消未启动）：attempts 不变，清租约。"""
    await db.execute(
        update(ExecutionJob)
        .where(ExecutionJob.id == job_id)
        .values(status="queued", claimed_by=None, claimed_at=None,
                heartbeat_at=None,
                last_error=reason or None))


# ─── 取消（DB 位）─────────────────────────────────────────────

async def request_cancel(db, execution_id: int) -> bool:
    """标记取消请求（DB 权威位 + 本进程 advisory 快速通道）。

    返回是否存在可取消的任务（queued/running）。
    """
    res = await db.execute(
        update(ExecutionJob)
        .where(ExecutionJob.execution_id == execution_id,
               ExecutionJob.status.in_(("queued", "running")))
        .values(cancel_requested=True))
    _cancel_hint.add(execution_id)
    return bool(res.rowcount)


async def is_cancel_requested(db, execution_id: int) -> bool:
    if execution_id in _cancel_hint:
        return True   # 本进程快速通道(权威位的镜像;fanout teardown 出清)
    row = await db.execute(
        text("SELECT cancel_requested FROM execution_jobs "
             "WHERE execution_id = :eid"),
        {"eid": execution_id})
    return bool(row.scalar())


# ─── 孤儿回收 / 启动恢复 ──────────────────────────────────────

async def sweep_stale(db) -> int:
    """租约过期的 running 孤儿：attempts<上限 → 回队；否则失败收口。

    返回处理行数。失败收口的执行由调用方（startup_recovery）统一标
    reconciled。
    """
    cutoff = _utcnow() - timedelta(seconds=LEASE_SEC)
    stale = (await db.execute(
        text("SELECT id, execution_id, attempts FROM execution_jobs "
             "WHERE status = 'running' "
             "AND (heartbeat_at IS NULL OR heartbeat_at < :cutoff)"),
        {"cutoff": cutoff})).all()
    requeued: list[int] = []
    failed: list[int] = []
    for jid, eid, attempts in stale:
        (requeued if attempts < MAX_ATTEMPTS else failed).append((jid, eid))
    if requeued:
        await db.execute(
            text("UPDATE execution_jobs SET status='queued', claimed_by=NULL, "
                 "claimed_at=NULL, heartbeat_at=NULL, "
                 "last_error='lease expired; requeued' "
                 f"WHERE id IN ({','.join(str(j) for j, _ in requeued)})"))
    for jid, eid in failed:
        await db.execute(
            update(ExecutionJob).where(ExecutionJob.id == jid)
            .values(status="failed", last_error="lease expired; attempts exhausted"))
    return len(stale)


# ─── worker 循环 ─────────────────────────────────────────────

async def _execute_job(job: dict) -> None:
    """任务体分派（延迟导入避免与 run_dispatcher 循环依赖）。"""
    from . import run_dispatcher
    from ..core import db as db_module

    async with db_module.SessionLocal() as session:
        await heartbeat(session, job["id"])
        await session.commit()
    _busy.add(job["id"])
    try:
        await run_dispatcher.run_job_from_payload(job)
        async with db_module.SessionLocal() as session:
            await finish(session, job["id"], "done")
            await session.commit()
    except asyncio.CancelledError:
        # 优雅关闭：当前任务回队（行边界已执行的行保持终态,
        # 重跑从头再来——与"重启后排队任务继续执行"同一口径）
        async with db_module.SessionLocal() as session:
            await release(session, job["id"], reason="worker shutdown")
            await session.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("execution_queue: job %s failed: %s", job["id"], exc)
        async with db_module.SessionLocal() as session:
            await finish(session, job["id"], "failed", last_error=str(exc)[:2000])
            await session.commit()
        # 任务体异常时执行行由任务体自身收口；此处兜底标 failed
        # （幂等：_finalize_execution 已终态的不会再改）
        from . import run_dispatcher as rd
        await rd.finalize_execution_if_stuck(job["execution_id"], str(exc))
    finally:
        _busy.discard(job["id"])


async def _worker_loop(idx: int) -> None:
    from ..core import db as db_module
    logger.info("execution_queue: worker %s#%d started", WORKER_ID, idx)
    try:
        while not _stopping:
            job = None
            try:
                async with db_module.SessionLocal() as session:
                    job = await claim_next(session)
                    await session.commit()
            except Exception:  # noqa: BLE001
                logger.exception("execution_queue: claim failed (worker %d)", idx)
                job = None
            if job is None:
                await asyncio.sleep(0.5)
                continue
            # 取消先于启动：直接 canceled 收口（执行行终态化由任务体做）
            try:
                async with db_module.SessionLocal() as session:
                    cancelled = await is_cancel_requested(
                        session, job["execution_id"])
                if cancelled:
                    from . import run_dispatcher as rd
                    await rd.finalize_canceled_before_start(job)
                    async with db_module.SessionLocal() as session:
                        await finish(session, job["id"], "canceled")
                        await session.commit()
                    continue
            except Exception:  # noqa: BLE001
                logger.exception("execution_queue: pre-start cancel check failed")
            await _execute_job(job)
    except asyncio.CancelledError:
        logger.info("execution_queue: worker %d cancelled", idx)
        raise


def start_workers(count: int | None = None) -> None:
    """启动 worker 循环（幂等；lifespan 与 dispatch 惰性ensure 双入口）。

    跨事件循环清理:测试每用例新 loop,旧 loop 的任务在本 loop 复位
    （已 done 或 loop 已关的先出清,不跨 loop 复用 asyncio 任务）。
    """
    global _stopping
    _stopping = False
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    for t in list(_workers):
        if t.done() or t.get_loop() is not loop:
            _workers.discard(t)
    n = count if count is not None else int(
        getattr(settings, "EXEC_WORKERS", 1))
    for i in range(n):
        if any(t.get_name() == f"exec-worker-{i}" and not t.done()
               for t in _workers):
            continue
        t = asyncio.create_task(_worker_loop(i), name=f"exec-worker-{i}")
        _workers.add(t)
        t.add_done_callback(_workers.discard)


def ensure_workers() -> None:
    """dispatch 侧惰性入口：lifespan 未跑（如测试 ASGITransport 直连）
    时也能驱动队列。幂等。"""
    if _workers and not _stopping:
        # 同 loop 已有活 worker 即够
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if any(not t.done() and t.get_loop() is loop for t in _workers):
            return
    start_workers()


async def stop_workers(timeout_s: float = 15.0) -> int:
    """优雅停止：通知停止 → 等在飞任务收口（当前任务回队）→ 返回数。"""
    global _stopping
    _stopping = True
    tasks = list(_workers)
    if not tasks:
        return 0
    done, pending = await asyncio.wait(tasks, timeout=timeout_s)
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    return len(done) + len(pending)


def reset_worker_state() -> None:
    """测试复位。"""
    global _stopping
    _stopping = False
    for t in list(_workers):
        t.cancel()
    _workers.clear()
    _busy.clear()
    _cancel_hint.clear()
