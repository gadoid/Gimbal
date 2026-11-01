"""M3 + S4 修复(修复方案 2026-11-01 §4/§5):回调契约。

M3:全部事件时间字段用 iso_utc_z(UTC、Z 结尾);此前对 aware 值
``isoformat() + "Z"`` 产出 ``+00:00Z`` 双后缀,调用方解析失败。
S4:投递行构造错误不得阻止执行进入终态 —— 只有数据库错误透传(与终态
同生共死),其余异常只记 error、本条不投递。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Execution, User
from app.models.integration_task import IntegrationTask
from app.services import integration_runner as ir
from app.services import run_dispatcher as rd
from app.services.run_dispatcher import STATUS_DONE

from .inbound_fixtures import (
    deliveries as _deliveries, mk_execution as _mk_execution,
    mk_task_pair as _mk_pair, seed_alias as _seed_alias,
    seed_platform_user as _seed_platform_user,
)

_Z_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z$")


class TestM3TimestampFormat:
    async def test_payload_timestamps_parse(self, client):
        """三类事件的全部时间字段匹配 UTC-Z 且可被 fromisoformat 解析。"""
        await _seed_platform_user()
        # execution.finished(带 started_at 的 aware 值)
        async with db_module.SessionLocal() as s:
            sys_uid = (await s.execute(sa.select(User.id).where(
                User.is_system == True))).scalar_one()  # noqa: E712
        await _seed_alias()
        async with db_module.SessionLocal() as s:
            ex = Execution(
                scenario_id="sc-z", scenario_name="Z", owner_id=sys_uid,
                owner_name="平台系统", status="running", total_runs=1,
                caller_alias_name="agent-sys",
                started_at=datetime(2026, 11, 1, 14, 6, 27, 735108,
                                    tzinfo=timezone.utc))
            s.add(ex)
            await s.commit()
            ex_id = ex.id
        await rd.transition_execution(
            db_module.SessionLocal, ex_id, STATUS_DONE)
        # integration.run_finished + paused
        tpl_id, inst_id = await _mk_pair()
        async with db_module.SessionLocal() as db:
            tpl = await db.get(IntegrationTask, tpl_id)
            inst = await db.get(IntegrationTask, inst_id)
            await ir._finish(db, inst, tpl, "ok", "", check_status="pass",
                             lease=inst.running_since)
        tpl2_id, inst2_id = await _mk_pair(name="z2")
        async with db_module.SessionLocal() as db:
            tpl2 = await db.get(IntegrationTask, tpl2_id)
            inst2 = await db.get(IntegrationTask, inst2_id)
            await ir._pause_consent_changed(
                db, inst2, tpl2, paused_reason="template_changed",
                message="m", lease=inst2.running_since)
        bodies = [json.loads(r.body) for r in await _deliveries()]
        checked = 0
        for b in bodies:
            for key in ("startedAt", "finishedAt", "at"):
                if key in b and b[key] is not None:
                    assert _Z_RE.match(b[key]), (b["event"], key, b[key])
                    datetime.fromisoformat(b[key].replace("Z", "+00:00"))
                    checked += 1
        assert checked >= 3


# ── S4:构造错误不得阻止终态 ──────────────────────────────────────


class TestS4ConstructionErrors:
    async def test_non_db_error_keeps_terminal(self, client, monkeypatch):
        await _seed_alias()
        ex_id = await _mk_execution(caller="agent-sys")
        # 构造面异常(非 SQLAlchemyError):如 payload 组装抛 ValueError
        async def _boom(db, ex):
            raise ValueError("payload assembly failed")

        monkeypatch.setattr(
            "app.services.webhook_outbox._enqueue_execution_finished", _boom)
        res = await rd.transition_execution(
            db_module.SessionLocal, ex_id, STATUS_DONE)
        assert res is rd.TransitionResult.MOVED
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, ex_id)
            assert ex.status == STATUS_DONE          # 终态已写
        assert await _deliveries() == []             # 无投递行

    async def test_db_error_rolls_back_terminal(self, client, monkeypatch):
        await _seed_alias()
        ex_id = await _mk_execution(caller="agent-sys")
        from sqlalchemy.exc import IntegrityError

        async def _db_boom(db, ex):
            raise IntegrityError("stmt", {}, Exception("db"))

        monkeypatch.setattr(
            "app.services.webhook_outbox._enqueue_execution_finished",
            _db_boom)
        res = await rd.transition_execution(
            db_module.SessionLocal, ex_id, STATUS_DONE)
        assert res is rd.TransitionResult.FAILED
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, ex_id)
            assert ex.status == "running"            # 终态未写(原子性保留)

