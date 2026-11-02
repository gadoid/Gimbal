"""graph 单元级取消(方案 2026-11-02 P2-P5):server 链 graph 中途取消 ——
跑完当前单元再停。

假执行器会话(替换 gimbal_server_session.ServerSession):发 a 的 scenario.start
后挂起等待,收到 cancel(scope=unit) 放行 → a passed、b cancelled(或忽略取消
两者都 passed);平台侧按主体是否有 cancelled 收口 canceled / cancelIgnored。
"""
from __future__ import annotations

import asyncio

import sqlalchemy as sa

from app.core import db as db_module
from app.models.execution import Execution, ExecutionRow
from tests.helpers import launch_ok, register_and_login

from .test_graph_dispatch import _mk_scenario


class _Knobs:
    run_id_ready = True      # False → cancel() 先返回 False(POST /runs 未返回 runId)
    honor_cancel = True      # False → 执行器忽略取消,两单元都 passed


class FakeServerSession:
    instances: "list[FakeServerSession]" = []

    def __init__(self) -> None:
        self.cancel_calls: list[str] = []
        self.gate = asyncio.Event()       # 已进入 a 的执行
        self.release = asyncio.Event()    # 放行(由 cancel 或测试触发)
        FakeServerSession.instances.append(self)

    async def start(self, **kw) -> None:
        return None

    async def close(self) -> None:
        return None

    async def cancel(self, *, scope: str = "step") -> bool:
        self.cancel_calls.append(scope)
        if not _Knobs.run_id_ready:
            return False
        self.release.set()
        return True

    async def run_case(self, case_path, *, n_runs=1, on_event=None, m2_info=None):
        def ev(d):
            if on_event is not None:
                on_event(dict(d))
        ev({"event_type": "scenario.start", "seq": 2, "scenario_id": "sc-a",
            "scenario_name": "a", "step_count": 1, "unit": "a", "attempt": "1.1"})
        self.gate.set()
        await asyncio.wait_for(self.release.wait(), timeout=10.0)
        ev({"event_type": "scenario.end", "seq": 3, "scenario_id": "sc-a",
            "status": "passed", "step_count": 1, "unit": "a", "attempt": "1.1"})
        cancelled = bool(self.cancel_calls) and _Knobs.honor_cancel
        if not cancelled:
            ev({"event_type": "scenario.start", "seq": 4, "scenario_id": "sc-b",
                "scenario_name": "b", "step_count": 1, "unit": "b", "attempt": "1.1"})
            ev({"event_type": "scenario.end", "seq": 5, "scenario_id": "sc-b",
                "status": "passed", "step_count": 1, "unit": "b", "attempt": "1.1"})
        details = [{"unit": "a", "status": "passed"},
                   {"unit": "b", "status": "cancelled" if cancelled else "passed"}]
        ev({"event_type": "run.finished", "seq": 6, "exit_code": 0,
            "total": 2, "passed": 1 if cancelled else 2, "failed": 0,
            "skipped": 1 if cancelled else 0, "attempts": 2, "details": details})
        return launch_ok()


async def _fake_convert(scenario):
    return {"consumer": "platform", "converted": dict(scenario)}


async def _setup(client, monkeypatch, *, run_id_ready=True, honor_cancel=True):
    from app.core.config import settings
    from app.services import gimbal_server_session as gss, plate_client as pc

    FakeServerSession.instances.clear()
    _Knobs.run_id_ready = run_id_ready
    _Knobs.honor_cancel = honor_cancel
    monkeypatch.setattr(settings, "EXEC_CHAIN", "server", raising=True)
    monkeypatch.setattr(gss, "ServerSession", FakeServerSession)
    monkeypatch.setattr(pc, "convert", _fake_convert)
    headers = await register_and_login(client)
    await _mk_scenario(client, headers, "sc-a")
    await _mk_scenario(client, headers, "sc-b")
    return headers


async def _post_graph(client, headers) -> int:
    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-a",
        "graph": {"mode": "aggregate",
                  "units": [{"ref": "a", "scenarioId": "sc-a"},
                            {"ref": "b", "scenarioId": "sc-b"}]},
    })
    assert r.status_code == 201, r.text
    return r.json()["executionId"]


async def _wait_session() -> FakeServerSession:
    for _ in range(200):
        if FakeServerSession.instances and FakeServerSession.instances[0].gate.is_set():
            return FakeServerSession.instances[0]
        await asyncio.sleep(0.05)
    raise AssertionError("假执行器未进入运行")


async def _wait_terminal(exec_id: int) -> Execution:
    for _ in range(400):
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, exec_id)
        if ex is not None and ex.status in ("done", "failed", "canceled"):
            return ex
        await asyncio.sleep(0.05)
    raise AssertionError("执行未终态")


async def _rows(exec_id: int) -> list[tuple]:
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(sa.select(ExecutionRow).where(
            ExecutionRow.execution_id == exec_id).order_by(ExecutionRow.seq))
        ).scalars().all()
    return [(r.seq, r.unit_id, r.status) for r in rows]


