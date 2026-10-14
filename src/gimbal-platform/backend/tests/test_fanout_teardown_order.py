"""阻断回归(2026-10-13 复审):server 链尾部日志必须在 finalize 前入库。

时序缺陷:_fanout 此前先 ``ingester.finalize()``、终态,``_teardown()``
(server_pool.close())在 finally。server 进程不随 run 结束退出,stderr 泵
在 run_case 返回后仍会读到滞留管道的行(最后一步 WARNING / uvicorn
收尾)——这些行进的是**已停止**的 ingester,永远不落库,却已计入
logs_ingested(S9 对账失真)。launch 链无此问题(进程退出即 EOF)。

闸:假池以真 ``_pump_stderr`` 驱动,close() 先吐尾行再 EOF(模拟
terminate 前管道突发)——断言尾行已入库且 ingest_stats 与行数对账。
"""
from __future__ import annotations

import asyncio
import json

import sqlalchemy as sa

from app.core import db as db_module
from app.models.execution import Execution, ExecutionEvent
from app.models.user import User
from app.services import run_dispatcher
from tests.helpers import make_draft, register_and_login

_STEPS = [{
    "call": {"view_hints": {"endpoint_id": "fin.order.add"}},
    "request": {"body": {"customer_id": "${var.a}"}},
}]


def _logline(message: str) -> str:
    return json.dumps({
        "timestamp": "2026-10-14T01:00:00+00:00", "level": "INFO",
        "logger": "gimbal.core.x", "category": "core", "message": message,
    }, ensure_ascii=False)


class _TrailingLogPool:
    """server 链假池:start 起真 _pump_stderr;run_case 吐运行中一行并
    直接成功;close() 先吐滞留尾行再 EOF(进程 terminate 前的管道突发),
    等泵收尾后返回 —— 与 ServerSessionPool.close 的「泵排空才返回」
    契约一致。"""

    def __init__(self, *, size: int) -> None:
        # 队列模拟管道:行随时入队、泵逐行读,None = EOF
        self._q: "asyncio.Queue[bytes | None]" = asyncio.Queue()
        self._pump: "asyncio.Task | None" = None

    # stderr 协议(泵消费面)
    async def readline(self) -> bytes:
        item = await self._q.get()
        return item if item is not None else b""

    def _emit(self, message: str) -> None:
        self._q.put_nowait((_logline(message) + "\n").encode("utf-8"))

    @property
    def first(self):  # 调试会话注册用;本测试不涉调试
        return None

    async def start(self, *, engine_log_path=None, cwd=None,
                    on_log=None, log_counters=None) -> None:
        from app.core.config import settings
        from app.services.gimbal_server_session import _pump_stderr
        self._pump = asyncio.get_event_loop().create_task(
            _pump_stderr(self, None, on_log,
                         settings.EXEC_INGEST_LOG_LEVEL, log_counters))

    async def run_case(self, case_path, **kwargs):
        from app.services.gimbal_launcher import LaunchResult
        self._emit("mid-run-line")
        return LaunchResult(launch_status="ok", exit_code=0, total=1,
                            passed=1, failed=0, skipped=0, attempts=1,
                            argv=["fake-server"])

    async def close(self) -> None:
        self._emit("trailing-after-run")
        self._q.put_nowait(None)     # EOF
        if self._pump is not None:
            try:
                await self._pump
            except Exception:  # noqa: BLE001
                pass


async def _wait_final(execution_id: int, timeout_s: float = 30.0) -> Execution:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, execution_id)
            if ex.status in ("done", "failed", "canceled"):
                return ex
        await asyncio.sleep(0.1)
    raise AssertionError(f"execution {execution_id} not final in {timeout_s}s")


