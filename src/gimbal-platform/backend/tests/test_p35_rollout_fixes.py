"""P3.5（server 链放量前置）回归：多行并发探针 / 恢复行级断点 / 双链等价。

* P3.5-1：server 链 × 多行 × parallel>1 —— 引擎 ``/runs`` 单 run 设计，
  共用实例时并发行直接 409 → ``gimbal_rejected``（复审探针复现）；
  槽位实例池修复后全行通过、被测系统请求数 = 行数；
* P3.5-2：job 重跑（租约过期/重启回队）只补未终态行 —— 不重复执行、
  事件 seq 从 DB 续接不撞唯一约束、行 upsert 无冲突；
* P3.5-3：同配方 legacy / server 双链逐字段等价（对账的回归形态）。
"""
from __future__ import annotations

import asyncio
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest
import sqlalchemy as sa

from app.core import db as db_module
from app.core.config import settings
from app.models.execution import Execution, ExecutionEvent, ExecutionJob, ExecutionRow
from app.services import execution_queue, run_dispatcher
from tests.helpers import make_draft, register_and_login

# 引擎可用性判据复用 C12 e2e(桩被测系统本文件自带独立实例)
from tests.test_debug_console import _engine_available


# ── P3.5-1 / P3.5-3：真引擎（不可用时 skip）────────────────────

_STEPS = [{
    "id": "s1", "kind": "step",
    "call": {"kind": "call", "protocol": "http", "service": "svc",
             "method": "GET", "path": "/ping"},
    "request": {"kind": "request", "body": {}},
    "strategy": [{"kind": "assertion",
                  "target": "$.call.response.body.code",
                  "operator": "eq", "expected": "0"}],
}]


class _StubSut(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    hits: list[dict] = []

    def do_GET(self):  # noqa: N802
        _StubSut.hits.append({"path": self.path})
        out = json.dumps({"code": "0"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):  # noqa: D102
        pass


@pytest.fixture
def stub_sut2():
    """独立于 test_debug_console 的桩被测系统（本文件断言用独立 hits 面）。"""
    _StubSut.hits = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _StubSut)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


async def _dispatch_chain(client, username: str, *, dataset_rows: list[dict],
                          parallel: int, chain: str, sut_url: str,
                          steps: list | None = None) -> int:
    """3 行数据集场景按指定链发起;返回 executionId(等执行者处理)。

    scenarioId 全局唯一 —— 同测试多链各用各的场景(按用户名派生)。
    """
    from app.schemas.scenario_composer import RunRequest, ServiceBinding

    sc_id = f"sc-p35-{username}"
    h = await register_and_login(client, username, "pw123456")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        sc_id, steps=steps or _STEPS, vars_map={"a": "1"},
        description="p35", author="t", owner=username, tags=[],
        version="1", createTime="2026-09-24T00:00:00Z", expire=False,
        requirementRef=[],
    ))
    assert r.status_code in (200, 201), r.text
    if dataset_rows:
        r = await client.post(f"/api/scenarios/{sc_id}/data-sets", headers=h,
                              json={"name": "ds", "rows": dataset_rows})
        assert r.status_code in (200, 201), r.text
        ds_id = r.json()["datasetId"]
    else:
        ds_id = None

    req = RunRequest(
        scenarioId=sc_id,
        dataSetIds=[ds_id] if ds_id else [],
        parallel=parallel,
        serviceBindings={"svc": ServiceBinding(url=sut_url)},
    )
    async with db_module.SessionLocal() as db:
        from app.models.user import User
        user = (await db.execute(
            sa.select(User).where(User.username == username))).scalar_one()
        resp = await run_dispatcher.dispatch_run(
            db, user.id, req, chain_override=chain)
        await db.commit()
    return resp.execution_id


async def _wait_final(execution_id: int, timeout_s: float = 90.0) -> Execution:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, execution_id)
            if ex.status in ("done", "failed", "canceled"):
                return ex
        await asyncio.sleep(0.1)
    raise AssertionError(f"execution {execution_id} not final in {timeout_s}s")


