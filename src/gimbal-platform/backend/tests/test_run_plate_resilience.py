"""P6:convert 按输入 memo;plate 连续不可用开路。"""
import asyncio
import json

from tests.helpers import make_draft, register_and_login, test_env


# ─── 测试基座(同 test_run_cancel / test_run_log_integrity)──
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
                       cwd=None, timeout=None):
    from tests.helpers import launch_ok
    return launch_ok()


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


async def _run_with_convert(client, monkeypatch, convert, *, body_over=None):
    from app.services import gimbal_launcher as gl, plate_client as pc

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-plate", vars_map={"customer_id": "1"}))
    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", convert)
    body = {"scenarioId": "sc-plate", "dataSetIds": [], "env": test_env()}
    body.update(body_over or {})
    r = await client.post("/api/runs", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()["executionId"]


async def test_convert_memoized_across_repeats(client, monkeypatch):
    from app.services import plate_client as pc  # noqa: F401 — patched below

    calls = {"n": 0}

    async def counting_convert(scenario):
        calls["n"] += 1
        return {"consumer": "platform", "converted": dict(scenario)}

    eid = await _run_with_convert(client, monkeypatch, counting_convert,
                                  body_over={"nRuns": 3})
    await _wait_terminal(eid)
    assert calls["n"] == 1          # 同一行 ×3 重复共享一次 convert


async def test_memo_hit_injection_view_not_polluted(client, monkeypatch):
    """memo 命中必须给深拷贝:注入的原地修改不得泄漏进后续命中。

    默认 injectCredentials=false → exec_auths 为空 → _inject_exec_users
    原样返回同一引用,随后 _inject_* 系列就地修改 convert 输出。若
    memo 命中按引用共享缓存对象,rep 2/3 会看到 rep 1 留下的注入痕迹。
    """
    import copy

    from app.services import run_dispatcher

    calls = {"n": 0}
    snapshots: list[dict] = []

    async def passthrough_convert(scenario):
        calls["n"] += 1
        return {"consumer": "platform", "converted": dict(scenario)}

    def spying_inject_services(composed, env):
        # 记录进入注入时的深快照,并施加一次可观察的原地修改。
        snapshots.append(copy.deepcopy(composed))
        composed.setdefault("__pollution_marker", []).append(len(snapshots))

    monkeypatch.setattr(
        run_dispatcher, "_inject_services", spying_inject_services
    )

    eid = await _run_with_convert(client, monkeypatch, passthrough_convert,
                                  body_over={"nRuns": 3})
    await _wait_terminal(eid)

    assert calls["n"] == 1          # 前提:rep 2/3 确实命中 memo
    assert len(snapshots) == 3
    assert snapshots[1] == snapshots[0], (
        f"rep 2 携带 rep 1 的注入痕迹: {snapshots[1]}"
    )
    assert snapshots[2] == snapshots[0], (
        f"rep 3 携带前次注入痕迹: {snapshots[2]}"
    )


async def test_breaker_opens_after_consecutive_unavailable(
    client, monkeypatch
):
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher
    from tests.helpers import register_and_login  # noqa: F401

    headers = await register_and_login(client)  # noqa: F841 — 复用登录态
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-plate", vars_map={"customer_id": "1"}))
    # 5 行数据集,行值互不相同(防 memo 干扰熔断计数路径)
    r = await client.post("/api/scenarios/sc-plate/data-sets", headers=headers,
                          json={"name": "ds5", "rows": [
                              {"customer_id": str(i)} for i in range(5)]})
    assert r.status_code == 201, r.text
    ds_id = r.json()["datasetId"]

    calls = {"n": 0}

    async def down_convert(scenario):
        calls["n"] += 1
        raise pc.PlateUnavailableError("plate_unavailable: connect timeout")

    async def noop_launch(*a, **k):
        from tests.helpers import launch_ok
        return launch_ok()

    monkeypatch.setattr(gl, "launch", noop_launch)
    monkeypatch.setattr(pc, "convert", down_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-plate", "dataSetIds": [ds_id], "env": test_env(),
        "parallel": 1,
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]
    await _wait_terminal(eid)

    assert calls["n"] == 3          # 阈值 3:第 4、5 行不再打 plate
    records = _jsonl_records(run_dispatcher)
    assert any(
        rec.get("status") == "plate_unavailable"
        and "circuit open" in str(rec.get("error", ""))
        for rec in records
    )
