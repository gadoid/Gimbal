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
    # healthz 能力位(§6「可」项):() = 旧执行器(空能力,会把 scope=unit
    # 当 step 处理且带 A0 缺陷)
    server_scopes: tuple = ("step", "unit")
    # 设了 → start() 挂起等放行:模拟「执行器启动窗口」(ss.start 轮询
    # healthz 期间 on_session 尚未回调,评审 2026-11-03 §3.1)
    start_gate: asyncio.Event | None = None


class FakeServerSession:
    instances: "list[FakeServerSession]" = []

    def __init__(self) -> None:
        self.cancel_calls: list[str] = []
        self.gate = asyncio.Event()       # 已进入 a 的执行
        self.release = asyncio.Event()    # 放行(由 cancel 或测试触发)
        FakeServerSession.instances.append(self)

    @property
    def server_version(self) -> str:
        return "fake"

    @property
    def cancel_scopes(self) -> tuple:
        return _Knobs.server_scopes

    async def start(self, **kw) -> None:
        if _Knobs.start_gate is not None:
            await asyncio.wait_for(_Knobs.start_gate.wait(), timeout=10.0)

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
    _Knobs.server_scopes = ("step", "unit")
    _Knobs.start_gate = None
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


async def _wait_instance() -> FakeServerSession:
    """等假会话实例出现(不等进入运行 —— start() 可能仍在启动窗口挂起)。"""
    for _ in range(200):
        if FakeServerSession.instances:
            return FakeServerSession.instances[0]
        await asyncio.sleep(0.05)
    raise AssertionError("假执行器会话未创建")


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
        # 执行 kind 仍是 scenario(POST /api/runs 带 graph)—— 说明文案按任务体给
        assert r.json()["cancel_note"] == (
            "已请求取消:当前单元跑完后停止,后续单元记为已取消")

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
        # 终态留痕有解释:详情/列表的 cancel_note 说明为何按真实结果收口
        d = (await client.get(f"/api/executions/{exec_id}", headers=headers)).json()
        assert d["cancel_note"] == (
            "已请求取消,但当时所有单元均已启动、没有可停的单元,已按真实结果收口")
        lst = (await client.get("/api/executions", headers=headers)).json()["items"]
        row = next(i for i in lst if i["id"] == exec_id)
        assert row["cancel_note"] == d["cancel_note"]

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

    async def test_cancel_during_executor_start_is_delivered(
            self, client, monkeypatch):
        """3.1(评审 2026-11-03):执行器启动窗口(ss.start 轮询 healthz、
        on_session 未回调)取消被接受 → 下发任务先建;session 就绪后能力位
        通过 → 下发 scope=unit → a passed、b cancelled → 执行 canceled。"""
        headers = await _setup(client, monkeypatch)
        _Knobs.start_gate = asyncio.Event()
        exec_id = await _post_graph(client, headers)
        await _wait_instance()

        d = (await client.get(f"/api/executions/{exec_id}", headers=headers)).json()
        assert d["status"] == "running"          # 已过 _mark_running
        assert d["cancelable"] is True           # 能力位未落,server 缺省可取消

        r = await client.post(f"/api/executions/{exec_id}/cancel", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["cancel_requested"] is True

        _Knobs.start_gate.set()                  # 放行 start → on_session → 下发
        sess = await _wait_session()
        ex = await _wait_terminal(exec_id)
        assert ex.status == "canceled"
        assert sess.cancel_calls == ["unit"]
        assert (ex.passed, ex.failed, ex.skipped) == (1, 0, 1)

    async def test_old_executor_cancel_during_start_marks_no_unit_cancel(
            self, client, monkeypatch):
        """3.1 附带:旧执行器(cancel_scopes 空)启动窗口取消被读侧接受、
        session 就绪后能力位 False → 停止下发;按真实结果收口并留痕
        cancelIgnored=executor_no_unit_cancel,detail/list cancel_note 给
        对应解释(与「所有单元已启动」区分)。"""
        headers = await _setup(client, monkeypatch)
        _Knobs.server_scopes = ()
        _Knobs.start_gate = asyncio.Event()
        exec_id = await _post_graph(client, headers)
        sess = await _wait_instance()

        r = await client.post(f"/api/executions/{exec_id}/cancel", headers=headers)
        assert r.status_code == 200, r.text      # 能力位未落,读侧接受

        _Knobs.start_gate.set()
        await _wait_session()                    # 进入运行(未收到取消)
        sess.release.set()                       # 旧执行器正常跑完
        ex = await _wait_terminal(exec_id)
        assert ex.status == "done"
        assert sess.cancel_calls == []           # 未下发
        assert (ex.config_json or {}).get("cancelIgnored") == "executor_no_unit_cancel"
        d = (await client.get(f"/api/executions/{exec_id}", headers=headers)).json()
        assert d["cancel_note"] == (
            "已请求取消,但执行器版本不支持单元级中途取消,取消未下发,"
            "已按真实结果收口")
        lst = (await client.get("/api/executions", headers=headers)).json()["items"]
        row = next(i for i in lst if i["id"] == exec_id)
        assert row["cancel_note"] == d["cancel_note"]


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


class TestCapabilityGate:
    """§6「可」项 + legacy 通道:单元级取消按能力位放行/拦截。"""

    async def test_old_executor_server_graph_cancel_409(self, client, monkeypatch):
        """旧执行器(healthz 空能力)→ on_session 落 unit_cancel=False;
        已认领 graph 的取消 409(文案点明执行器版本)、cancelable 投影 False、
        取消不下发 → 按真实结果跑完。"""
        from app.models.execution import ExecutionJob

        headers = await _setup(client, monkeypatch)
        _Knobs.server_scopes = ()            # 旧执行器
        exec_id = await _post_graph(client, headers)
        sess = await _wait_session()

        for _ in range(100):                 # 等 session 就绪 + 能力位落库
            d = (await client.get(f"/api/executions/{exec_id}",
                                  headers=headers)).json()
            if d["cancelable"] is False:
                break
            await asyncio.sleep(0.05)
        assert d["cancelable"] is False
        r = await client.post(f"/api/executions/{exec_id}/cancel", headers=headers)
        assert r.status_code == 409
        assert "执行器版本过低" in r.json()["detail"]["message"]

        async with db_module.SessionLocal() as s:
            payload = (await s.execute(sa.select(ExecutionJob.payload).where(
                ExecutionJob.execution_id == exec_id))).scalar_one()
        assert payload["unit_cancel"] is False

        sess.release.set()                   # 未收到取消 → 正常跑完
        ex = await _wait_terminal(exec_id)
        assert ex.status == "done"
        assert sess.cancel_calls == []

    async def test_legacy_graph_cancel_via_signal_file(self, client, monkeypatch):
        """legacy 链 + 本地引擎带 cancel-file 能力:取消 → 平台写信号文件 →
        执行器(假 launch)读到后跑完在飞单元、其余 cancelled → 执行 canceled。"""
        from pathlib import Path

        from app.core.config import settings
        from app.models.execution import ExecutionJob
        from app.services import graph_dispatch as gd

        headers = await _setup(client, monkeypatch)
        monkeypatch.setattr(settings, "EXEC_CHAIN", "legacy", raising=True)
        # 同环境部署(GIMBAL_BIN 空)→ 能力读本地 gimbal FEATURES;外部
        # GIMBAL_BIN 无法探测、保守 False 的路径由 test_run_cancel 的
        # _graph_unit_cancelable 单测面覆盖
        monkeypatch.setattr(settings, "GIMBAL_BIN", "", raising=True)
        seen: dict = {}

        async def _fake_launch(case_path, *, step_to=None, report_dir=None,
                               cwd=None, timeout=None, engine_log_path=None,
                               on_event=None, on_log=None, log_counters=None,
                               n_runs=1, retry=0, cancel_file=None):
            seen["cancel_file"] = cancel_file
            assert cancel_file is not None and Path(cancel_file).name == "cancel-unit"

            def ev(d):
                if on_event is not None:
                    on_event(dict(d))
            ev({"event_type": "scenario.start", "seq": 2, "scenario_id": "sc-a",
                "scenario_name": "a", "step_count": 1, "unit": "a", "attempt": "1.1"})
            for _ in range(200):             # 等平台写信号文件(单元级取消)
                if Path(cancel_file).exists():
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("cancel signal file never appeared")
            ev({"event_type": "scenario.end", "seq": 3, "scenario_id": "sc-a",
                "status": "passed", "step_count": 1, "unit": "a", "attempt": "1.1"})
            ev({"event_type": "run.finished", "seq": 6, "exit_code": 0,
                "total": 2, "passed": 1, "failed": 0, "skipped": 1, "attempts": 2,
                "details": [{"unit": "a", "status": "passed"},
                            {"unit": "b", "status": "cancelled"}]})
            return launch_ok()

        monkeypatch.setattr(gd, "launch", _fake_launch)
        exec_id = await _post_graph(client, headers)

        for _ in range(100):                 # 等 spawn 前能力位落库(legacy 可取消)
            d = (await client.get(f"/api/executions/{exec_id}",
                                  headers=headers)).json()
            if d["cancelable"] is True:
                break
            await asyncio.sleep(0.05)
        assert d["cancelable"] is True
        r = await client.post(f"/api/executions/{exec_id}/cancel", headers=headers)
        assert r.status_code == 200, r.text

        ex = await _wait_terminal(exec_id)
        assert ex.status == "canceled"
        assert (ex.passed, ex.failed, ex.skipped) == (1, 0, 1)
        async with db_module.SessionLocal() as s:
            payload = (await s.execute(sa.select(ExecutionJob.payload).where(
                ExecutionJob.execution_id == exec_id))).scalar_one()
        assert payload["chain"] == "legacy" and payload["unit_cancel"] is True
