"""Read-side tests for the executions API (V3 scope).

V3 retired the V1 subprocess chain AND the per-run exec_runs cluster
(detail runs / report / log / SSE / run deletion).  Creation lives at
POST /api/runs via run_dispatcher; observability is the Execution
counters + ``data/runs/<date>.jsonl`` dispatch logs (file-based, not
API).  These tests cover the surviving read surface: list/detail
isolation, execution deletion, retired endpoints, and the dev-version
``exec_runs`` table drop migration.  Rows are inserted directly via
SQLAlchemy — no subprocess, no loader.
"""
from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from .helpers import register_and_login


async def _login_alice(client: AsyncClient) -> dict:
    return await register_and_login(client)


async def _insert_execution(
    *,
    scenario_id: str = "sc_e2e",
    total_runs: int = 1,
    passed: int = 0,
    failed: int = 0,
    status: str = "done",
) -> int:
    """Insert an Execution for alice."""
    from app.core.db import SessionLocal
    from app.models import Execution, User

    async with SessionLocal() as s:
        alice = (
            await s.execute(select(User).where(User.username == "alice"))
        ).scalar_one()
        ex = Execution(
            scenario_id=scenario_id,
            owner_id=alice.id,
            status=status,
            total_runs=total_runs,
            passed=passed,
            failed=failed,
        )
        s.add(ex)
        await s.commit()
        await s.refresh(ex)
        return ex.id


# ── list / detail isolation ────────────────────────────────────
async def test_list_executions_only_returns_owners(client: AsyncClient) -> None:
    a_auth = await _login_alice(client)
    await _insert_execution(scenario_id="sc_a")
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
    assert a_list.json()["items"][0]["scenario_id"] == "sc_a"

    # Cross-owner detail access: bob can't read alice's execution.
    eid = a_list.json()["items"][0]["id"]
    r = await client.get(f"/api/executions/{eid}", headers=b_auth)
    assert r.status_code == 404

    # Detail is the same shape as the list item (no more runs/report/log).
    d = await client.get(f"/api/executions/{eid}", headers=a_auth)
    assert d.status_code == 200
    assert d.json()["scenario_id"] == "sc_a"
    assert "runs" not in d.json()


async def test_unknown_execution_404(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    r = await client.get("/api/executions/9999", headers=auth)
    assert r.status_code == 404


# ── delete execution ───────────────────────────────────────────
async def test_delete_execution_removes_rows(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    eid = await _insert_execution(total_runs=1, passed=1)
    d = await client.delete(f"/api/executions/{eid}", headers=auth)
    assert d.status_code == 204
    g = await client.get(f"/api/executions/{eid}", headers=auth)
    assert g.status_code == 404


# ── V1 creation endpoints retired (P4) ─────────────────────────
async def test_post_execution_and_rerun_are_gone(client: AsyncClient) -> None:
    """POST /api/executions and …/rerun must no longer exist (405/404)."""
    auth = await _login_alice(client)
    eid = await _insert_execution()
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={"scenario_id": "sc_x", "n_runs": 1, "parallel": 1},
    )
    assert r.status_code == 405
    r = await client.post(f"/api/executions/{eid}/runs/1/rerun", headers=auth)
    assert r.status_code in (404, 405)


# ── V1 per-run cluster retired (exec_runs drop migration) ──────
async def test_v1_run_endpoints_are_gone(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    eid = await _insert_execution()
    r = await client.get(f"/api/executions/{eid}/runs/1/log", headers=auth)
    assert r.status_code == 404
    r = await client.get(f"/api/executions/{eid}/runs/1/log/stream", headers=auth)
    assert r.status_code == 404
    r = await client.delete(f"/api/executions/{eid}/runs/1", headers=auth)
    assert r.status_code in (404, 405)  # only /api/executions/{id} DELETE exists


async def test_init_db_drops_legacy_exec_runs_table(tmp_path) -> None:
    """A dev DB that still carries the V1 exec_runs table must have it
    dropped by init_db (dev-version data purge, idempotent)."""
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
            scenario_id VARCHAR(128),
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
            log_path TEXT,
            command_line TEXT,
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
        # Idempotency: a second run must not fail on the missing table.
        await db_module.init_db()
    finally:
        await test_engine.dispose()
        db_module.engine = orig_engine
        db_module.SessionLocal = orig_session

    chk = sqlite3.connect(db_file)
    tables = {
        r[0]
        for r in chk.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    chk.close()
    assert "exec_runs" not in tables
    assert "executions" in tables