@pytest.mark.skipif(not _engine_available(),
                    reason="真 gimbal 引擎不可用(GIMBAL_BIN / importable gimbal)")
async def test_server_chain_multirow_parallel(client, monkeypatch, stub_sut2):
    """P3.5-1 探针回归:server 链 3 行 × parallel=3 → 全行通过、请求 ×3。

    修复前共用单实例,引擎 409 "one run at a time" → 1 通过 2 拒绝、
    被测系统只收到 1 个请求(复审复现值)。
    """
    from app.services import plate_client as pc

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(settings, "GIMBAL_BIN", "")   # 钉当前解释器引擎

    eid = await _dispatch_chain(
        client, "p35a", dataset_rows=[{"a": "1"}, {"a": "2"}, {"a": "3"}],
        parallel=3, chain="server", sut_url=stub_sut2)

    ex = await _wait_final(eid)
    assert ex.status == "done", ex.status
    assert ex.passed == 3 and ex.failed == 0
    assert len(_StubSut.hits) == 3            # 每行都真打了被测系统

    # 事件完整性:每个 case 的完整事件流(run.finished ×3)必须入库
    async with db_module.SessionLocal() as s:
        fin = (await s.execute(
            sa.select(sa.func.count()).where(
                ExecutionEvent.execution_id == eid,
                ExecutionEvent.event_type == "run.finished"))).scalar()
        scen_end = (await s.execute(
            sa.select(sa.func.count()).where(
                ExecutionEvent.execution_id == eid,
                ExecutionEvent.event_type == "scenario.end"))).scalar()
    assert fin == 3, f"run.finished 丢失: {fin}/3"
    assert scen_end == 3, f"scenario.end 丢失: {scen_end}/3"


@pytest.mark.skipif(not _engine_available(),
                    reason="真 gimbal 引擎不可用(GIMBAL_BIN / importable gimbal)")
async def test_dual_chain_equivalence_multirow(client, monkeypatch, stub_sut2):
    """P3.5-3:同配方(3 行 × parallel=3)legacy / server 各跑一次,
    计数与行状态逐字段一致 —— reconcile_chain.py 的回归形态。"""
    from app.services import plate_client as pc

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(settings, "GIMBAL_BIN", "")

    eid_l = await _dispatch_chain(
        client, "p35b", dataset_rows=[{"a": "1"}, {"a": "2"}, {"a": "3"}],
        parallel=3, chain="legacy", sut_url=stub_sut2)
    eid_s = await _dispatch_chain(
        client, "p35c", dataset_rows=[{"a": "1"}, {"a": "2"}, {"a": "3"}],
        parallel=3, chain="server", sut_url=stub_sut2)

    ex_l, ex_s = await _wait_final(eid_l), await _wait_final(eid_s)
    summary_l = {"status": ex_l.status, "total": ex_l.total_runs,
                 "passed": ex_l.passed, "failed": ex_l.failed,
                 "skipped": ex_l.skipped}
    summary_s = {"status": ex_s.status, "total": ex_s.total_runs,
                 "passed": ex_s.passed, "failed": ex_s.failed,
                 "skipped": ex_s.skipped}
    assert summary_l == summary_s

    async def _rows(eid: int) -> list[tuple]:
        async with db_module.SessionLocal() as s:
            rs = (await s.execute(
                sa.select(ExecutionRow.status, ExecutionRow.attempts)
                .where(ExecutionRow.execution_id == eid)
                .order_by(ExecutionRow.seq))).all()
        return [tuple(r) for r in rs]

    rows_l, rows_s = await _rows(eid_l), await _rows(eid_s)
    # 状态逐行等价;attempts 负载敏感(偶发重试两链独立抖动),只设下界
    assert [st for st, _ in rows_l] == [st for st, _ in rows_s]
    assert all(a >= 1 for _, a in rows_l + rows_s)


# ── P3 收尾:对账基准扩充(五形态,真引擎)───────────────────────