class TestServerGraphUnitCancel:
    async def test_running_server_graph_cancel_finishes_inflight_then_canceled(
            self, client, monkeypatch):
        """取消 → 200 且取消中;执行器收到 scope=unit;a 跑完 passed、b
        cancelled → 执行 canceled,计数 = 真实结果 + skipped。"""
        headers = await _setup(client, monkeypatch)
        exec_id = await _post_graph(client, headers)
        sess = await _wait_session()

        d = (await client.get(f"/api/executions/{exec_id}", headers=headers)).json()
        assert d["status"] == "running"
        assert d["cancelable"] is True and d["cancel_requested"] is False

        r = await client.post(f"/api/executions/{exec_id}/cancel", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["cancel_requested"] is True
        assert r.json()["cancelable"] is False

        ex = await _wait_terminal(exec_id)
        assert ex.status == "canceled"
        assert sess.cancel_calls == ["unit"]
        assert (ex.passed, ex.failed, ex.skipped) == (1, 0, 1)
        assert await _rows(exec_id) == [
            (0, "graph", "canceled"), (1, "a", "passed"), (2, "b", "cancelled")]
        assert "cancelIgnored" not in (ex.config_json or {})
        lst = (await client.get("/api/executions", headers=headers)).json()["items"]
        row = next(i for i in lst if i["id"] == exec_id)
        assert row["cancelable"] is False and row["cancel_requested"] is False

    async def test_cancel_before_run_id_is_retried(self, client, monkeypatch):
        """POST /runs 未返回 runId 时 cancel() 返回 False → 轮询器 0.5s 重试直到受理。"""
        headers = await _setup(client, monkeypatch, run_id_ready=False)
        exec_id = await _post_graph(client, headers)
        sess = await _wait_session()
        r = await client.post(f"/api/executions/{exec_id}/cancel", headers=headers)
        assert r.status_code == 200, r.text
        for _ in range(100):
            if len(sess.cancel_calls) >= 2:
                break
            await asyncio.sleep(0.05)
        assert len(sess.cancel_calls) >= 2 and set(sess.cancel_calls) == {"unit"}
        _Knobs.run_id_ready = True            # 下一次重试受理
        ex = await _wait_terminal(exec_id)
        assert ex.status == "canceled"

    async def test_cancel_ignored_when_all_units_already_started(
            self, client, monkeypatch):
        """执行器没有可停的单元(两者都 passed)→ 按真实结果收口 + cancelIgnored。"""
        headers = await _setup(client, monkeypatch, honor_cancel=False)
        exec_id = await _post_graph(client, headers)
        await _wait_session()
        r = await client.post(f"/api/executions/{exec_id}/cancel", headers=headers)
        assert r.status_code == 200, r.text
        ex = await _wait_terminal(exec_id)
        assert ex.status == "done"
        assert (ex.passed, ex.failed, ex.skipped) == (2, 0, 0)
        assert ex.config_json.get("cancelIgnored") == "all units already started"

    async def test_cancel_in_materialize_window_skips_dispatch(
            self, client, monkeypatch):
        """物化完成、下发前命中取消位 → 不下发执行器,canceled 零计数。"""
        from app.services import execution_queue as _eq, graph_dispatch as gd

        headers = await _setup(client, monkeypatch)
        orig = gd.materialize_graph

        async def _materialize_then_cancel(session, owner_id, spec, **kw):
            out = await orig(session, owner_id, spec, **kw)
            # 写取消位(全 schema 内唯一的 job 行)+ 进程内快速通道
            from app.models.execution import ExecutionJob
            ids = (await session.execute(sa.select(ExecutionJob.execution_id))
                   ).scalars().all()
            await session.execute(sa.update(ExecutionJob).values(cancel_requested=True))
            await session.commit()
            for eid in ids:
                _eq._cancel_hint.add(eid)
            return out
        monkeypatch.setattr(gd, "materialize_graph", _materialize_then_cancel)

        exec_id = await _post_graph(client, headers)
        ex = await _wait_terminal(exec_id)
        assert ex.status == "canceled"
        assert (ex.passed, ex.failed, ex.skipped) == (0, 0, 0)
        assert ex.started_at is None                 # 从未启动,不回填
        assert FakeServerSession.instances == []     # 未下发


def _live_cancel_pollers() -> set:
    return {t for t in asyncio.all_tasks()
            if not t.done()
            and "_poll_cancel" in getattr(t.get_coro(), "__qualname__", "")}


class TestGraphRecoveryNoPollerLeak:
    async def test_at_most_once_recovery_does_not_leak_cancel_poller(
            self, client, monkeypatch):
        """恢复分支(已有事件 → failed 收口、不重放)在 try/finally 之前返回,
        _teardown 不执行;取消轮询器若在此之前启动,会每 0.5s 查库直到进程
        退出(恢复后执行已 failed,取消位永远不会置上)。"""
        from app.models.execution import ExecutionJob
        from app.services import run_dispatcher as rd

        headers = await _setup(client, monkeypatch)
        exec_id = await _post_graph(client, headers)
        sess = await _wait_session()
        sess.release.set()                           # 正常跑完,留下事件
        ex = await _wait_terminal(exec_id)
        assert ex.status == "done"

        # 崩溃残留:事件已落库、执行回到未终态,job 重放同一配方
        async with db_module.SessionLocal() as s:
            payload = (await s.execute(
                sa.select(ExecutionJob.payload)
                .where(ExecutionJob.execution_id == exec_id))).scalar_one()
            ex = await s.get(Execution, exec_id)
            ex.status = "queued"
            ex.finished_at = None
            await s.commit()

        before = _live_cancel_pollers()
        await rd.run_job_from_payload({"payload": payload})
        await asyncio.sleep(0)

        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, exec_id)
        assert ex.status == "failed"
        assert "at-most-once" in (ex.config_json or {}).get("dispatcherError", "")
        assert len(FakeServerSession.instances) == 1     # 恢复未再下发
        assert _live_cancel_pollers() - before == set()
