"""N2 终态迁移归一回归(+P0:三态返回/周期对账/集成租约令牌)。

覆盖:transition_execution 原子守卫(重复迁移无效、不重复通知)、
派生状态(failed>0 → failed)、计数兜底、counterDrift、三个异常路径
补通知(stuck / 启动对账 / graph 恢复口径共用同一函数)、canceled
三类不发通知、集成 _recover_stuck 经 _finish 计 fail_streak/自动暂停;
P0(webhook 设计 v3):三态返回与 FAILED 重试一次、周期对账宽限与
reason 前缀、对账 job canceled → 执行 canceled 不通知、集成租约令牌
(回收后/重认领后的迟到结果与迟到暂停均丢弃、匹配令牌正常收口、
调度链传令牌)。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Notification
from app.models.execution import Execution
from app.models.integration_task import IntegrationTask
from app.services import integration_runner as ir
from app.services import run_dispatcher as rd
from tests.helpers import ensure_fk_users, register_and_login

UTC = timezone.utc


async def _seed_execution(*, status="running", passed=0, failed=0,
                          total=2, owner=1, kind="scenario") -> int:
    async with db_module.SessionLocal() as s:
        await ensure_fk_users(s, owner)
        s.add(Execution(
            scenario_id="sc-n2", owner_id=owner, total_runs=total,
            scenario_name="n2用例", status=status, kind=kind))
        await s.flush()
        ex_id = (await s.execute(sa.select(Execution.id).order_by(
            Execution.id.desc()))).scalars().first()
        if passed or failed:
            await s.execute(sa.text(
                "UPDATE executions SET passed=:p, failed=:f WHERE id=:i"),
                {"p": passed, "f": failed, "i": ex_id})
        await s.commit()
    return ex_id


async def _notify_count(owner: int) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(
            sa.select(sa.func.count()).select_from(Notification)
            .where(Notification.user_id == owner,
                   Notification.type == "execution_finished"))
        ).scalar() or 0


async def _get_ex(ex_id: int) -> Execution:
    async with db_module.SessionLocal() as s:
        return await s.get(Execution, ex_id)


class TestTransitionExecution:

    async def test_idempotent_no_duplicate_notify(self, client):
        await register_and_login(client, "n2_a", "pw123456")
        async with db_module.SessionLocal() as s:
            owner = (await s.execute(sa.text(
                "SELECT id FROM users WHERE username='n2_a'"))).scalar_one()
        ex_id = await _seed_execution(owner=owner)

        moved = await rd.transition_execution(
            rd.session_factory, ex_id, "failed")
        assert moved is rd.TransitionResult.MOVED
        ex = await _get_ex(ex_id)
        assert ex.status == "failed" and ex.finished_at is not None
        assert await _notify_count(owner) == 1      # 异常收口也发(N2-2)

        moved2 = await rd.transition_execution(
            rd.session_factory, ex_id, "failed")
        assert moved2 is rd.TransitionResult.ALREADY_TERMINAL   # 已终态:幂等跳过
        assert await _notify_count(owner) == 1       # 不重复通知
        assert (await _get_ex(ex_id)).status == "failed"

    async def test_derived_status_and_drift_flag(self, client):
        await register_and_login(client, "n2_b", "pw123456")
        # passed=total → 派生 done,无 drift
        ex_ok = await _seed_execution(passed=2, failed=0, total=2)
        assert await rd.transition_execution(
            rd.session_factory, ex_ok, None) is rd.TransitionResult.MOVED
        ex = await _get_ex(ex_ok)
        assert ex.status == "done"
        assert not (ex.config_json or {}).get("counterDrift")
        # failed=1 且 total=3 → 派生 failed + 计数兜底 + drift 标记
        ex_bad = await _seed_execution(passed=0, failed=1, total=3)
        assert await rd.transition_execution(
            rd.session_factory, ex_bad, None,
            count_fallback=True) is rd.TransitionResult.MOVED
        ex = await _get_ex(ex_bad)
        assert ex.status == "failed"
        assert (ex.config_json or {}).get("counterDrift") is True

    async def test_canceled_paths_do_not_notify(self, client):
        await register_and_login(client, "n2_c", "pw123456")
        async with db_module.SessionLocal() as s:
            owner = (await s.execute(sa.text(
                "SELECT id FROM users WHERE username='n2_c'"))).scalar_one()
        ex_id = await _seed_execution(status="queued", owner=owner)
        job = {"payload": {"args": {"execution_id": ex_id}}}
        await rd.finalize_canceled_before_start(job)
        ex = await _get_ex(ex_id)
        assert ex.status == "canceled"
        assert ex.started_at is None        # 取消类不回填 started_at
        assert await _notify_count(owner) == 0

    async def test_stuck_finalize_notifies_with_fallback(self, client):
        await register_and_login(client, "n2_d", "pw123456")
        async with db_module.SessionLocal() as s:
            owner = (await s.execute(sa.text(
                "SELECT id FROM users WHERE username='n2_d'"))).scalar_one()
        ex_id = await _seed_execution(owner=owner)   # passed=failed=0
        await rd.finalize_execution_if_stuck(ex_id, "boom")
        ex = await _get_ex(ex_id)
        assert ex.status == "failed"
        assert ex.failed == 2                       # count_fallback=total
        assert (ex.config_json or {}).get("dispatcherError") == "boom"
        assert await _notify_count(owner) == 1       # N2-2:兜底也发

    async def test_reconcile_migrates_notifies_and_idempotent(self, client):
        await register_and_login(client, "n2_e", "pw123456")
        async with db_module.SessionLocal() as s:
            owner = (await s.execute(sa.text(
                "SELECT id FROM users WHERE username='n2_e'"))).scalar_one()
        ex_id = await _seed_execution(status="queued", owner=owner)

        n = await rd.reconcile_stale_executions(rd.session_factory)
        assert n == 1
        ex = await _get_ex(ex_id)
        assert ex.status == "failed"
        assert ex.failed == 2                        # 零计数兜底
        assert "reconciled" in (ex.config_json or {})
        assert ex.started_at == ex.created_at        # created_at 回填
        assert await _notify_count(owner) == 1        # N2-2:对账也发

        assert await rd.reconcile_stale_executions(rd.session_factory) == 0
        assert await _notify_count(owner) == 1        # 幂等:不重复


class TestIntegrationRecoverStuck:

    async def _seed_running_instance(self, *, fail_streak=0,
                                     cron="*/5 * * * *") -> int:
        async with db_module.SessionLocal() as s:
            await ensure_fk_users(s, 1, 2)
            s.add(IntegrationTask(
                name="n2集成", owner_id=1, visibility="public",
                scenario_id="sc-n2i",
                trigger_cron=cron, result_policy="latest"))
            await s.flush()
            tpl_id = (await s.execute(sa.select(IntegrationTask.id).order_by(
                IntegrationTask.id.desc()))).scalars().first()
            s.add(IntegrationTask(
                name="n2集成", owner_id=1, holder_id=2,
                template_id=tpl_id, enabled=True, state="running",
                running_since=datetime(2026, 1, 1, tzinfo=UTC),
                next_run_at=datetime(2026, 1, 1, tzinfo=UTC),
                fail_streak=fail_streak,
                run_status="ok"))
            await s.commit()
            return (await s.execute(sa.select(IntegrationTask.id).where(
                IntegrationTask.template_id == tpl_id,
                IntegrationTask.holder_id == 2))).scalars().one()

    async def test_recover_counts_streak_via_finish(self, client):
        inst_id = await self._seed_running_instance(fail_streak=0)
        async with db_module.SessionLocal() as db:
            n = await ir._recover_stuck(db)
        assert n == 1
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.state == "idle"
            assert inst.run_status == "timeout"
            assert inst.fail_streak == 1            # 经 _finish 累计
            assert inst.last_run_at is not None      # 经 _finish 回写
            assert "租约超时" in (inst.last_error or "")
            assert inst.next_run_at > datetime(2026, 1, 1, tzinfo=UTC)
            # 上一轮 run=ok → timeout 是翻转,记 run_flipped 时间线
            acts = (await s.execute(sa.text(
                "SELECT COUNT(*) FROM activity_events "
                "WHERE kind='integration.run_flipped'"))).scalar() or 0
            assert acts >= 1

    async def test_recover_auto_pauses_at_threshold(self, client):
        inst_id = await self._seed_running_instance(fail_streak=4)
        async with db_module.SessionLocal() as db:
            await ir._recover_stuck(db)
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            # 4+1=5 达 FAIL_STREAK_AUTO_PAUSE → 自动暂停
            assert inst.state == "paused"
            assert inst.paused_reason == "fail_streak"
            assert inst.fail_streak == 5


# ─── P0-3.2:三态返回与重试(webhook 设计 v3)────────────────────────
class TestTransitionTriState:

    async def test_failed_retries_once(self, client, monkeypatch):
        """FAILED → 1 秒(测试传 0)重试一次:重试成功返回 MOVED;
        两次都失败返回 FAILED(记 error,等待周期对账兜底)。"""
        calls = {"n": 0, "seq": [rd.TransitionResult.FAILED,
                                 rd.TransitionResult.MOVED]}

        async def fake(factory, ex_id, status=None, **kw):
            calls["n"] += 1
            return (calls["seq"].pop(0) if calls["seq"]
                    else rd.TransitionResult.MOVED)

        monkeypatch.setattr(rd, "transition_execution", fake)
        out = await rd.transition_with_retry(
            rd.session_factory, 1, "failed", retry_delay=0)
        assert calls["n"] == 2 and out is rd.TransitionResult.MOVED

        calls.update(n=0, seq=[rd.TransitionResult.FAILED,
                               rd.TransitionResult.FAILED])
        out = await rd.transition_with_retry(
            rd.session_factory, 1, "failed", retry_delay=0)
        assert calls["n"] == 2 and out is rd.TransitionResult.FAILED

    async def test_terminal_and_moved_skip_retry(self, client, monkeypatch):
        """ALREADY_TERMINAL 幂等跳过、不重试(重试反而可能覆写)。"""
        calls = {"n": 0}

        async def fake(factory, ex_id, status=None, **kw):
            calls["n"] += 1
            return rd.TransitionResult.ALREADY_TERMINAL

        monkeypatch.setattr(rd, "transition_execution", fake)
        out = await rd.transition_with_retry(
            rd.session_factory, 1, None, retry_delay=0)
        assert calls["n"] == 1 and out is rd.TransitionResult.ALREADY_TERMINAL

    async def test_write_failure_returns_failed(self, client):
        """db 工厂炸 → FAILED(旧 bool 把它与「已终态」混为同一个
        False,调用方无从分辨、静默等下次启动对账)。"""
        class _Boom:
            def __call__(self):
                raise OSError("db gone")

        assert await rd.transition_execution(
            _Boom(), 1, "failed") is rd.TransitionResult.FAILED


# ─── P0-3.2/3.3:周期对账与 canceled 口径(webhook 设计 v3)─────────
class TestPeriodicReconcile:

    async def _old_running_with_job(self, *, job_status=None, minutes=11) -> int:
        """造一行 running 执行(created_at 拨回 N 分钟前)+ 可选 job 行。"""
        from app.models.execution import ExecutionJob
        ex_id = await _seed_execution(status="running")
        async with db_module.SessionLocal() as s:
            if job_status is not None:
                s.add(ExecutionJob(execution_id=ex_id, status=job_status,
                                   payload={}))
            await s.execute(sa.text(
                "UPDATE executions SET created_at = "
                "now() - make_interval(mins => (:m)::int) WHERE id = :i"),
                {"m": minutes, "i": ex_id})
            await s.commit()
        return ex_id

    async def test_periodic_grace_then_closes_done_job(self, client):
        """宽限(EXEC_RECONCILE_GRACE_S)内的单不动(可能与正在收尾的
        执行抢);超宽限 + job done → failed 收口,reason 带周期前缀
        (与启动期可区分)。"""
        ex_fresh = await self._old_running_with_job(
            job_status="done", minutes=0)
        assert await rd.reconcile_stale_executions(
            rd.session_factory, periodic=True) == 0
        assert (await _get_ex(ex_fresh)).status == "running"

        ex_old = await self._old_running_with_job(job_status="done")
        assert await rd.reconcile_stale_executions(
            rd.session_factory, periodic=True) == 1
        ex = await _get_ex(ex_old)
        assert ex.status == "failed"
        assert ex.config_json["reconciled"]["reason"].startswith(
            "periodic reconcile:")

    async def test_periodic_job_canceled_marks_canceled_no_notify(self, client):
        """P0-3.3/D7:job canceled → 执行 canceled;取消不是失败 ——
        不做零计数兜底、不发通知(回调面上线后 status=canceled)。"""
        await register_and_login(client, "n2_p2", "pw123456")
        async with db_module.SessionLocal() as s:
            owner = (await s.execute(sa.text(
                "SELECT id FROM users WHERE username='n2_p2'"))).scalar_one()
        ex_id = await self._old_running_with_job(job_status="canceled")
        assert await rd.reconcile_stale_executions(
            rd.session_factory, periodic=True) == 1
        ex = await _get_ex(ex_id)
        assert ex.status == "canceled"
        assert ex.failed == 0                     # 不做零计数兜底
        assert "canceled" in ex.config_json["reconciled"]["reason"]
        assert await _notify_count(owner) == 0    # 不通知


# ─── P0-3.1:集成租约令牌(webhook 设计 v3:行锁单事务版)────────────
class TestLeaseToken:

    async def _seed(self, *, state="running",
                    running_since=None) -> int:
        async with db_module.SessionLocal() as s:
            await ensure_fk_users(s, 1, 2)
            s.add(IntegrationTask(
                name="租约", owner_id=1, visibility="public",
                scenario_id="sc-lease",
                trigger_cron="*/5 * * * *", result_policy="latest"))
            await s.flush()
            tpl_id = (await s.execute(sa.select(IntegrationTask.id).order_by(
                IntegrationTask.id.desc()))).scalars().first()
            s.add(IntegrationTask(
                name="租约", owner_id=1, holder_id=2,
                template_id=tpl_id, enabled=True, state=state,
                running_since=running_since,
                next_run_at=datetime(2026, 1, 1, tzinfo=UTC),
                fail_streak=0, run_status="ok"))
            await s.commit()
            return (await s.execute(sa.select(IntegrationTask.id).where(
                IntegrationTask.template_id == tpl_id,
                IntegrationTask.holder_id == 2))).scalars().one()

    async def test_late_result_after_recovery_discarded(self, client):
        """回收(timeout 收口)后迟到的正常结果 → 丢弃:不覆写结果、
        不重复累计 fail_streak(上线回调后即无重复 run_finished)。"""
        old_lease = datetime(2026, 1, 1, tzinfo=UTC)
        inst_id = await self._seed(running_since=old_lease)  # 已超租约
        async with db_module.SessionLocal() as db:
            n = await ir._recover_stuck(db)
        assert n == 1
        async with db_module.SessionLocal() as db:
            inst = await db.get(IntegrationTask, inst_id)
            tpl = await db.get(IntegrationTask, inst.template_id)
            res = await ir._finish(db, inst, tpl, "ok", "", lease=old_lease)
        assert res["status"] == "discarded"
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.state == "idle"
            assert inst.run_status == "timeout"   # 未被迟到的 ok 覆写
            assert inst.fail_streak == 1          # 未重复累计

    async def test_late_result_after_reclaim_discarded(self, client):
        """回收后新一轮已认领(新令牌)→ 旧令牌的结果丢弃,新运行不被
        覆写、不被按停。"""
        old_lease = datetime(2026, 1, 1, tzinfo=UTC)
        new_lease = datetime.now(UTC)
        inst_id = await self._seed(running_since=new_lease)
        async with db_module.SessionLocal() as db:
            inst = await db.get(IntegrationTask, inst_id)
            tpl = await db.get(IntegrationTask, inst.template_id)
            res = await ir._finish(db, inst, tpl, "ok", "", lease=old_lease)
        assert res["status"] == "discarded"
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.state == "running"        # 新一轮照跑
            assert inst.run_status == "ok"

    async def test_late_consent_pause_discarded(self, client):
        """迟到的同意闸暂停不把新一轮运行按停(v3 覆盖面定案:
        _pause_consent_changed 同走租约判定)。"""
        old_lease = datetime(2026, 1, 1, tzinfo=UTC)
        new_lease = datetime.now(UTC)
        inst_id = await self._seed(running_since=new_lease)
        async with db_module.SessionLocal() as db:
            inst = await db.get(IntegrationTask, inst_id)
            tpl = await db.get(IntegrationTask, inst.template_id)
            res = await ir._pause_consent_changed(
                db, inst, tpl, paused_reason="template_changed",
                message="模板内容已变更", lease=old_lease)
        assert res["status"] == "discarded"
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.state == "running"
            assert not inst.paused_reason   # 列默认空串,未被迟到暂停写入

    async def test_matching_lease_finishes_normally(self, client):
        """令牌匹配 → 正常收口(守卫不误伤正常路径)。"""
        lease = datetime.now(UTC)
        inst_id = await self._seed(running_since=lease)
        async with db_module.SessionLocal() as db:
            inst = await db.get(IntegrationTask, inst_id)
            tpl = await db.get(IntegrationTask, inst.template_id)
            res = await ir._finish(db, inst, tpl, "ok", "", lease=lease)
        assert res["status"] != "discarded"
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.state == "idle" and inst.run_status == "ok"

    async def test_scheduler_claim_passes_lease(self, client, monkeypatch):
        """调度链恒传令牌:_claim_due 返回 (id, running_since),
        scheduler_tick → _spawn → run_instance(lease=…)。"""
        import asyncio as _asyncio

        captured: list = []

        async def fake_spawn(iid, lease=None):
            captured.append((iid, lease))

        monkeypatch.setattr(ir, "_spawn", fake_spawn)
        inst_id = await self._seed(state="idle", running_since=None)
        await ir.scheduler_tick()
        for _ in range(3):          # create_task 的协程让一拍再断言
            await _asyncio.sleep(0)
        assert captured, "调度应认领到期实例"
        iid, lease = captured[0]
        assert iid == inst_id and lease is not None
        from app.core.timeutil import ensure_aware
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
        assert ensure_aware(lease) == ensure_aware(inst.running_since)
        ir._inflight.clear()   # fake_spawn 不走 finally 减计数,手动清
