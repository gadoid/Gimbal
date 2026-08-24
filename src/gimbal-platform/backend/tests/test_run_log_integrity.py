"""P8/P9:JSONL 异步写 + 计数器重试与漂移校账。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from app.models.execution import Execution


# ─── 测试基座:直接造/读 Execution 行(不走 /api/runs 全链)────────
# ``db_module.SessionLocal`` 即满足 db_factory 契约(``async with
# factory() as session``);由 conftest 的 fresh_db fixture 换成每测库。
async def _seed_execution(
    owner_id: int, *, status: str, total_runs: int,
    passed: int = 0, failed: int = 0,
) -> int:
    """Insert one Execution row; return its id."""
    from app.core import db as db_module
    from app.models.execution import Execution

    async with db_module.SessionLocal() as session:
        ex = Execution(
            scenario_id="sc-integrity",
            owner_id=owner_id,
            status=status,
            total_runs=total_runs,
            passed=passed,
            failed=failed,
            config_json={},
        )
        session.add(ex)
        await session.commit()
        return ex.id


async def _get_execution(execution_id: int) -> "Execution":
    from app.core import db as db_module
    from app.models.execution import Execution

    async with db_module.SessionLocal() as session:
        return (
            await session.execute(
                select(Execution).where(Execution.id == execution_id)
            )
        ).scalar_one()


async def test_append_log_is_async_and_tolerates_failure(tmp_path, monkeypatch):
    from app.services import run_dispatcher

    written = []

    def fake_append(path, payload):
        written.append(payload)
        if payload.get("boom"):
            raise OSError("disk full")

    monkeypatch.setattr(run_dispatcher, "_append_jsonl", fake_append)
    await run_dispatcher._append_log(tmp_path / "a.jsonl", {"x": 1})
    await run_dispatcher._append_log(tmp_path / "a.jsonl", {"boom": 1})  # 不抛
    assert written[0] == {"x": 1}


async def test_bump_counters_retries_once(monkeypatch):
    from app.services import run_dispatcher

    factory_calls = {"n": 0}

    class FlakySession:
        def __init__(self):
            self.nth = 0

        async def __aenter__(self):
            factory_calls["n"] += 1
            self.nth = factory_calls["n"]
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, *a, **k):
            if self.nth == 1:
                raise OSError("db locked")
            return None

        async def commit(self):
            return None

    def factory():
        return FlakySession()

    await run_dispatcher._bump_counters(factory, 999, passed=0, failed=1)
    assert factory_calls["n"] == 2          # 第一次失败,重试一次


async def test_bump_counters_double_failure_logs_jsonl(monkeypatch, tmp_path):
    from app.services import run_dispatcher

    async def dead_factory():
        raise OSError("db gone")

    monkeypatch.setattr(run_dispatcher, "_jsonl_path", lambda: tmp_path / "r.jsonl")
    recorded = []

    async def fake_append(path, payload):
        recorded.append(payload)

    monkeypatch.setattr(run_dispatcher, "_append_log", fake_append)
    await run_dispatcher._bump_counters(dead_factory, 999, passed=1, failed=0)
    assert recorded and recorded[0]["status"] == "counter_bump_failed"


async def test_finalize_flags_counter_drift(fresh_db):
    from app.core import db as db_module
    from app.services import run_dispatcher

    eid = await _seed_execution(1, status="queued", total_runs=2,
                                passed=0, failed=0)
    await run_dispatcher._finalize_execution(db_module.SessionLocal, eid)
    row = await _get_execution(eid)
    assert row.status == "done"             # failed=0 → done
    assert row.config_json.get("counterDrift") is True   # 0+0 != 2


async def test_finalize_no_drift_when_consistent(fresh_db):
    from app.core import db as db_module
    from app.services import run_dispatcher

    eid = await _seed_execution(1, status="queued", total_runs=2,
                                passed=1, failed=1)
    await run_dispatcher._finalize_execution(db_module.SessionLocal, eid)
    row = await _get_execution(eid)
    # 严格规则 failed > 0 → failed(与 impl 及 test_run_partial_failure_
    # marks_execution_failed 一致;1+1=2 对账一致,本例只验无漂移标记)
    assert row.status == "failed"
    assert "counterDrift" not in (row.config_json or {})


async def test_dispatch_rejects_when_shutting_down(client, monkeypatch):
    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models.execution import Execution
    from app.services import run_dispatcher
    from tests.helpers import make_draft, register_and_login, test_env

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-shutdown"))

    run_dispatcher._shutting_down = True
    try:
        r = await client.post("/api/runs", headers=headers, json={
            "scenarioId": "sc-shutdown", "dataSetIds": [], "env": test_env(),
        })
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "shutting_down"
        async with db_module.SessionLocal() as s:
            n = (await s.execute(
                sa.select(sa.func.count()).select_from(Execution)
            )).scalar_one()
        assert n == 0                      # 不留 Execution 行
    finally:
        run_dispatcher._shutting_down = False
