"""P2 案卷生命周期:删除执行清 case 目录;启动清扫过期目录。"""
import os
import time


# ─── 测试基座(同 test_run_baseline:mock launch/convert 走 /api/runs 全链)──
async def _fake_launch(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None):
    from tests.helpers import launch_ok

    return launch_ok()


async def _fake_convert(scenario):
    return {"consumer": "platform", "converted": dict(scenario)}


async def _wait_terminal(execution_id: int, timeout_s: float = 5.0) -> str:
    """轮询 Execution 至终态(done/failed/canceled)后返回 status。"""
    import asyncio

    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models.execution import Execution

    for _ in range(int(timeout_s / 0.05)):
        async with db_module.SessionLocal() as s:
            status = (await s.execute(
                sa.select(Execution.status).where(Execution.id == execution_id)
            )).scalar_one_or_none()
        if status in ("done", "failed", "canceled"):
            return status
        await asyncio.sleep(0.05)
    raise TimeoutError(f"execution {execution_id} not terminal in {timeout_s}s")


def _make_case_dir(run_dispatcher, run_id: str, age_days: float = 0):
    d = run_dispatcher._run_dir(run_id) / "case-001-baseline-r0-n0"
    d.mkdir(parents=True, exist_ok=True)
    (d / "case.json").write_text("{}", encoding="utf-8")
    if age_days:
        stamp = time.time() - age_days * 86400
        os.utime(d.parent, (stamp, stamp))
        os.utime(d, (stamp, stamp))
    return d


async def test_delete_execution_purges_case_dir(client, monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher
    from tests.helpers import make_draft, register_and_login, test_env

    # DATA_DIR 指到 tmp:case 目录/JSONL 全落在临时域,不污染真实 data/。
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-purge"))
    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-purge", "dataSetIds": [], "env": test_env(),
    })
    assert r.status_code == 201, r.text
    run_id, eid = r.json()["runId"], r.json()["executionId"]
    await _wait_terminal(eid)
    assert run_dispatcher._run_dir(run_id).exists()

    r = await client.delete(f"/api/executions/{eid}", headers=headers)
    assert r.status_code == 204
    assert not run_dispatcher._run_dir(run_id).exists()
    # JSONL 按日期分文件,设计上不随删
    assert run_dispatcher._jsonl_path().exists()


def test_sweep_removes_old_dirs_only(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services import run_dispatcher

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    _make_case_dir(run_dispatcher, "old-run", age_days=30)
    _make_case_dir(run_dispatcher, "new-run", age_days=0)
    removed = run_dispatcher.sweep_stale_case_dirs()
    assert removed == 1
    assert not (tmp_path / "runs" / "cases" / "old-run").exists()
    assert (tmp_path / "runs" / "cases" / "new-run").exists()


def test_sweep_disabled_when_zero(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services import run_dispatcher

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "CASE_RETENTION_DAYS", 0)
    _make_case_dir(run_dispatcher, "old-run", age_days=365)
    assert run_dispatcher.sweep_stale_case_dirs() == 0
    assert (tmp_path / "runs" / "cases" / "old-run").exists()