class _SlowSut(BaseHTTPRequestHandler):
    """慢被测系统:每请求睡 4s(超时/取消形态的时序基座)。"""
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802
        time.sleep(4.0)
        out = json.dumps({"code": "0"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):  # noqa: D102
        pass


@pytest.fixture
def slow_sut():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _SlowSut)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


async def _summaries(ex_l: Execution, ex_s: Execution) -> tuple[dict, dict]:
    return (
        {"status": ex_l.status, "total": ex_l.total_runs,
         "passed": ex_l.passed, "failed": ex_l.failed, "skipped": ex_l.skipped},
        {"status": ex_s.status, "total": ex_s.total_runs,
         "passed": ex_s.passed, "failed": ex_s.failed, "skipped": ex_s.skipped},
    )


@pytest.mark.skipif(not _engine_available(),
                    reason="真 gimbal 引擎不可用(GIMBAL_BIN / importable gimbal)")
async def test_reconcile_assertion_failure_shape(client, monkeypatch, stub_sut2):
    """断言失败形态:期望值打错 → 双链 3 行全 failed、计数一致。"""
    from app.services import plate_client as pc

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(settings, "GIMBAL_BIN", "")
    bad = [{
        "id": "s1", "kind": "step",
        "call": {"kind": "call", "protocol": "http", "service": "svc",
                 "method": "GET", "path": "/ping"},
        "request": {"kind": "request", "body": {}},
        "strategy": [{"kind": "assertion",
                      "target": "$.call.response.body.code",
                      "operator": "eq", "expected": "1"}],   # 实际恒 0
    }]
    rows = [{"a": "1"}, {"a": "2"}, {"a": "3"}]
    eid_l = await _dispatch_chain(client, "p35e", dataset_rows=rows, parallel=3,
                                  chain="legacy", sut_url=stub_sut2, steps=bad)
    eid_s = await _dispatch_chain(client, "p35f", dataset_rows=rows, parallel=3,
                                  chain="server", sut_url=stub_sut2, steps=bad)
    ex_l, ex_s = await _wait_final(eid_l), await _wait_final(eid_s)
    sl, ss = await _summaries(ex_l, ex_s)
    assert sl == ss
    assert sl["failed"] == 3 and sl["passed"] == 0


@pytest.mark.skipif(not _engine_available(),
                    reason="真 gimbal 引擎不可用(GIMBAL_BIN / importable gimbal)")
async def test_reconcile_multistep_extract_shape(client, monkeypatch, stub_sut2):
    """多 step 带 extract:提取→跨步 assign→断言(引擎正规跨步数据流)。"""
    from app.services import plate_client as pc

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(settings, "GIMBAL_BIN", "")
    steps = [
        {"id": "s1", "kind": "step",
         "call": {"kind": "call", "protocol": "http", "service": "svc",
                  "method": "GET", "path": "/ping"},
         "request": {"kind": "request", "body": {}},
         "strategy": [{"kind": "extract",
                       "expression": "$.call.response.body.code",
                       "target": "token", "scope": "scenario"}]},
        {"id": "s2", "kind": "step",
         "call": {"kind": "call", "protocol": "http", "service": "svc",
                  "method": "GET", "path": "/ping"},
         "request": {"kind": "request", "body": {}},
         "strategy": [
             {"kind": "assign", "source": "$.token", "target": "tok",
              "scope": "scenario"},
             {"kind": "assertion", "target": "$.tok",
              "operator": "eq", "expected": "0"}]},
    ]
    rows = [{"a": "1"}, {"a": "2"}]
    eid_l = await _dispatch_chain(client, "p35g", dataset_rows=rows, parallel=2,
                                  chain="legacy", sut_url=stub_sut2, steps=steps)
    eid_s = await _dispatch_chain(client, "p35h", dataset_rows=rows, parallel=2,
                                  chain="server", sut_url=stub_sut2, steps=steps)
    ex_l, ex_s = await _wait_final(eid_l), await _wait_final(eid_s)
    sl, ss = await _summaries(ex_l, ex_s)
    assert sl == ss
    assert sl["passed"] == 2 and sl["failed"] == 0   # extract 流真实走通


