"""N2 终态迁移归一回归。

覆盖:transition_execution 原子守卫(重复迁移无效、不重复通知)、
派生状态(failed>0 → failed)、计数兜底、counterDrift、三个异常路径
补通知(stuck / 启动对账 / graph 恢复口径共用同一函数)、canceled
三类不发通知、集成 _recover_stuck 经 _finish 计 fail_streak/自动暂停。
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
        assert moved is True
        ex = await _get_ex(ex_id)
        assert ex.status == "failed" and ex.finished_at is not None
        assert await _notify_count(owner) == 1      # 异常收口也发(N2-2)

        moved2 = await rd.transition_execution(
            rd.session_factory, ex_id, "failed")
        assert moved2 is False                       # 已终态:无效迁移
        assert await _notify_count(owner) == 1       # 不重复通知
        assert (await _get_ex(ex_id)).status == "failed"

    async def test_derived_status_and_drift_flag(self, client):
        await register_and_login(client, "n2_b", "pw123456")
        # passed=total → 派生 done,无 drift
        ex_ok = await _seed_execution(passed=2, failed=0, total=2)
        assert await rd.transition_execution(rd.session_factory, ex_ok, None)
        ex = await _get_ex(ex_ok)
        assert ex.status == "done"
        assert not (ex.config_json or {}).get("counterDrift")
        # failed=1 且 total=3 → 派生 failed + 计数兜底 + drift 标记
        ex_bad = await _seed_execution(passed=0, failed=1, total=3)
        assert await rd.transition_execution(
            rd.session_factory, ex_bad, None, count_fallback=True)
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
                identity_mode="personal", scenario_id="sc-n2i",
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
