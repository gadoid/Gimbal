"""P4 协作式取消:行边界生效、canceled 终态、终态单 409。
running 状态:fanout 行分发前置 running(+started_at),终态覆盖。"""
import asyncio
import json

from tests.helpers import (
    launch_ok as _ok,
    make_draft,
    register_and_login,
    wait_until,
)


# ─── 测试基座(同 test_run_log_integrity / test_run_case_retention)──
async def _seed_execution(
    owner_id: int, *, status: str, total_runs: int = 1,
    passed: int = 0, failed: int = 0, config: dict | None = None,
) -> int:
    """Insert one Execution row; return its id."""
    from app.core import db as db_module
    from app.models.execution import Execution

    async with db_module.SessionLocal() as session:
        ex = Execution(
            scenario_id="sc-cancel",
            owner_id=owner_id,
            status=status,
            total_runs=total_runs,
            passed=passed,
            failed=failed,
            config_json=config or {},
        )
        session.add(ex)
        await session.commit()
        return ex.id


async def _get_execution(execution_id: int):
    from sqlalchemy import select

    from app.core import db as db_module
    from app.models.execution import Execution

    async with db_module.SessionLocal() as session:
        return (
            await session.execute(
                select(Execution).where(Execution.id == execution_id)
            )
        ).scalar_one()


async def _wait_terminal(execution_id: int, timeout_s: float = 5.0):
    """轮询 Execution 至终态(done/failed/canceled)后返回该行。"""
    for _ in range(int(timeout_s / 0.05)):
        row = await _get_execution(execution_id)
        if row.status in ("done", "failed", "canceled"):
            return row
        await asyncio.sleep(0.05)
    raise TimeoutError(f"execution {execution_id} not terminal in {timeout_s}s")


async def _fake_launch(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None,
                       on_event=None, on_log=None, log_counters=None,
                       n_runs=1, retry=0):
    return _ok()


async def _fake_convert(scenario):
    return {"consumer": "platform", "converted": dict(scenario)}


def _jsonl_records(run_dispatcher) -> list:
    """读当日调度日志(JSONL)的全部记录。"""
    path = run_dispatcher._jsonl_path()
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def test_cancel_skips_remaining_rows(client, monkeypatch):
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-cancel", vars_map={"customer_id": "1"}))
    r = await client.post("/api/scenarios/sc-cancel/data-sets", headers=headers,
                          json={"name": "ds", "rows": [
                              {"customer_id": str(i)} for i in range(6)]})
    ds_id = r.json()["datasetId"]

    done = {"n": 0}

    async def _slow_launch(*a, **k):
        await asyncio.sleep(0.02)
        done["n"] += 1
        return _ok()

    monkeypatch.setattr(gl, "launch", _slow_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-cancel", "dataSetIds": [ds_id],
        "runOptions": {"parallel": 1},
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]

    await wait_until(lambda: done["n"] >= 1)     # 至少一行落地后取消
    cr = await client.post(f"/api/executions/{eid}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text

    row = await _wait_terminal(eid)
    assert row.status == "canceled"
    assert row.passed + row.failed < row.total_runs   # 有行被跳过
    # M6(27b6431d)行级 JSONL 停写:取消的权威落点 = execution_rows 行终态
    # (上行断言);JSONL 只保留运行级生命周期行,不再断言行级 canceled 记录。


async def test_cancel_terminal_conflicts(client, monkeypatch):
    from app.services import gimbal_launcher as gl, plate_client as pc

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-cancel-done"))
    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)
    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-cancel-done", "dataSetIds": [],
    })
    eid = r.json()["executionId"]
    await _wait_terminal(eid)

    cr = await client.post(f"/api/executions/{eid}/cancel", headers=headers)
    assert cr.status_code == 409, cr.text
    assert cr.json()["detail"]["code"] == "not_cancelable"


