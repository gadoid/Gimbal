"""S6 失败通知两行式根因摘要(结构化日志设计 §5 S6 / 决策 D6)。

覆盖:
- #304 型:锚 = ``step.failed`` 事件,行 1 = 锚前最近 WARNING,行 2 = 其前
  同 unit/step 一行(INFO 带 ``expression=`` 的根因细节);
- 通知 body 出口:摘要进 body、打码生效(token=/Bearer 形态)、无日志
  执行回落现状文案;
- 回退链:无 WARNING/ERROR → 锚前最后两条日志行;多 unit 最多 3 组;
- 竞态防回归(§7 四步收口):失败行日志刚进缓冲即终态 —— finalize()
  先冲刷余量,摘要必须取到。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models.execution import Execution
from app.models.permission import Notification
from app.services import execution_store
from app.services.run_dispatcher import _failure_digest, _notify_finished, _mask_secrets
from tests.helpers import register_and_login

_T0 = "2026-10-14T01:00:00+00:00"


def _log(ts: str, message: str, **labels) -> dict:
    d = {"timestamp": ts, "level": "INFO", "logger": "gimbal.core.x",
         "category": "step", "message": message}
    d.update(labels)
    return d


def _failed_event(ts: str, unit: str, step: str, seq: int = 900) -> dict:
    return {"event_type": "step.failed", "timestamp": ts,
            "step_id": step, "unit": unit, "step": step, "seq": seq}


async def _seed_failed_execution(client, *, batch_id=None) -> tuple[int, int]:
    headers = await register_and_login(client)
    async with db_module.SessionLocal() as s:
        from app.models.user import User
        me = (await s.execute(sa.select(User).order_by(User.id.desc())
                              )).scalars().first()
        ex = Execution(scenario_id="sc-digest", owner_name="t", owner_id=me.id,
                       status="failed", total_runs=1, passed=0, failed=1,
                       batch_id=batch_id)
        s.add(ex)
        await s.commit()
        return ex.id, me.id


class TestMaskSecrets:

    def test_value_shapes_masked_process_words_kept(self):
        assert _mask_secrets("token=sk-live-abcdef123") == "token=***"
        assert _mask_secrets('Authorization: "Bearer abc123def456"') == \
            'Authorization: "Bearer ***"'
        assert _mask_secrets("刷新 token: tag=u1") == "刷新 token: ***"
        # 过程性词面(无取值形状)不动
        assert _mask_secrets("PreToken 模式跳过 refresh") == \
            "PreToken 模式跳过 refresh"


class TestFailureDigest:

    async def test_304_shape_expression_line_survives(self, client):
        """#304 型:WARNING 只有泛化句,根因细节在前一行 INFO(expression=)。"""
        eid, _ = await _seed_failed_execution(client)
        async with db_module.SessionLocal() as s:
            await execution_store.insert_logs(s, eid, [
                _log(_T0, "ExtractExecutor 执行提取: "
                          "expression=$.call.response.body.data.data[0].order_id",
                     unit="bl-001", step="step-002"),
                _log("2026-10-14T01:00:02+00:00", "Phase aborting: 业务阶段硬失败",
                     level="WARNING", unit="bl-001", step="step-002"),
                # 别的 unit 的 WARNING 更近 —— 不得串行进 bl-001 的摘要
                _log("2026-10-14T01:00:03+00:00", "other-unit warning",
                     level="WARNING", unit="bl-002", step="step-001"),
            ], seq_base=0)
            await execution_store.insert_events(s, eid, [
                _failed_event("2026-10-14T01:00:04+00:00",
                              "bl-001", "step-002")])
            await s.commit()
            digest = await _failure_digest(s, eid)
        assert digest is not None
        assert "expression=" in digest
        assert "bl-001: Phase aborting" in digest
        assert "other-unit warning" not in digest

    async def test_fallback_last_two_lines_and_max_three_units(self, client):
        eid, _ = await _seed_failed_execution(client)
        async with db_module.SessionLocal() as s:
            await execution_store.insert_logs(s, eid, [
                _log(_T0, f"line-{u}-{i}", unit=f"u-{u}", step="step-000")
                for u in range(1, 5) for i in (1, 2)
            ], seq_base=0)
            await execution_store.insert_events(s, eid, [
                _failed_event(f"2026-10-14T01:00:{9 - u:02d}+00:00",
                              f"u-{u}", "step-000", seq=900 + u)
                for u in range(1, 5)])
            await s.commit()
            digest = await _failure_digest(s, eid)
        assert digest is not None
        # 无 WARNING → 回退锚前最后两条日志行;4 个失败 unit → 取最新 3 组
        # (种子 ts:u-1 最晚 … u-4 最早,ts 倒序取前三 = u-1/u-2/u-3)
        assert "u-1: line-1-2" in digest and "↳ line-1-1" in digest
        assert "u-3: line-3-2" in digest
        assert "u-4" not in digest
        assert len([ln for ln in digest.splitlines() if not ln.startswith("↳")]) == 3

    async def test_no_logs_returns_none(self, client):
        eid, _ = await _seed_failed_execution(client)
        async with db_module.SessionLocal() as s:
            await execution_store.insert_events(s, eid, [
                _failed_event(_T0, "bl-001", "step-000")])
            await s.commit()
            assert await _failure_digest(s, eid) is None