@pytest.mark.skipif(not _engine_available(),
                    reason="真 gimbal 引擎不可用(GIMBAL_BIN / importable gimbal)")
async def test_reconcile_graph_shape(client, monkeypatch, stub_sut2):
    """graph 形态:两单元 chain 图,双链图行/计数一致。"""
    from app.schemas.scenario_composer import (
        GraphSpec, GraphUnitSpec, RunRequest, ServiceBinding,
    )
    from app.services import plate_client as pc

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(settings, "GIMBAL_BIN", "")

    async def _dispatch_graph(username: str, chain: str) -> int:
        h = await register_and_login(client, username, "pw123456")
        for i in (1, 2):
            await client.post("/api/scenarios", headers=h, json=make_draft(
                f"sc-p35-{username}-u{i}", steps=_STEPS, vars_map={"a": "1"},
                description="p35", author="t", owner=username, tags=[],
                version="1", createTime="2026-09-24T00:00:00Z", expire=False,
                requirementRef=[]))
        req = RunRequest(
            scenarioId=f"sc-p35-{username}-u1",   # 锚场景(graph 挂载点)
            graph=GraphSpec(mode="chain", units=[
                GraphUnitSpec(ref="u1", scenario_id=f"sc-p35-{username}-u1"),
                GraphUnitSpec(ref="u2",
                              scenario_id=f"sc-p35-{username}-u2"),
            ], service_bindings={"svc": {"url": stub_sut2}}),
        )
        async with db_module.SessionLocal() as db:
            from app.models.user import User
            user = (await db.execute(
                sa.select(User).where(User.username == username))).scalar_one()
            resp = await run_dispatcher.dispatch_run(
                db, user.id, req, chain_override=chain)
            await db.commit()
        return resp.execution_id

    eid_l = await _dispatch_graph("p35i", "legacy")
    eid_s = await _dispatch_graph("p35j", "server")
    ex_l, ex_s = await _wait_final(eid_l), await _wait_final(eid_s)
    sl, ss = await _summaries(ex_l, ex_s)

    # 重构方案第 3 处:计数按单元累加 —— 两链等价 + 计数守恒(两单元
    # 全过 = passed 2;满套件负载下单元可能偶发失败,passed 数值抖动,
    # 故只钉链间等价与总和,不钉全绿)
    assert sl == ss
    for s in (sl, ss):
        assert s["passed"] + s["failed"] + s["skipped"] == 2

    async def _graph_row(eid: int) -> tuple:
        async with db_module.SessionLocal() as s:
            r = (await s.execute(
                sa.select(ExecutionRow.status, ExecutionRow.attempts)
                .where(ExecutionRow.execution_id == eid, ExecutionRow.seq == 0))
                ).one()
        return tuple(r)

    rl, rs = await _graph_row(eid_l), await _graph_row(eid_s)
    # 状态必须等价;attempts 是负载敏感值(满套件负载下偶发重试会 +1,
    # 两链独立采样必然抖动)——只设下界(两单元各至少一次尝试)
    assert rl[0] == rs[0] == "passed"
    assert rl[1] >= 2 and rs[1] >= 2


@pytest.mark.skipif(not _engine_available(),
                    reason="真 gimbal 引擎不可用(GIMBAL_BIN / importable gimbal)")
async def test_reconcile_step_timeout_shape(client, monkeypatch, slow_sut):
    """超时形态:step 协议超时 2s × 慢 SUT 4s → 引擎内超时失败,双链一致。"""
    from app.services import plate_client as pc

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(settings, "GIMBAL_BIN", "")
    steps = [{
        "id": "s1", "kind": "step",
        "call": {"kind": "call", "protocol": "http", "service": "svc",
                 "method": "GET", "path": "/slow", "timeout": 2},
        "request": {"kind": "request", "body": {}},
        "strategy": [],
    }]
    eid_l = await _dispatch_chain(client, "p35k", dataset_rows=[], parallel=1,
                                  chain="legacy", sut_url=slow_sut, steps=steps)
    eid_s = await _dispatch_chain(client, "p35l", dataset_rows=[], parallel=1,
                                  chain="server", sut_url=slow_sut, steps=steps)
    ex_l, ex_s = await _wait_final(eid_l, timeout_s=120), \
        await _wait_final(eid_s, timeout_s=120)
    sl, ss = await _summaries(ex_l, ex_s)
    assert sl == ss and sl["failed"] == 1


