"""Read-side tests for the executions API (P4 scope).

P4 retired the V1 subprocess creation chain (POST /api/executions +
/…/rerun — creation now lives at POST /api/runs via run_dispatcher).
These tests cover the shared read surface that survives: list/detail
isolation, run deletion counter consistency, execution deletion, the
log endpoint, SSE log-stream replay, and the auto-migration of new
exec_runs columns.  Rows are inserted directly via SQLAlchemy — no
subprocess, no loader.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select


async def _login_alice(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    r = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _alice_id() -> int:
    from app.core.db import SessionLocal
    from app.models import User

    async with SessionLocal() as s:
        alice = (
            await s.execute(select(User).where(User.username == "alice"))
        ).scalar_one()
        return alice.id


async def _insert_execution(
    *,
    case_id: str = "sc_e2e",
    runs: list[dict] | None = None,
    total_runs: int | None = None,
    passed: int = 0,
    failed: int = 0,
    status: str = "done",
) -> int:
    """Insert an Execution (+ optional ExecRun rows) for alice."""
    from app.core.db import SessionLocal
    from app.models import ExecRun, Execution

    runs = runs if runs is not None else [{"idx": 1, "status": "pending"}]
    owner_id = await _alice_id()
    async with SessionLocal() as s:
        ex = Execution(
            case_id=case_id,
            owner_id=owner_id,
            status=status,
            total_runs=total_runs if total_runs is not None else len(runs),
            passed=passed,
            failed=failed,
        )
        s.add(ex)
        await s.commit()
        await s.refresh(ex)
        for r in runs:
            s.add(ExecRun(execution_id=ex.id, **r))
        await s.commit()
        return ex.id


# ── list / detail isolation ────────────────────────────────────
async def test_list_executions_only_returns_owners(client: AsyncClient) -> None:
    a_auth = await _login_alice(client)
    await _insert_execution(case_id="sc_a")
    await client.post(
        "/api/auth/register", json={"username": "bob", "password": "bobpass456"}
    )
    b_login = await client.post(
        "/api/auth/login", json={"username": "bob", "password": "bobpass456"}
    )
    b_auth = {"Authorization": f"Bearer {b_login.json()['access_token']}"}
    # Bob has no executions.
    b_list = await client.get("/api/executions", headers=b_auth)
    assert b_list.status_code == 200
    assert b_list.json()["total"] == 0

    a_list = await client.get("/api/executions", headers=a_auth)
    assert a_list.json()["total"] == 1
    assert a_list.json()["items"][0]["case_id"] == "sc_a"

    # Cross-owner detail access: bob can't read alice's execution.
    eid = a_list.json()["items"][0]["id"]
    r = await client.get(f"/api/executions/{eid}", headers=b_auth)
    assert r.status_code == 404


async def test_unknown_execution_404(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    r = await client.get("/api/executions/9999", headers=auth)
    assert r.status_code == 404


# ── delete execution ───────────────────────────────────────────
async def test_delete_execution_removes_rows(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    eid = await _insert_execution(
        runs=[{"idx": 1, "status": "passed", "exit_code": 0}]
    )
    d = await client.delete(f"/api/executions/{eid}", headers=auth)
    assert d.status_code == 204
    g = await client.get(f"/api/executions/{eid}", headers=auth)
    assert g.status_code == 404


# ── delete run counter consistency ─────────────────────────────
async def test_delete_completed_run_decrements_passed_counter(
    client: AsyncClient,
) -> None:
    auth = await _login_alice(client)
    eid = await _insert_execution(
        runs=[{"idx": 1, "status": "passed", "exit_code": 0}],
        passed=1,
    )
    from app.core.db import SessionLocal
    from app.models import ExecRun

    async with SessionLocal() as s:
        run = (
            await s.execute(select(ExecRun).where(ExecRun.execution_id == eid))
        ).scalars().first()
        run_id = run.id

    r = await client.delete(f"/api/executions/{eid}/runs/{run_id}", headers=auth)
    assert r.status_code == 204

    from app.models import Execution

    async with SessionLocal() as s:
        ex = await s.get(Execution, eid)
        assert ex.passed == 0
        assert ex.total_runs == 0


async def test_delete_pending_run_only_decrements_total_runs(
    client: AsyncClient,
) -> None:
    auth = await _login_alice(client)
    eid = await _insert_execution(runs=[{"idx": 1, "status": "pending"}])
    from app.core.db import SessionLocal
    from app.models import ExecRun

    async with SessionLocal() as s:
        run = (
            await s.execute(select(ExecRun).where(ExecRun.execution_id == eid))
        ).scalars().first()
        run_id = run.id

    r = await client.delete(f"/api/executions/{eid}/runs/{run_id}", headers=auth)
    assert r.status_code == 204

    from app.models import Execution

    async with SessionLocal() as s:
        ex = await s.get(Execution, eid)
        assert ex.passed == 0
        assert ex.failed == 0
        assert ex.total_runs == 0


# ── run log endpoint ───────────────────────────────────────────
async def test_run_log_endpoint_returns_file_text(
    client: AsyncClient, tmp_path: Path
) -> None:
    auth = await _login_alice(client)
    eid = await _insert_execution()

    fake_log = tmp_path / "run_X.log"
    fake_log.write_text(
        "# gimbal run log\n"
        "# command:\ngimbal run launch tmp.yaml --env dev --report-dir reports\n"
        "# exit_code: 0\n\n"
        "===== STDOUT =====\nhello stdout\n"
        "===== STDERR =====\nhello stderr\n\n",
        encoding="utf-8",
    )
    from app.core.db import SessionLocal
    from app.models import ExecRun

    async with SessionLocal() as s:
        run = (
            await s.execute(select(ExecRun).where(ExecRun.execution_id == eid))
        ).scalars().first()
        run.log_path = str(fake_log)
        run.command_line = "gimbal run launch tmp.yaml --env dev --report-dir reports"
        await s.commit()
        rid = run.id

    r = await client.get(f"/api/executions/{eid}/runs/{rid}/log", headers=auth)
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "gimbal run launch" in r.text
    assert "hello stdout" in r.text
    assert "hello stderr" in r.text

    # log_path / command_line flow through the detail endpoint
    d = await client.get(f"/api/executions/{eid}", headers=auth)
    items = d.json()["runs"]
    assert items[0]["log_path"].endswith("run_X.log")
    assert "gimbal run launch" in items[0]["command_line"]


async def test_run_log_endpoint_returns_404_for_unknown_run(
    client: AsyncClient,
) -> None:
    auth = await _login_alice(client)
    r = await client.get("/api/executions/999999/runs/999999/log", headers=auth)
    assert r.status_code == 404


# ── SSE log stream ─────────────────────────────────────────────
async def test_run_log_stream_replays_history_for_late_subscriber(
    client: AsyncClient,
) -> None:
    from app.services.log_hub import hub

    auth = await _login_alice(client)
    eid = 999_001
    rid = 888_001
    from app.core.db import SessionLocal
    from app.models import ExecRun, Execution

    async with SessionLocal() as s:
        s.add(Execution(
            id=eid, case_id="stream-test", owner_id=await _alice_id(),
            status="done", total_runs=1, passed=1, failed=0,
        ))
        s.add(ExecRun(id=rid, execution_id=eid, idx=1, status="passed", exit_code=0))
        await s.commit()

    channel = hub.get_or_create(eid, rid)
    loop = asyncio.get_running_loop()
    channel.publish_from_thread("stdout", "first-line\n", loop)
    channel.publish_from_thread("stderr", "warning-line\n", loop)
    channel.mark_done_from_thread(exit_code=0, loop=loop)

    try:
        async with client.stream(
            "GET", f"/api/executions/{eid}/runs/{rid}/log/stream", headers=auth
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            collected: list[str] = []
            async for chunk in resp.aiter_text():
                collected.append(chunk)
                if "event: end" in "".join(collected):
                    break
        body = "".join(collected)
        assert "first-line" in body
        assert "event: stdout" in body
        assert "event: end" in body
        assert '"exit_code": 0' in body
    finally:
        async with SessionLocal() as s:
            await s.execute(ExecRun.__table__.delete().where(ExecRun.id == rid))
            await s.execute(Execution.__table__.delete().where(Execution.id == eid))
            await s.commit()
        hub.drop(eid, rid)


async def test_run_log_stream_skips_lines_before_last_event_id(
    client: AsyncClient,
) -> None:
    from app.services.log_hub import hub

    auth = await _login_alice(client)
    eid = 999_002
    rid = 888_002
    from app.core.db import SessionLocal
    from app.models import ExecRun, Execution

    async with SessionLocal() as s:
        s.add(Execution(
            id=eid, case_id="resume-test", owner_id=await _alice_id(),
            status="done", total_runs=1, passed=1, failed=0,
        ))
        s.add(ExecRun(id=rid, execution_id=eid, idx=1, status="passed", exit_code=0))
        await s.commit()

    channel = hub.get_or_create(eid, rid)
    loop = asyncio.get_running_loop()
    for i in range(1, 6):
        channel.publish_from_thread("stdout", f"line-{i}\n", loop)
    channel.mark_done_from_thread(exit_code=0, loop=loop)

    try:
        async with client.stream(
            "GET",
            f"/api/executions/{eid}/runs/{rid}/log/stream",
            headers={**auth, "Last-Event-ID": "3"},
        ) as resp:
            assert resp.status_code == 200
            chunks: list[str] = []
            async for chunk in resp.aiter_text():
                chunks.append(chunk)
                if "event: end" in "".join(chunks):
                    break
        body = "".join(chunks)
        for gone in ("line-1", "line-2", "line-3"):
            assert gone not in body
        assert "line-4" in body
        assert "line-5" in body
        assert "event: end" in body
    finally:
        async with SessionLocal() as s:
            await s.execute(ExecRun.__table__.delete().where(ExecRun.id == rid))
            await s.execute(Execution.__table__.delete().where(Execution.id == eid))
            await s.commit()
        hub.drop(eid, rid)


# ── V1 creation endpoints retired (P4) ─────────────────────────
async def test_post_execution_and_rerun_are_gone(client: AsyncClient) -> None:
    """POST /api/executions and …/rerun must no longer exist (405/404)."""
    auth = await _login_alice(client)
    eid = await _insert_execution()
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={"case_id": "sc_x", "n_runs": 1, "parallel": 1},
    )
    assert r.status_code == 405
    r = await client.post(f"/api/executions/{eid}/runs/1/rerun", headers=auth)
    assert r.status_code in (404, 405)


# ── auto-migration of new columns ─────────────────────────────
async def test_auto_migrate_adds_missing_exec_runs_columns(tmp_path) -> None:
    import sqlite3

    from app.core import db as db_module

    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username VARCHAR(64) NOT NULL,
            display_name VARCHAR(128),
            password_hash VARCHAR(256),
            is_admin BOOLEAN,
            is_active BOOLEAN,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
        CREATE TABLE executions (
            id INTEGER PRIMARY KEY,
            case_id VARCHAR(256),
            owner_id INTEGER,
            status VARCHAR(16),
            total_runs INTEGER,
            passed INTEGER,
            failed INTEGER,
            config_json TEXT,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            created_at TIMESTAMP
        );
        CREATE TABLE exec_runs (
            id INTEGER PRIMARY KEY,
            execution_id INTEGER,
            idx INTEGER,
            status VARCHAR(16),
            exit_code INTEGER,
            report_path TEXT,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            duration_ms INTEGER
        );
        """
    )
    conn.close()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    orig_engine = db_module.engine
    orig_session = db_module.SessionLocal
    db_module.engine = test_engine
    db_module.SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)
    try:
        await db_module.init_db()
    finally:
        await test_engine.dispose()
        db_module.engine = orig_engine
        db_module.SessionLocal = orig_session

    chk = sqlite3.connect(db_file)
    cols = {r[1] for r in chk.execute("PRAGMA table_info(exec_runs)").fetchall()}
    chk.close()
    assert "log_path" in cols
    assert "command_line" in cols