class TestNotifyBody:

    async def test_failed_notification_body_carries_masked_digest(self, client):
        """验收:失败通知 body 含 expression=;token 形态打码后出口。"""
        eid, uid = await _seed_failed_execution(client)
        async with db_module.SessionLocal() as s:
            await execution_store.insert_logs(s, eid, [
                _log(_T0,
                     "ExtractExecutor 执行提取: expression=$.data[0].order_id",
                     unit="bl-001", step="step-001"),
                _log("2026-10-14T01:00:01+00:00",
                     "refresh failed token=sk-live-abcdef123456 retry later",
                     level="WARNING", unit="bl-001", step="step-001"),
            ], seq_base=0)
            await execution_store.insert_events(s, eid, [
                _failed_event("2026-10-14T01:00:02+00:00",
                              "bl-001", "step-001")])
            await s.commit()
            ex = await s.get(Execution, eid)
            await _notify_finished(ex, "failed")

        async with db_module.SessionLocal() as s:
            rows = (await s.execute(sa.select(Notification).where(
                Notification.user_id == uid,
                Notification.type == "execution_finished"))).scalars().all()
        assert len(rows) == 1
        body = rows[0].body
        assert "expression=" in body
        assert "sk-live-abcdef123456" not in body
        assert "token=***" in body

    async def test_no_log_execution_keeps_current_body(self, client):
        eid, uid = await _seed_failed_execution(client)
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, eid)
            await _notify_finished(ex, "failed")
        async with db_module.SessionLocal() as s:
            n = (await s.execute(sa.select(Notification).where(
                Notification.user_id == uid))).scalars().one()
        assert n.body == "sc-digest · 0 通过 / 1 失败"

    async def test_batch_notification_stays_aggregate(self, client):
        """批次通知走 SQL 聚合并发安全路径,不注入摘要(§3.2 第五轮)。"""
        eid, uid = await _seed_failed_execution(client, batch_id="batch-d1")
        async with db_module.SessionLocal() as s:
            await execution_store.insert_logs(s, eid, [
                _log(_T0, "expression=$.x", level="WARNING",
                     unit="bl-001", step="step-001")], seq_base=0)
            await execution_store.insert_events(s, eid, [
                _failed_event("2026-10-14T01:00:01+00:00",
                              "bl-001", "step-001")])
            await s.commit()
            ex = await s.get(Execution, eid)
            await _notify_finished(ex, "failed")
        async with db_module.SessionLocal() as s:
            n = (await s.execute(sa.select(Notification).where(
                Notification.user_id == uid))).scalars().one()
        assert "批次" in n.body


class TestRaceRegression:
    """§7 四步收口防回归:失败行日志刚进缓冲即终态。"""

    async def test_finalize_flushes_tail_logs_before_digest(self, client):
        from app.services.run_dispatcher import _EventIngester

        eid, _ = await _seed_failed_execution(client)
        ingester = _EventIngester(db_module.SessionLocal, eid)
        ingester.start()
        # 最后一步失败:根因日志刚进缓冲(未达阈值、ticker 未到点),
        # 随即 gather 收口 finalize → 终态 → 通知摘要
        ingester.on_log(_log(_T0, "ExtractExecutor 执行提取: "
                                 "expression=$.call.response.body.order_id",
                             unit="bl-001", step="step-002"))
        ingester.on_log(_log("2026-10-14T01:00:01+00:00",
                             "Phase aborting", level="WARNING",
                             unit="bl-001", step="step-002"))
        ingester.on_event(_failed_event(
            "2026-10-14T01:00:02+00:00", "bl-001", "step-002"))
        await ingester.finalize()
        async with db_module.SessionLocal() as s:
            digest = await _failure_digest(s, eid)
        assert digest is not None and "expression=" in digest