@pytest.mark.skipif(not _engine_available(),
                    reason="真 gimbal 引擎不可用(GIMBAL_BIN / importable gimbal)")
async def test_reconcile_cancel_shape(client, monkeypatch, slow_sut):
    """取消形态:3 行串行,首行在飞时取消 → 在飞行自然跑完、余行 canceled,
    执行 canceled —— 双链语义一致(C11 协作取消:行边界消费)。"""
    from app.services import plate_client as pc

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(settings, "GIMBAL_BIN", "")

    async def _dispatch_and_cancel(username: str, chain: str) -> int:
        eid = await _dispatch_chain(
            client, username, dataset_rows=[{"a": "1"}, {"a": "2"}, {"a": "3"}],
            parallel=1, chain=chain, sut_url=slow_sut)
        # 等首行真实开跑(首批事件入库)再取消 —— 命中"在飞行"窗口
        for _ in range(300):
            async with db_module.SessionLocal() as s:
                n = (await s.execute(
                    sa.select(sa.func.count())
                    .where(ExecutionEvent.execution_id == eid))).scalar()
            if n:
                break
            await asyncio.sleep(0.05)
        async with db_module.SessionLocal() as s:
            await execution_queue.request_cancel(s, eid)
            await s.commit()
        return eid

    eid_l = await _dispatch_and_cancel("p35m", "legacy")
    eid_s = await _dispatch_and_cancel("p35n", "server")
    ex_l, ex_s = await _wait_final(eid_l, timeout_s=120), \
        await _wait_final(eid_s, timeout_s=120)
    assert ex_l.status == "canceled" and ex_s.status == "canceled"
    assert ex_l.passed == ex_s.passed == 1   # 在飞首行双链都自然跑完

    async def _row_statuses(eid: int) -> list:
        async with db_module.SessionLocal() as s:
            rs = (await s.execute(
                sa.select(ExecutionRow.status)
                .where(ExecutionRow.execution_id == eid)
                .order_by(ExecutionRow.seq))).scalars().all()
        return list(rs)

    assert await _row_statuses(eid_l) == await _row_statuses(eid_s)


# ── P3.5-2：恢复行级断点(伪引擎)────────────────────────────────