async def test_cancel_zombie_finalizes_immediately(client):
    from app.services import run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    me = (await client.get("/api/auth/me", headers=headers)).json()
    eid = await _seed_execution(me["user"]["id"], status="queued")  # MeOut 信封

    cr = await client.post(f"/api/executions/{eid}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text
    assert cr.json()["status"] == "canceled"


async def test_cancel_running_zombie_finalizes_immediately(client):
    """running 单可取消:无 live fanout 的 running = 重启僵尸,inline 终态化。

    (cancel 闸 = queued|running;done/failed/canceled 仍 409。)
    """
    from app.services import run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    me = (await client.get("/api/auth/me", headers=headers)).json()
    eid = await _seed_execution(me["user"]["id"], status="running")

    cr = await client.post(f"/api/executions/{eid}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text
    assert cr.json()["status"] == "canceled"


async def _seed_job(execution_id: int, *, kind: str, status: str,
                    chain: str = "legacy", unit_cancel: bool | None = None) -> None:
    """挂一行 execution_jobs(不经 dispatch,无 worker 认领)。

    ``unit_cancel``:spawn 期探测落库的单元级取消能力位(None = 未探测,
    即物化窗口形态)。"""
    from app.core import db as db_module
    from app.models.execution import ExecutionJob

    payload = {"kind": kind, "chain": chain,
               "args": {"execution_id": execution_id}}
    if unit_cancel is not None:
        payload["unit_cancel"] = unit_cancel
    async with db_module.SessionLocal() as session:
        session.add(ExecutionJob(
            execution_id=execution_id, kind=kind, status=status,
            payload=payload))
        await session.commit()


async def test_cancel_running_graph_conflicts_and_cancelable_flag(client):
    """全量评估 2026-11-02 #1 + 单元级取消方案 P3:**legacy 链**已认领(job
    running)的 graph 不消费取消位 → 409 not_cancelable、状态不动,列表/详情
    cancelable=false —— 不看执行状态(执行仍 queued 的物化窗口同样 409);
    job 仍 queued 的 graph 照常可取消(启动前检查有效);running 的 cases 链
    仍可取消;server 链 graph 已认领也可取消(取消中:cancel_requested)。"""
    from app.services import run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    me = (await client.get("/api/auth/me", headers=headers)).json()
    uid = me["user"]["id"]

    running_graph = await _seed_execution(uid, status="running")
    await _seed_job(running_graph, kind="graph", status="running")
    queued_graph = await _seed_execution(uid, status="queued")
    await _seed_job(queued_graph, kind="graph", status="queued")
    running_cases = await _seed_execution(uid, status="running")
    await _seed_job(running_cases, kind="cases", status="running")
    # 核验补充:graph job 已认领、执行仍 queued(物化窗口)→ 同样不可取消
    claimed_graph = await _seed_execution(uid, status="queued")
    await _seed_job(claimed_graph, kind="graph", status="running")

    async def flag(eid: int) -> bool:
        r = await client.get(f"/api/executions/{eid}", headers=headers)
        assert r.status_code == 200, r.text
        return r.json()["cancelable"]

    assert await flag(running_graph) is False
    assert await flag(queued_graph) is True
    assert await flag(running_cases) is True
    assert await flag(claimed_graph) is False
    lst = (await client.get("/api/executions", headers=headers)).json()["items"]
    flags = {i["id"]: i["cancelable"] for i in lst}
    assert flags[running_graph] is False and flags[claimed_graph] is False
    assert flags[queued_graph] is True and flags[running_cases] is True

    cr = await client.post(f"/api/executions/{claimed_graph}/cancel", headers=headers)
    assert cr.status_code == 409, cr.text
    assert cr.json()["detail"]["code"] == "not_cancelable"
    assert (await _get_execution(claimed_graph)).status == "queued"

    cr = await client.post(f"/api/executions/{running_graph}/cancel", headers=headers)
    assert cr.status_code == 409, cr.text
    assert cr.json()["detail"]["code"] == "not_cancelable"
    assert (await _get_execution(running_graph)).status == "running"

    cr = await client.post(f"/api/executions/{queued_graph}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text   # 位已写,worker 启动前消费
    assert cr.json()["cancel_requested"] is True and cr.json()["cancelable"] is False

    # 单元级取消方案 P3:server 链 graph 已认领仍可取消(执行器 scope=unit)
    server_graph = await _seed_execution(uid, status="running")
    await _seed_job(server_graph, kind="graph", status="running", chain="server")
    assert await flag(server_graph) is True
    cr = await client.post(f"/api/executions/{server_graph}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text
    assert cr.json()["cancel_requested"] is True
    d = (await client.get(f"/api/executions/{server_graph}", headers=headers)).json()
    assert d["status"] == "running"          # 等在飞单元跑完才收口
    assert d["cancel_requested"] is True and d["cancelable"] is False


async def test_cancel_capability_gate_unit_cancel_flag(client):
    """能力位判定(§6「可」项 + legacy 通道):server 链 unit_cancel=False
    (healthz 空能力的旧执行器)→ 409 + 文案点明执行器版本、cancelable 投影
    False;legacy 链 unit_cancel=True(--cancel-file 通道)→ 200 可取消。"""
    from app.services import run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    me = (await client.get("/api/auth/me", headers=headers)).json()
    uid = me["user"]["id"]

    server_old = await _seed_execution(uid, status="running")
    await _seed_job(server_old, kind="graph", status="running",
                    chain="server", unit_cancel=False)
    legacy_new = await _seed_execution(uid, status="running")
    await _seed_job(legacy_new, kind="graph", status="running",
                    chain="legacy", unit_cancel=True)

    async def flag(eid: int) -> bool:
        return (await client.get(f"/api/executions/{eid}", headers=headers)
                ).json()["cancelable"]

    assert await flag(server_old) is False
    assert await flag(legacy_new) is True
    lst = (await client.get("/api/executions", headers=headers)).json()["items"]
    flags = {i["id"]: i["cancelable"] for i in lst}
    assert flags[server_old] is False and flags[legacy_new] is True

    cr = await client.post(f"/api/executions/{server_old}/cancel", headers=headers)
    assert cr.status_code == 409, cr.text
    assert cr.json()["detail"]["code"] == "not_cancelable"
    assert "执行器版本过低" in cr.json()["detail"]["message"]

    cr = await client.post(f"/api/executions/{legacy_new}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text
    assert cr.json()["cancel_requested"] is True


def test_graph_unit_cancelable_defaults():
    """能力位缺失(未探测)的缺省口径:server 链 = 物化窗口(取消走启动前
    检查、不下发执行器)→ 可取消;legacy 链 = 旧引擎/未探测 → 不可取消。"""
    from app.services.execution_store import _graph_unit_cancelable

    assert _graph_unit_cancelable({"chain": "server"}) is True
    assert _graph_unit_cancelable({}) is False                 # legacy 缺省
    assert _graph_unit_cancelable({"chain": "legacy"}) is False
    assert _graph_unit_cancelable({"chain": "server", "unit_cancel": False}) is False
    assert _graph_unit_cancelable({"chain": "legacy", "unit_cancel": True}) is True


async def test_cancel_note_follows_job_form_and_ignored(client):
    """取消说明文案(前端 toast/徽标 title/告警条原样显示)由服务端给:
    取消中按**任务体** kind 区分等待面(graph 等在飞单元 / cases 等当前行)——
    POST /api/runs 带 graph 的执行 kind 仍是 scenario,按 Execution.kind 自推
    必错;终态 config.cancelIgnored 单在详情/列表解释为何按真实结果收口。"""
    from app.services import run_dispatcher
    from app.services.execution_store import (
        CANCEL_NOTE_CASES,
        CANCEL_NOTE_GRAPH,
        CANCEL_NOTE_IGNORED,
    )

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    me = (await client.get("/api/auth/me", headers=headers)).json()
    uid = me["user"]["id"]

    plain = await _seed_execution(uid, status="running")     # 未请求取消:无说明
    await _seed_job(plain, kind="cases", status="running")
    ignored = await _seed_execution(
        uid, status="done", passed=1,
        config={"cancelIgnored": "all units already started"})
    done_plain = await _seed_execution(uid, status="done", passed=1)

    async def detail_note(eid: int):
        return (await client.get(f"/api/executions/{eid}", headers=headers)
                ).json()["cancel_note"]

    async def list_note(eid: int):
        lst = (await client.get("/api/executions", headers=headers)).json()["items"]
        return next(i["cancel_note"] for i in lst if i["id"] == eid)

    assert await detail_note(plain) is None
    assert await detail_note(done_plain) is None
    assert await detail_note(ignored) == CANCEL_NOTE_IGNORED
    assert await list_note(ignored) == CANCEL_NOTE_IGNORED

    # cases 链在飞:取消 → 当前行口径(取消响应与详情/列表投影一致)
    cr = await client.post(f"/api/executions/{plain}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text
    assert cr.json()["cancel_note"] == CANCEL_NOTE_CASES
    assert await detail_note(plain) == CANCEL_NOTE_CASES
    assert await list_note(plain) == CANCEL_NOTE_CASES

    # graph(server 链)在飞:执行 kind 仍是 scenario —— 文案必须按任务体给
    graph = await _seed_execution(uid, status="running")
    await _seed_job(graph, kind="graph", status="running", chain="server")
    cr = await client.post(f"/api/executions/{graph}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text
    assert cr.json()["kind"] == "scenario"
    assert cr.json()["cancel_note"] == CANCEL_NOTE_GRAPH
    assert await detail_note(graph) == CANCEL_NOTE_GRAPH
    assert await list_note(graph) == CANCEL_NOTE_GRAPH


async def test_fanout_marks_running(client, monkeypatch):
    """认证解析通过、行分发开始前 → status=running + started_at 落定;
    终态(done)覆盖 running。"""
    import asyncio

    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-running"))

    gate = asyncio.Event()
    entered = {"n": 0}

    async def _gated_launch(*a, **k):
        entered["n"] += 1         # launch 被调 ⇒ _mark_running 已提交
        await gate.wait()          # 卡住首行,让 running 窗口可观测
        return _ok()

    monkeypatch.setattr(gl, "launch", _gated_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-running", "dataSetIds": [],
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]

    await wait_until(lambda: entered["n"] >= 1)
    row = await _get_execution(eid)
    assert row.status == "running"
    assert row.started_at is not None

    gate.set()                    # 放行 → 自然跑完
    row = await _wait_terminal(eid)
    assert row.status == "done"