async def test_server_chain_trailing_logs_flushed_before_terminal(
        client, monkeypatch):
    """run 结束后管道滞留的尾行必须在终态前入库,ingest_stats 严格对账。

    修复前(先 finalize 后关池):trailing-after-run 只进已停 ingester 的
    缓冲,DB 无此行,而 logs_ingested=2 —— 本断言两处都炸。
    """
    from app.schemas.scenario_composer import RunRequest
    from app.services import gimbal_server_session
    from app.services import plate_client as pc

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(gimbal_server_session, "ServerSessionPool",
                        _TrailingLogPool)

    h = await register_and_login(client, "trail1", "pw123456")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-trail", steps=_STEPS, vars_map={"a": "1"},
        description="trail", author="t", owner="trail1", tags=[],
        version="1", createTime="2026-10-13T00:00:00Z", expire=False,
        requirementRef=[],
    ))
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/scenarios/sc-trail/data-sets", headers=h,
                          json={"name": "ds", "rows": [{"a": "1"}]})
    assert r.status_code in (200, 201), r.text
    ds_id = r.json()["datasetId"]

    req = RunRequest(scenarioId="sc-trail", dataSetIds=[ds_id])
    async with db_module.SessionLocal() as db:
        user = (await db.execute(
            sa.select(User).where(User.username == "trail1"))).scalar_one()
        resp = await run_dispatcher.dispatch_run(
            db, user.id, req, chain_override="server")
        await db.commit()

    ex = await _wait_final(resp.execution_id)
    assert ex.status == "done", ex.status
    assert ex.passed == 1 and ex.failed == 0

    # 终态可见时,尾部行必须已在库里(终态写在 finalize 之后,机制保证)
    async with db_module.SessionLocal() as s:
        msgs = (await s.execute(
            sa.select(ExecutionEvent.message).where(
                ExecutionEvent.execution_id == resp.execution_id,
                ExecutionEvent.kind == "log")
            .order_by(ExecutionEvent.id))).scalars().all()
        ex_row = await s.get(Execution, resp.execution_id)
    assert "mid-run-line" in msgs, f"运行中日志行丢失: {msgs}"
    assert "trailing-after-run" in msgs, (
        f"管道滞留尾行未入库(close 晚于 finalize): {msgs}")
    # S9 对账:快照计数与实际入库行数严格一致
    stats = (ex_row.config_json or {}).get("ingest_stats") or {}
    assert stats.get("logs_ingested") == len(msgs) == 2, (stats, msgs)
    assert stats.get("logs_dropped_unparsable") == 0
    assert stats.get("logs_below_level") == 0


async def test_gather_exception_still_closes_pump_and_finalizes(
        client, monkeypatch):
    """gather 抛出未捕获异常 → 关池排空泵 + finalize 冲刷后再放行异常。

    修复前此路径只走 _teardown:teardown 的 close 把尾行送进**无人冲刷**
    的 ingester 缓冲(静默丢失),ticker 任务泄漏。终态不在此处写 ——
    worker 的 finalize_execution_if_stuck 兜(异常)/租约回收重跑(取消)。
    直调 _fanout(compose 打爆模拟行任务外的意外异常),断言紧随异常
    立即查库 —— 赶在 ticker 的 0.5s 首拍之前,修复前必为 0 行。
    """
    import pytest

    from app.services import gimbal_server_session
    from app.services import plate_client as pc
    from app.services import run_dispatcher as rd

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    def _boom(scenario_payload, row_dict):
        raise RuntimeError("compose-boom")

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(gimbal_server_session, "ServerSessionPool",
                        _TrailingLogPool)
    monkeypatch.setattr(rd, "_compose_scenario", _boom)

    h = await register_and_login(client, "trail2", "pw123456")
    async with db_module.SessionLocal() as s:
        user = (await s.execute(
            sa.select(User).where(User.username == "trail2"))).scalar_one()
        ex = Execution(scenario_id="sc-trail2", owner_id=user.id,
                       status="running", total_runs=1, scenario_name="t")
        s.add(ex)
        await s.commit()
        eid = ex.id

    with pytest.raises(RuntimeError, match="compose-boom"):
        await rd._fanout(
            db_factory=db_module.SessionLocal, execution_id=eid,
            run_id="run-trail2",
            scenario_payload={"scenarioId": "sc-trail2", "definition": {}},
            datasets=[{"datasetId": None, "rows": [(0, {})]}],
            injections=[None], owner_id=user.id, auth_aliases=[],
            chain="server")

    # 异常路径的 close(吐尾行+EOF)→ finalize 冲刷:紧随异常查库,
    # 行已在、对账一致(ticker 0.5s 首拍前,修复前此处必为空)
    async with db_module.SessionLocal() as s:
        msgs = (await s.execute(
            sa.select(ExecutionEvent.message).where(
                ExecutionEvent.execution_id == eid,
                ExecutionEvent.kind == "log"))).scalars().all()
        ex_row = await s.get(Execution, eid)
    assert msgs == ["trailing-after-run"], msgs
    stats = (ex_row.config_json or {}).get("ingest_stats") or {}
    assert stats.get("logs_ingested") == 1, stats
    # teardown 照常收尾:行状态注册表已注销
    assert eid not in rd._row_states