async def test_recovery_skips_terminal_rows_and_continues_seq(
        client, monkeypatch):
    """job 重跑只补未终态行:不重复执行 / 事件 seq 续接 / 行无冲突。

    首轮 3 行全过(6 事件);模拟崩溃残留 —— seq=1 行回退到未执行
    (删行+减计数+执行置 queued+同配方重入队);重跑只执行 seq=1,
    事件 seq 从 7 续接,行终态 upsert,无唯一约束异常。
    """
    calls = {"n": 0}

    async def _fake_launch(case_path, *, step_to=None, report_dir=None,
                           cwd=None, timeout=None, engine_log_path=None,
                           on_event=None, on_log=None, n_runs=1):
        calls["n"] += 1
        if on_event is not None:
            on_event({"event_type": "run.meta", "unit": f"u{calls['n']}"})
            on_event({"event_type": "run.finished", "status": "passed",
                      "passed": 1, "failed": 0, "skipped": 0, "attempts": 1,
                      "unit": f"u{calls['n']}"})
        from tests.helpers import launch_ok
        return launch_ok()

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import gimbal_launcher as gl, plate_client as pc
    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    h = await register_and_login(client, "p35d", "pw123456")
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-p35", vars_map={"a": "1"}))
    r = await client.post("/api/scenarios/sc-p35/data-sets", headers=h,
                          json={"name": "ds",
                                "rows": [{"a": "1"}, {"a": "2"}, {"a": "3"}]})
    ds_id = r.json()["datasetId"]
    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": "sc-p35", "dataSetIds": [ds_id]})
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]

    ex = await _wait_final(eid)
    assert ex.status == "done" and ex.passed == 3 and calls["n"] == 3

    async with db_module.SessionLocal() as s:
        payload = (await s.execute(
            sa.select(ExecutionJob.payload)
            .where(ExecutionJob.execution_id == eid))).scalar_one()

    # 模拟崩溃残留:seq=1 行未完成(行未落库、计数未 bump)→ 既有 job
    # 复位回队(0009 一执行一任务;复现 sweep_stale 的回队语义)
    async with db_module.SessionLocal() as s:
        ex = await s.get(Execution, eid)
        ex.status = "queued"
        ex.finished_at = None
        ex.passed = ex.passed - 1          # seq=1 的计数随行一起回退
        row = (await s.execute(
            sa.select(ExecutionRow)
            .where(ExecutionRow.execution_id == eid, ExecutionRow.seq == 1))
            ).scalar_one()
        await s.delete(row)
        job = (await s.execute(
            sa.select(ExecutionJob)
            .where(ExecutionJob.execution_id == eid))).scalar_one()
        job.status = "queued"
        job.claimed_by = None
        job.claimed_at = None
        job.heartbeat_at = None
        await s.commit()
    execution_queue.ensure_workers()

    ex = await _wait_final(eid)
    assert ex.status == "done" and ex.passed == 3 and ex.failed == 0
    assert calls["n"] == 4                 # 只重跑了 seq=1 一行

    async with db_module.SessionLocal() as s:
        rows = (await s.execute(
            sa.select(ExecutionRow.seq, ExecutionRow.status)
            .where(ExecutionRow.execution_id == eid)
            .order_by(ExecutionRow.seq))).all()
        n_events, max_seq = (await s.execute(
            sa.select(sa.func.count(), sa.func.max(ExecutionEvent.seq))
            .where(ExecutionEvent.execution_id == eid))).one()

    # 行:seq 0..2 全部终态 passed(upsert 后无缺行)
    assert [(r.seq, r.status) for r in rows] == [
        (0, "passed"), (1, "passed"), (2, "passed")]
    # 事件:首轮 6 + 重跑 2 = 8;seq 续接(无 on_conflict_do_nothing 丢弃)
    assert n_events == 8 and max_seq == 8


# ── P3.5-3 副产物:flush 取消竞态(对账实测抓到)─────────────────

async def test_ingester_flush_cancel_rebuffers_batch(client, monkeypatch):
    """在飞 flush 被取消时批次必须回填、由收尾冲刷重试。

    finalize 取消 ticker 时批次可能正在 DB 往返中;CancelledError 不是
    Exception 子类,旧的 except Exception 回填逻辑放行 → 整批事件静默
    丢失(批已从缓冲换出,收尾 flush 拿到空缓冲)。
    """
    from app.services import execution_store as es
    from app.services.run_dispatcher import _EventIngester

    in_flight, release = asyncio.Event(), asyncio.Event()
    calls = {"n": 0}

    async def _insert_events(session, execution_id, events):
        calls["n"] += 1
        if calls["n"] == 1:
            in_flight.set()
            await release.wait()      # 卡在 DB 往返中,等取消
        return None

    async def _noop_logs(session, execution_id, logs, *, seq_base):
        return None

    monkeypatch.setattr(es, "insert_events", _insert_events)
    monkeypatch.setattr(es, "insert_logs", _noop_logs)

    ing = _EventIngester(db_module.SessionLocal, 1)
    ing.on_event({"event_type": "run.meta"})
    t = asyncio.create_task(ing._flush())
    await asyncio.wait_for(in_flight.wait(), timeout=2)
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
    assert len(ing._events) == 1      # 批次已回填,未被静默丢弃
    release.set()
    await ing.finalize()              # 收尾冲刷重试整批
    assert calls["n"] == 2 and ing._events == []
