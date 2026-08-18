"""Tests for the executions API + executor (Spec-2 §4.5 E).

Most of the executor logic is tested at the unit level (yaml rendering,
auth merge) because the subprocess side-effects (gimbal binary) aren't
available in CI.  Router tests cover lifecycle + isolation.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.services.executor import _render_temp_yaml


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


@pytest.fixture
async def seed_public_case(tmp_path, monkeypatch) -> str:
    """Seed a public case file and point settings at the temp dir."""
    pub_dir = tmp_path / "public"
    pub_dir.mkdir()
    seed = pub_dir / "sc_e2e.json"
    seed.write_text(
        json.dumps(
            {
                "kind": "scenario",
                "scenarioId": "sc_e2e",
                "meta": {"name": "E2E Test"},
                "config": {
                    "services": {"svc": "http://x"},
                    "users": {},
                    "vars": {},
                },
                "steps": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", pub_dir)
    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    monkeypatch.setattr(cfg.settings, "DATA_DIR", tmp_path)
    (tmp_path / "users").mkdir()
    from app.services.case_loader import loader

    loader._cache.clear()
    loader._last_full_scan = 0
    return "sc_e2e"


# ── _render_temp_yaml unit tests ───────────────────────────────
def _auth(alias: str, password: str = "pw"):
    from types import SimpleNamespace

    return SimpleNamespace(
        id=1,
        alias=alias,
        url="https://x",
        username=f"user_{alias}",
        password=password,
        token_type="Bearer",
        expires_in=3600,
    )


def test_render_override_replaces_existing_users() -> None:
    payload = {
        "config": {"users": {"old": {"url": "x", "username": "u", "password": "p"}}}
    }
    out = _render_temp_yaml(
        payload,
        exec_auths=[_auth("qa1"), _auth("qa2")],
        merge_policy="override",
        prefix=None,
        idx=1,
    )
    assert set(out["config"]["users"].keys()) == {"qa1", "qa2"}
    assert "old" not in out["config"]["users"]


def test_render_override_with_empty_aliases_preserves_users() -> None:
    """Defensive: ``override`` with ``exec_auths=[]`` must NOT clobber the
    case yaml's users with an empty dict.  Falls through to the origin
    (preserve) path so an accidental "override + nothing selected" still
    leaves the baseline users intact."""
    payload = {
        "config": {
            "users": {"codfish": {"url": "x", "username": "u", "password": "p"}}
        }
    }
    out = _render_temp_yaml(
        payload,
        exec_auths=[],
        merge_policy="override",
        prefix=None,
        idx=1,
        inject_credentials=True,
    )
    assert out["config"]["users"] == payload["config"]["users"]
    assert "codfish" in out["config"]["users"]


def test_render_merge_keeps_existing() -> None:
    payload = {
        "config": {
            "users": {"old": {"url": "x", "username": "u", "password": "p"}}
        }
    }
    out = _render_temp_yaml(
        payload,
        exec_auths=[_auth("qa1")],
        merge_policy="merge",
        prefix=None,
        idx=1,
    )
    assert set(out["config"]["users"].keys()) == {"old", "qa1"}


def test_render_merge_overrides_same_alias() -> None:
    payload = {
        "config": {
            "users": {"qa1": {"url": "old", "username": "u", "password": "p"}}
        }
    }
    out = _render_temp_yaml(
        payload,
        exec_auths=[_auth("qa1", password="newpw")],
        merge_policy="merge",
        prefix=None,
        idx=1,
    )
    assert out["config"]["users"]["qa1"]["password"] == "newpw"


def test_render_append_raises_on_conflict() -> None:
    payload = {
        "config": {"users": {"qa1": {"url": "x", "username": "u", "password": "p"}}}
    }
    with pytest.raises(ValueError, match="append policy conflict"):
        _render_temp_yaml(
            payload,
            exec_auths=[_auth("qa1")],
            merge_policy="append",
            prefix=None,
            idx=1,
        )


def test_render_injects_prefix_and_sequence_vars() -> None:
    payload = {"config": {}}
    out = _render_temp_yaml(
        payload,
        exec_auths=[],
        merge_policy="override",
        prefix="BIZ2024",
        idx=1,
    )
    assert out["config"]["vars"]["order_no_prefix"] == "BIZ2024"
    assert out["config"]["vars"]["order_no"].startswith("BIZ2024-")
    assert out["config"]["vars"]["seq"] == {"kind": "seq"}


def test_render_preserves_services_and_setup() -> None:
    payload = {
        "config": {
            "services": {"api": "https://api"},
            "setup": [{"kind": "noop"}],
        }
    }
    out = _render_temp_yaml(
        payload, exec_auths=[], merge_policy="override", prefix=None, idx=1
    )
    assert out["config"]["services"] == {"api": "https://api"}
    assert out["config"]["setup"] == [{"kind": "noop"}]


def test_render_does_not_mutate_input() -> None:
    """Critical: payload from loader cache must not be mutated."""
    payload = {"config": {"users": {"original": {"url": "x", "username": "u", "password": "p"}}}}
    snapshot = json.dumps(payload, sort_keys=True)
    _render_temp_yaml(
        payload,
        exec_auths=[_auth("qa1")],
        merge_policy="override",
        prefix=None,
        idx=1,
    )
    assert json.dumps(payload, sort_keys=True) == snapshot


# ── inject_credentials=False (a.k.a. UI "origin") ──────────────
def test_render_origin_keeps_existing_users() -> None:
    """``inject_credentials=False`` must leave ``Config.users`` exactly as
    the case yaml defines it — even if ``exec_auths`` is non-empty."""
    payload = {
        "config": {
            "users": {"default_user": {"url": "x", "username": "u", "password": "p"}}
        }
    }
    out = _render_temp_yaml(
        payload,
        exec_auths=[_auth("qa1"), _auth("qa2")],
        merge_policy="override",
        prefix=None,
        idx=1,
        inject_credentials=False,
    )
    assert out["config"]["users"] == payload["config"]["users"]
    assert "qa1" not in out["config"]["users"]
    assert "qa2" not in out["config"]["users"]


def test_render_origin_still_injects_vars() -> None:
    """``inject_credentials=False`` only skips credentials — prefix + seq
    vars must still be injected, they're not credentials."""
    payload = {"config": {}}
    out = _render_temp_yaml(
        payload,
        exec_auths=[],
        merge_policy="override",
        prefix="BIZ",
        idx=1,
        inject_credentials=False,
    )
    assert out["config"]["vars"]["seq"] == {"kind": "seq"}
    assert out["config"]["vars"]["order_no_prefix"] == "BIZ"
    assert out["config"]["vars"]["order_no"].startswith("BIZ-")


def test_render_origin_with_no_users_in_payload() -> None:
    """Edge case: payload has no ``Config.users`` at all and origin is on.
    Result must be an empty ``Config.users`` dict (no auths are fetched,
    nothing to inject)."""
    payload = {"config": {"services": {"api": "https://api"}}}
    out = _render_temp_yaml(
        payload,
        exec_auths=[],
        merge_policy="override",
        prefix=None,
        idx=1,
        inject_credentials=False,
    )
    assert out["config"]["users"] == {}
    assert out["config"]["services"] == {"api": "https://api"}


# ── router lifecycle ────────────────────────────────────────────
async def test_create_execution_creates_runs_and_returns(
    client: AsyncClient, seed_public_case: str
) -> None:
    await client.post(
        "/api/auth/register", json={"username": "alice", "password": "alicepass123"}
    )
    login = await client.post(
        "/api/auth/login", json={"username": "alice", "password": "alicepass123"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.post(
        "/api/executions",
        headers=auth,
        json={
            "case_id": seed_public_case,
            "n_runs": 3,
            "parallel": 2,
            "env": "dev",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["case_id"] == seed_public_case
    assert body["total_runs"] == 3
    assert body["status"] in ("queued", "running", "done", "failed")

    # Detail shows 3 runs
    detail = await client.get(f"/api/executions/{body['id']}", headers=auth)
    assert detail.status_code == 200
    runs = detail.json()["runs"]
    assert len(runs) == 3
    assert [r["idx"] for r in runs] == [1, 2, 3]


async def test_list_executions_only_returns_owners(
    client: AsyncClient, seed_public_case: str
) -> None:
    await client.post(
        "/api/auth/register", json={"username": "alice", "password": "alicepass123"}
    )
    a_login = await client.post(
        "/api/auth/login", json={"username": "alice", "password": "alicepass123"}
    )
    a_auth = {"Authorization": f"Bearer {a_login.json()['access_token']}"}
    await client.post(
        "/api/auth/register", json={"username": "bob", "password": "bobpass456"}
    )
    b_login = await client.post(
        "/api/auth/login", json={"username": "bob", "password": "bobpass456"}
    )
    b_auth = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    await client.post(
        "/api/executions",
        headers=a_auth,
        json={"case_id": seed_public_case, "n_runs": 1, "parallel": 1},
    )
    await client.post(
        "/api/executions",
        headers=b_auth,
        json={"case_id": seed_public_case, "n_runs": 1, "parallel": 1},
    )

    a_list = await client.get("/api/executions", headers=a_auth)
    b_list = await client.get("/api/executions", headers=b_auth)
    assert a_list.json()["total"] == 1
    assert b_list.json()["total"] == 1
    # Cross-owner: bob can't see alice's
    bob_sees_alices = [e for e in b_list.json()["items"]]
    assert all(e["case_id"] == seed_public_case for e in bob_sees_alices)


async def test_unknown_execution_404(
    client: AsyncClient, seed_public_case: str
) -> None:
    await client.post(
        "/api/auth/register", json={"username": "alice", "password": "alicepass123"}
    )
    login = await client.post(
        "/api/auth/login", json={"username": "alice", "password": "alicepass123"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.get("/api/executions/9999", headers=auth)
    assert r.status_code == 404


async def test_execution_with_prefix_injects_var(
    client: AsyncClient, seed_public_case: str, tmp_path: Path
) -> None:
    """End-to-end: create execution with prefix, fetch detail, verify config."""
    await client.post(
        "/api/auth/register", json={"username": "alice", "password": "alicepass123"}
    )
    login = await client.post(
        "/api/auth/login", json={"username": "alice", "password": "alicepass123"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.post(
        "/api/executions",
        headers=auth,
        json={
            "case_id": seed_public_case,
            "n_runs": 1,
            "parallel": 1,
            "env": "dev",
            "prefix": "BIZ2024",
            "merge_policy": "override",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["config"]["prefix"] == "BIZ2024"
    assert body["config"]["merge_policy"] == "override"


async def test_execution_with_inject_credentials_false_persists(
    client: AsyncClient, seed_public_case: str
) -> None:
    """``inject_credentials`` must round-trip through ``config_json`` so
    a later rerun honors the original "origin" intent."""
    await client.post(
        "/api/auth/register", json={"username": "alice", "password": "alicepass123"}
    )
    login = await client.post(
        "/api/auth/login", json={"username": "alice", "password": "alicepass123"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.post(
        "/api/executions",
        headers=auth,
        json={
            "case_id": seed_public_case,
            "n_runs": 1,
            "parallel": 1,
            "env": "dev",
            "inject_credentials": False,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["config"]["inject_credentials"] is False


async def test_delete_execution_removes_rows(
    client: AsyncClient, seed_public_case: str
) -> None:
    await client.post(
        "/api/auth/register", json={"username": "alice", "password": "alicepass123"}
    )
    login = await client.post(
        "/api/auth/login", json={"username": "alice", "password": "alicepass123"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.post(
        "/api/executions",
        headers=auth,
        json={"case_id": seed_public_case, "n_runs": 2, "parallel": 1},
    )
    eid = r.json()["id"]

    d = await client.delete(f"/api/executions/{eid}", headers=auth)
    assert d.status_code == 204
    g = await client.get(f"/api/executions/{eid}", headers=auth)
    assert g.status_code == 404


# ── run log endpoint ──────────────────────────────────────────
async def test_run_log_writes_file_and_endpoint_returns_text(
    client: AsyncClient, tmp_path, monkeypatch, seed_public_case: str
) -> None:
    """The ``GET /executions/{eid}/runs/{rid}/log`` endpoint should
    stream the run's log file as ``text/plain``.  We hand-write a fake
    log file at a known path + DB row to skip the real subprocess.
    """
    import io
    import json

    from app.core import db as db_module
    from app.models import ExecRun
    from sqlalchemy import select

    auth = await _login_alice(client)
    payload = {
        "kind": "scenario",
        "scenarioId": seed_public_case,
        "meta": {"name": "log_test"},
    }
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={
            "file": ("x.json", io.BytesIO(json.dumps(payload).encode()), "application/json"),
        },
    )
    case_id = r.json()["case_id"]

    r = await client.post(
        "/api/executions",
        headers=auth,
        json={"case_id": case_id, "n_runs": 1, "parallel": 1},
    )
    eid = r.json()["id"]

    fake_log = tmp_path / "run_X.log"
    fake_log.write_text(
        "# gimbal run log\n"
        "# command:\ngimbal run launch tmp.yaml --env dev --report-dir reports\n"
        "# exit_code: 0\n\n"
        "===== STDOUT =====\nhello stdout\n"
        "===== STDERR =====\nhello stderr\n\n",
        encoding="utf-8",
    )
    async with db_module.SessionLocal() as session:
        run = (
            await session.execute(
                select(ExecRun).where(ExecRun.execution_id == eid)
            )
        ).scalars().first()
        assert run is not None
        run.log_path = str(fake_log)
        run.command_line = "gimbal run launch tmp.yaml --env dev --report-dir reports"
        await session.commit()
        rid = run.id

    # /log endpoint streams the file content
    r = await client.get(f"/api/executions/{eid}/runs/{rid}/log", headers=auth)
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    assert "gimbal run launch" in body
    assert "hello stdout" in body
    assert "hello stderr" in body

    # log_path / command_line flow through detail endpoint
    d = await client.get(f"/api/executions/{eid}", headers=auth)
    items = d.json()["runs"]
    assert items[0]["log_path"].endswith("run_X.log")
    assert "gimbal run launch" in items[0]["command_line"]


async def test_run_log_endpoint_returns_404_for_unknown_run(
    client: AsyncClient
) -> None:
    """Sanity: an unknown run_id must 404 (not crash)."""
    auth = await _login_alice(client)
    r = await client.get("/api/executions/999999/runs/999999/log", headers=auth)
    assert r.status_code == 404


# ── SSE log stream ───────────────────────────────────────────
async def test_run_log_stream_replays_history_for_late_subscriber(
    client: AsyncClient,
) -> None:
    """When a SSE consumer subscribes after the run is done, the
    endpoint replays the channel's history (sourced from disk) before
    emitting the ``end`` event."""
    from app.services.log_hub import hub

    # Manually seed a finished channel — no subprocess required.
    channel = hub.get_or_create(999_001, 888_001)
    loop = asyncio.get_running_loop()
    channel.publish_from_thread("stdout", "first-line\n", loop)
    channel.publish_from_thread("stderr", "warning-line\n", loop)
    channel.mark_done_from_thread(exit_code=0, loop=loop)

    # Login first so the user row exists, then build a fake execution.
    auth = await _login_alice(client)
    from app.core.db import SessionLocal
    from app.models import ExecRun, Execution, User
    from sqlalchemy import select as _sel
    async with SessionLocal() as s:
        alice = (await s.execute(_sel(User).where(User.username == "alice"))).scalar_one()
        ex = Execution(
            id=999_001, case_id="stream-test", owner_id=alice.id,
            status="done", total_runs=1, passed=1, failed=0,
        )
        run = ExecRun(
            id=888_001, execution_id=999_001, idx=1,
            status="passed", exit_code=0,
        )
        s.add(ex); s.add(run); await s.commit()
    try:
        async with client.stream(
            "GET", "/api/executions/999001/runs/888001/log/stream", headers=auth
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            # Collect frames until we see the terminal ``end`` event.
            collected: list[str] = []
            async for chunk in resp.aiter_text():
                collected.append(chunk)
                body = "".join(collected)
                if "event: end" in body:
                    break
        body = "".join(collected)
        # Expect a stdout frame with our first line and an end frame.
        assert "first-line" in body
        assert "event: stdout" in body
        assert "event: end" in body
        assert '"exit_code": 0' in body
    finally:
        # Cleanup the fake execution/run rows so they don't pollute other tests.
        async with SessionLocal() as s:
            await s.execute(
                ExecRun.__table__.delete().where(ExecRun.id == 888_001)
            )
            await s.execute(
                Execution.__table__.delete().where(Execution.id == 999_001)
            )
            await s.commit()
        # Forget the channel so a re-run of this test starts clean.
        hub.drop(999_001, 888_001)


async def test_run_log_stream_skips_lines_before_last_event_id(
    client: AsyncClient,
) -> None:
    """When the client reconnects with Last-Event-ID, lines whose seq
    is <= that id are NOT replayed — the consumer only sees what's
    actually new since the disconnect."""
    from app.services.log_hub import hub

    # Reuse the smoke user; if this test runs first we'll need to
    # create the account via _login_alice.
    auth = await _login_alice(client)
    from app.core.db import SessionLocal
    from app.models import ExecRun, Execution, User
    from sqlalchemy import select as _sel
    async with SessionLocal() as s:
        alice = (await s.execute(_sel(User).where(User.username == "alice"))).scalar_one()
        ex = Execution(
            id=999_002, case_id="resume-test", owner_id=alice.id,
            status="done", total_runs=1, passed=1, failed=0,
        )
        run = ExecRun(
            id=888_002, execution_id=999_002, idx=1,
            status="passed", exit_code=0,
        )
        s.add(ex); s.add(run); await s.commit()

    # Seed 5 lines (seq 1..5) + end (seq 6) on the channel.
    channel = hub.get_or_create(999_002, 888_002)
    loop = asyncio.get_running_loop()
    for i in range(1, 6):
        channel.publish_from_thread("stdout", f"line-{i}\n", loop)
    channel.mark_done_from_thread(exit_code=0, loop=loop)

    try:
        # Reconnect with Last-Event-ID=3 → only seq 4, 5, and the end
        # frame should be delivered.
        async with client.stream(
            "GET",
            "/api/executions/999002/runs/888002/log/stream",
            headers={**auth, "Last-Event-ID": "3"},
        ) as resp:
            assert resp.status_code == 200
            chunks: list[str] = []
            async for chunk in resp.aiter_text():
                chunks.append(chunk)
                if "event: end" in "".join(chunks):
                    break
        body = "".join(chunks)
        # Lines 1-3 must NOT be present.
        assert "line-1" not in body
        assert "line-2" not in body
        assert "line-3" not in body
        # Lines 4-5 must be present.
        assert "line-4" in body
        assert "line-5" in body
        # End event still emitted.
        assert "event: end" in body
    finally:
        async with SessionLocal() as s:
            await s.execute(ExecRun.__table__.delete().where(ExecRun.id == 888_002))
            await s.execute(Execution.__table__.delete().where(Execution.id == 999_002))
            await s.commit()
        hub.drop(999_002, 888_002)


# ── reconciler (orphan-run recovery at startup) ───────────────
async def test_reconcile_orphan_runs_marks_stuck_failed(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """Runs marked 'running' for > ORPHAN_GRACE_MIN with no finished_at
    must be flipped to 'failed' when reconcile_orphan_runs() runs.
    Without this, /executions displays permanently-stuck rows after a
    uvicorn --reload crash (the original /executions/7 bug repro).
    """
    from app.core import db as db_module
    from app.models import ExecRun, Execution
    from app.services.run_lifecycle import (
        ORPHAN_GRACE_MIN,
        reconcile_orphan_runs,
    )

    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=1)
    auth = await _login_alice(client)
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={"case_id": case_id, "n_runs": 1, "parallel": 1},
    )
    eid = r.json()["id"]

    # Manually push started_at into the past so the reconciler sees it
    # as stale; meanwhile, leave status='running' and finished_at NULL
    # to simulate a worker that died mid-run.
    past = datetime.now(timezone.utc) - timedelta(
        minutes=ORPHAN_GRACE_MIN + 1
    )
    async with db_module.SessionLocal() as session:
        run = (
            await session.execute(
                select(ExecRun).where(ExecRun.execution_id == eid)
            )
        ).scalars().first()
        assert run is not None
        run.status = "running"
        run.started_at = past
        run.finished_at = None
        ex = await session.get(Execution, eid)
        ex.status = "running"
        ex.started_at = past
        await session.commit()

    await reconcile_orphan_runs()

    # Re-read — both rows should be marked 'failed' with finished_at set.
    async with db_module.SessionLocal() as session:
        run = (
            await session.execute(
                select(ExecRun).where(ExecRun.execution_id == eid)
            )
        ).scalars().first()
        ex = await session.get(Execution, eid)
        assert run is not None
        assert run.status == "failed"
        assert run.finished_at is not None
        assert run.duration_ms is not None and run.duration_ms > 0
        # Synthesized log_path so the UI log dialog doesn't 404.
        assert run.log_path == "recovered-at-startup"
        assert ex.status == "failed"
        assert ex.finished_at is not None


async def test_reconcile_orphan_runs_leaves_active_runs_alone(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """Runs that ARE active (started_at within grace window) must NOT be
    touched — the reconciler must only reap STALE state, not anything
    in flight."""
    from app.core import db as db_module
    from app.models import ExecRun, Execution
    from app.services.run_lifecycle import reconcile_orphan_runs

    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=1)
    auth = await _login_alice(client)
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={"case_id": case_id, "n_runs": 1, "parallel": 1},
    )
    eid = r.json()["id"]

    # started_at defaults to now() — well within grace window.
    async with db_module.SessionLocal() as session:
        run = (
            await session.execute(
                select(ExecRun).where(ExecRun.execution_id == eid)
            )
        ).scalars().first()
        run.status = "running"
        ex = await session.get(Execution, eid)
        ex.status = "running"
        ex.started_at = run.started_at
        await session.commit()

    await reconcile_orphan_runs()

    async with db_module.SessionLocal() as session:
        run = (
            await session.execute(
                select(ExecRun).where(ExecRun.execution_id == eid)
            )
        ).scalars().first()
        ex = await session.get(Execution, eid)
        # Both still 'running' — reconciler left them alone
        assert run.status == "running"
        assert ex.status == "running"


# ── rerun-as-insert (B-model: rerun creates a new ExecRun row) ────
# Tests for the new semantics where each /rerun INSERTs a new ExecRun
# row with idx = max(idx) + 1, preserving full attempt history.  This
# replaces the old "update-in-place" behavior that double-counted
# passed/failed across attempts.


async def test_rerun_inserts_new_run_row_with_next_idx(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """Rerun must INSERT (not UPDATE) — old row keeps its id, new row
    gets idx = max(idx) + 1."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=3)
    await _login_alice(client)
    eid = await _create_execution_directly(
        client, case_id=case_id, n_runs=2, parallel=1,
    )
    # Capture command line via the existing pattern.
    cap = _CapturedCmd()
    cap.install(monkeypatch)

    # First rerun of an existing run.
    from app.core.db import SessionLocal
    from app.models import ExecRun
    from sqlalchemy import select as _sel

    async with SessionLocal() as s:
        first_run = (await s.execute(
            _sel(ExecRun).where(ExecRun.execution_id == eid)
        )).scalars().first()
        first_run_id = first_run.id
        first_idx = first_run.idx

    r = await client.post(
        f"/api/executions/{eid}/runs/{first_run_id}/rerun",
        headers={"Authorization": f"Bearer {(await client.post('/api/auth/login', json={'username':'alice','password':'alicepass123'})).json()['access_token']}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # New row must have a different id from the original.
    assert body["id"] != first_run_id
    # And idx must be max+1 of the previous set.
    async with SessionLocal() as s:
        rows = (await s.execute(
            _sel(ExecRun).where(ExecRun.execution_id == eid).order_by(ExecRun.idx)
        )).scalars().all()
    assert len(rows) == 3  # original 2 + 1 new
    assert [r.idx for r in rows] == [1, 2, 3]
    # The original row is untouched.
    assert rows[0].id == first_run_id
    assert rows[0].idx == first_idx


async def test_rerun_increments_total_runs(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """Each rerun increments execution.total_runs by 1 (B2 natural growth)."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=3)
    await _login_alice(client)
    eid = await _create_execution_directly(
        client, case_id=case_id, n_runs=2, parallel=1,
    )
    cap = _CapturedCmd()
    cap.install(monkeypatch)

    from app.core.db import SessionLocal
    from app.models import ExecRun, Execution
    from sqlalchemy import select as _sel

    async with SessionLocal() as s:
        ex0 = await s.get(Execution, eid)
        assert ex0.total_runs == 2
        target = (await s.execute(
            _sel(ExecRun).where(ExecRun.execution_id == eid)
        )).scalars().first()

    login = await client.post("/api/auth/login", json={"username":"alice","password":"alicepass123"})
    token = login.json()["access_token"]
    H = {"Authorization": f"Bearer {token}"}

    # Two reruns — total_runs must go from 2 to 4.
    await client.post(f"/api/executions/{eid}/runs/{target.id}/rerun", headers=H)
    await client.post(f"/api/executions/{eid}/runs/{target.id}/rerun", headers=H)

    async with SessionLocal() as s:
        ex = await s.get(Execution, eid)
        assert ex.total_runs == 4, f"expected 4, got {ex.total_runs}"


async def test_rerun_preserves_old_run_log_and_report(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """Each rerun gets its OWN log_path + report_path derived from the
    new run_id — old attempts' artifacts stay intact (no overwrite)."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=3)
    await _login_alice(client)
    eid = await _create_execution_directly(
        client, case_id=case_id, n_runs=1, parallel=1,
    )
    cap = _CapturedCmd()
    cap.install(monkeypatch)

    from app.core.db import SessionLocal
    from app.models import ExecRun
    from sqlalchemy import select as _sel

    async with SessionLocal() as s:
        target = (await s.execute(
            _sel(ExecRun).where(ExecRun.execution_id == eid)
        )).scalars().first()

    login = await client.post("/api/auth/login", json={"username":"alice","password":"alicepass123"})
    H = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # First rerun
    r1 = await client.post(f"/api/executions/{eid}/runs/{target.id}/rerun", headers=H)
    new_run_id_1 = r1.json()["id"]
    # Second rerun of the same original run
    r2 = await client.post(f"/api/executions/{eid}/runs/{target.id}/rerun", headers=H)
    new_run_id_2 = r2.json()["id"]

    async with SessionLocal() as s:
        run1 = await s.get(ExecRun, new_run_id_1)
        run2 = await s.get(ExecRun, new_run_id_2)
        # Each run's log_path references its own id (no shared file).
        assert run1.log_path is not None
        assert run2.log_path is not None
        assert run1.log_path != run2.log_path
        # Both end in their own run_<id>.log filename.
        assert run1.log_path.endswith(f"run_{new_run_id_1}.log")
        assert run2.log_path.endswith(f"run_{new_run_id_2}.log")




async def test_concurrent_reruns_dedup_via_unique_constraint(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """The UNIQUE (execution_id, idx) constraint on exec_runs
    forces a concurrent rerun collision into an IntegrityError, which
    the rerun handler catches and retries with a fresh idx.  Simulated
    by pre-inserting a row at the idx our rerun will pick, forcing
    the rerun into the retry path without actually racing two HTTP
    calls (which is brittle on aiosqlite + the connection pool)."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=3)
    await _login_alice(client)
    eid = await _create_execution_directly(
        client, case_id=case_id, n_runs=1, parallel=1,
    )
    cap = _CapturedCmd()
    cap.install(monkeypatch)

    from app.core.db import SessionLocal
    from app.models import ExecRun, Execution
    from sqlalchemy import select

    async with SessionLocal() as s:
        target = (await s.execute(
            select(ExecRun).where(ExecRun.execution_id == eid)
        )).scalars().first()
        # Pre-insert a "phantom" row at the idx the rerun would pick
        # next (max(existing idx) + 1 == 2 here, since the original row
        # is at idx=1).  This forces the INSERT to fail with
        # UNIQUE-constraint violation so the handler's retry path
        # runs; the retry then picks idx=3 and succeeds.
        s.add(ExecRun(execution_id=eid, idx=2, status="failed"))
        await s.commit()
        # Bump total_runs manually so the parent counter matches
        # what the retry will write (the failing INSERT also bumped).
        ex = await s.get(Execution, eid)
        ex.total_runs = (ex.total_runs or 0) + 1
        await s.commit()

    login = await client.post("/api/auth/login", json={"username":"alice","password":"alicepass123"})
    H = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # The rerun handler should: hit idx=2 (collision) → IntegrityError
    # → rollback → retry with idx=3 → success.
    r = await client.post(f"/api/executions/{eid}/runs/{target.id}/rerun", headers=H)
    assert r.status_code == 200, r.text

    async with SessionLocal() as s:
        new_rows = (await s.execute(
            select(ExecRun).where(
                ExecRun.execution_id == eid,
                ExecRun.id != target.id,
            )
        )).scalars().all()
    idxs = sorted(r.idx for r in new_rows)
    assert idxs == [2, 3], f"expected [2, 3], got {idxs}"
    # The rerun should land on idx=3, not collide with the phantom.
    assert any(r.idx == 3 for r in new_rows)
    assert not any(r.idx == 4 for r in new_rows)



async def test_rerun_replays_step_to_from_execution_config(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """Rerun honors the original execution's step_to (regression: B-model
    still threads step_to into argv even though rerun uses a new row)."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=5)
    await _login_alice(client)
    eid = await _create_execution_directly(
        client, case_id=case_id, n_runs=1, parallel=1, step_to=2,
    )
    cap = _CapturedCmd()
    cap.install(monkeypatch)

    from app.core.db import SessionLocal
    from app.models import ExecRun
    from sqlalchemy import select as _sel

    async with SessionLocal() as s:
        target = (await s.execute(
            _sel(ExecRun).where(ExecRun.execution_id == eid)
        )).scalars().first()

    login = await client.post("/api/auth/login", json={"username":"alice","password":"alicepass123"})
    H = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.post(f"/api/executions/{eid}/runs/{target.id}/rerun", headers=H)
    assert r.status_code == 200

    argv = cap.captured[-1]
    assert "--step-to" in argv
    assert argv[argv.index("--step-to") + 1] == "2"


async def test_delete_completed_run_decrements_passed_counter(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """Deleting a passed run must decrement execution.passed (B-model
    counter consistency)."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=3)
    await _login_alice(client)
    eid = await _create_execution_directly(
        client, case_id=case_id, n_runs=1, parallel=1,
    )
    cap = _CapturedCmd()
    cap.install(monkeypatch)

    from app.services.executor import run_execution
    await run_execution(eid)

    from app.core.db import SessionLocal
    from app.models import ExecRun, Execution
    from sqlalchemy import select as _sel

    async with SessionLocal() as s:
        ex = await s.get(Execution, eid)
        run = (await s.execute(
            _sel(ExecRun).where(ExecRun.execution_id == eid)
        )).scalars().first()
        assert run.status == "passed"
        assert ex.passed == 1
        run_id = run.id

    login = await client.post("/api/auth/login", json={"username":"alice","password":"alicepass123"})
    H = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.delete(f"/api/executions/{eid}/runs/{run_id}", headers=H)
    assert r.status_code == 204

    async with SessionLocal() as s:
        ex = await s.get(Execution, eid)
        assert ex.passed == 0, f"expected 0 after delete, got {ex.passed}"
        assert ex.total_runs == 0


async def test_delete_pending_run_only_decrements_total_runs(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """A pending/running run never incremented passed/failed, so delete
    must only decrement total_runs."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=3)
    await _login_alice(client)
    eid = await _create_execution_directly(
        client, case_id=case_id, n_runs=1, parallel=1,
    )

    from app.core.db import SessionLocal
    from app.models import ExecRun, Execution
    from sqlalchemy import select as _sel

    async with SessionLocal() as s:
        ex = await s.get(Execution, eid)
        # Counter is 0/0/1 (one pending run, no completed).
        assert ex.passed == 0
        assert ex.failed == 0
        assert ex.total_runs == 1
        run = (await s.execute(
            _sel(ExecRun).where(ExecRun.execution_id == eid)
        )).scalars().first()
        run_id = run.id

    login = await client.post("/api/auth/login", json={"username":"alice","password":"alicepass123"})
    H = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.delete(f"/api/executions/{eid}/runs/{run_id}", headers=H)
    assert r.status_code == 204

    async with SessionLocal() as s:
        ex = await s.get(Execution, eid)
        assert ex.passed == 0
        assert ex.failed == 0
        assert ex.total_runs == 0


# ── command_line override (admin-only) ──────────────────────
async def test_command_line_override_requires_admin(
    client: AsyncClient
) -> None:
    """``command_line`` is an authenticated RCE surface — only admins may
    set it.  Non-admin user posting it gets 403 and the field is silently
    ignored (defence in depth: the row stays functional with default)."""
    await client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "bobpass456"},
    )
    bob_login = await client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "bobpass456"},
    )
    bob_auth = {
        "Authorization": f"Bearer {bob_login.json()['access_token']}"
    }
    # Flip bob to non-admin (spec-1 all are admin; force non-admin here)
    from app.core import db as db_module
    from app.models.user import User

    async with db_module.SessionLocal() as session:
        bob = (
            await session.execute(
                select(User).where(User.username == "bob")
            )
        ).scalars().first()
        # Spec-1 users are admin by default; force non-admin for this test.
        bob.is_admin = False
        await session.commit()

    r = await client.post(
        "/api/executions",
        headers=bob_auth,
        json={
            "case_id": "sc_e2e",
            "n_runs": 1,
            "parallel": 1,
            "command_line": ["gimbal", "run", "launch", "/tmp/x.yaml"],
        },
    )
    assert r.status_code == 403


async def test_admin_command_line_override_persists(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """When an admin sets ``command_line``, the orchestrator must use it
    (overriding the default ``gimbal run launch <yaml> ...`` argv).  We
    verify this by inspecting the persisted ``config_json``.command_line
    on the resulting Execution row."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=1)
    await client.post(
        "/api/auth/register",
        json={"username": "adminuser", "password": "adminpass789"},
    )
    adm_login = await client.post(
        "/api/auth/login",
        json={"username": "adminuser", "password": "adminpass789"},
    )
    adm_auth = {
        "Authorization": f"Bearer {adm_login.json()['access_token']}"
    }

    custom_cmd = ["gimbal", "run", "launch", "/tmp/x.yaml", "--extra=foo"]
    r = await client.post(
        "/api/executions",
        headers=adm_auth,
        json={
            "case_id": case_id,
            "n_runs": 1,
            "parallel": 1,
            "command_line": custom_cmd,
        },
    )
    assert r.status_code == 201, r.text

    eid = r.json()["id"]
    g = await client.get(f"/api/executions/{eid}", headers=adm_auth)
    body = g.json()
    assert body["config"]["command_line"] == custom_cmd


# ── auto-migration of new columns ─────────────────────────────
async def test_auto_migrate_adds_missing_exec_runs_columns(tmp_path) -> None:
    """``_auto_add_columns()`` adds the new exec_runs columns to a DB
    predating this release (no alembic, dev-friendly auto-migrate).
    """
    import sqlite3

    from app.core import db as db_module

    # Create a "legacy" exec_runs table missing log_path + command_line.
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

    # Point the global engine at our file, run init_db.
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


# ── gimbal run show endpoint ────────────────────────────────────
# Tests for GET /api/cases/{case_id}/show.  All subprocess calls are
# replaced with ``monkeypatch`` against ``_run_gimbal_capture`` so no
# real ``gimbal`` binary needs to be on PATH during CI.


def _fake_show_payload(step_count: int = 3) -> str:
    """Synthesize the JSON output of ``gimbal run show --format=json``."""
    steps = [
        {
            "index": i,
            "kind": "step",
            "description": f"step {i} desc",
            "api": {"service": "svc", "method": "POST", "path": f"/api/{i}"},
            "strategy_kinds": ["assertion"],
            "strategy_count": 1,
        }
        for i in range(step_count)
    ]
    payload = [
        {
            "scenario_id": "sc_e2e",
            "name": "E2E Test",
            "description": "test scenario",
            "tags": ["smoke"],
            "module": "settlement",
            "priority": 1,
            "author": "alice",
            "step_count": step_count,
            "steps": steps,
            "usage_hint": {"run": "gimbal run scenario sc_e2e"},
        }
    ]
    return json.dumps(payload, ensure_ascii=False)


async def test_case_show_happy_path(
    client: AsyncClient, monkeypatch, seed_public_case: str
) -> None:
    """GET /cases/{case_id}/show shells out to gimbal and returns the
    first scenario parsed from its JSON stdout."""
    auth = await _login_alice(client)

    # Stub subprocess: succeed with the standard gimbal run show shape.
    async def fake_capture(cmd_args, *, timeout):
        return (0, _fake_show_payload(step_count=3))

    from app.routers import cases as cases_router

    monkeypatch.setattr(cases_router, "_run_gimbal_capture", fake_capture)

    r = await client.get(f"/api/cases/{seed_public_case}/show", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scenario_id"] == "sc_e2e"
    assert body["step_count"] == 3
    assert len(body["steps"]) == 3
    assert body["steps"][0]["index"] == 0
    assert body["steps"][0]["description"] == "step 0 desc"
    assert body["steps"][0]["api"]["method"] == "POST"


async def test_case_show_unknown_case_404(
    client: AsyncClient, monkeypatch
) -> None:
    auth = await _login_alice(client)

    async def fake_capture(cmd_args, *, timeout):
        return (0, _fake_show_payload())

    from app.routers import cases as cases_router

    monkeypatch.setattr(cases_router, "_run_gimbal_capture", fake_capture)

    r = await client.get("/api/cases/nonexistent_case/show", headers=auth)
    assert r.status_code == 404


async def test_case_show_gimbal_exit_nonzero_returns_502(
    client: AsyncClient, monkeypatch, seed_public_case: str
) -> None:
    """Non-zero subprocess exit → 502 with a stdout snippet in detail."""
    auth = await _login_alice(client)

    async def fake_capture(cmd_args, *, timeout):
        return (2, "Error: malformed scenario file")

    from app.routers import cases as cases_router

    monkeypatch.setattr(cases_router, "_run_gimbal_capture", fake_capture)

    r = await client.get(f"/api/cases/{seed_public_case}/show", headers=auth)
    assert r.status_code == 502
    detail = r.json()["detail"]
    assert "exit=2" in detail
    assert "malformed" in detail


async def test_case_show_gimbal_binary_missing_returns_500(
    client: AsyncClient, monkeypatch, seed_public_case: str
) -> None:
    """``returncode == 127`` (binary not on PATH) → 500 with actionable
    message so operators can diagnose without log-diving."""
    auth = await _login_alice(client)

    async def fake_capture(cmd_args, *, timeout):
        return (127, "")

    from app.routers import cases as cases_router

    monkeypatch.setattr(cases_router, "_run_gimbal_capture", fake_capture)

    r = await client.get(f"/api/cases/{seed_public_case}/show", headers=auth)
    assert r.status_code == 500
    assert "gimbal binary not on PATH" in r.json()["detail"]


async def test_case_show_file_missing_returns_400(
    client: AsyncClient, monkeypatch, seed_public_case: str, tmp_path: Path
) -> None:
    """If the on-disk yaml is gone but the cache summary still resolves,
    return 400 (not 502) — this is operator-fixable by re-uploading."""
    auth = await _login_alice(client)

    # Make the capture function a no-op; the 400 check fires before we
    # get to subprocess.
    async def fake_capture(cmd_args, *, timeout):
        pytest.fail("subprocess must not be invoked when yaml is missing")

    from app.routers import cases as cases_router

    monkeypatch.setattr(cases_router, "_run_gimbal_capture", fake_capture)

    # Force the loader to populate its cache NOW (before we delete the
    # file) so the endpoint can still resolve the case summary from cache
    # and reach the file-existence check.
    from app.services.case_loader import loader

    loader.scan(owner_id=None)

    # Locate the seeded file and delete it.
    pub_dir = tmp_path / "public"
    target = pub_dir / f"{seed_public_case}.json"
    target.unlink()

    r = await client.get(f"/api/cases/{seed_public_case}/show", headers=auth)
    assert r.status_code == 400
    assert "missing on disk" in r.json()["detail"]


async def test_case_show_private_cross_user_returns_404(
    client: AsyncClient, monkeypatch, tmp_path
) -> None:
    """Private case owned by alice → bob's GET returns 404 (existence-hiding)."""
    # Seed a private case directory for alice (owner_id resolved from her user.id).
    user_dir = tmp_path / "users" / "9999"
    user_dir.mkdir(parents=True)
    (user_dir / "alice_private.json").write_text(
        json.dumps(
            {
                "kind": "scenario",
                "scenarioId": "alice_private",
                "meta": {"name": "Alice's private case"},
                "config": {"services": {}, "users": {}, "vars": {}},
                "steps": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    pub_dir = tmp_path / "public"
    pub_dir.mkdir()
    (pub_dir / "_placeholder.json").write_text(
        json.dumps(
            {
                "kind": "scenario",
                "scenarioId": "_placeholder",
                "meta": {"name": "placeholder"},
                "config": {"services": {}, "users": {}, "vars": {}},
                "steps": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", pub_dir)
    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    monkeypatch.setattr(cfg.settings, "DATA_DIR", tmp_path)
    from app.services.case_loader import loader

    loader._cache.clear()
    loader._last_full_scan = 0

    # Register alice + bob
    await client.post(
        "/api/auth/register", json={"username": "alice", "password": "alicepass123"}
    )
    await client.post(
        "/api/auth/register", json={"username": "bob", "password": "bobpass123"}
    )
    al = (await client.post(
        "/api/auth/login", json={"username": "alice", "password": "alicepass123"}
    )).json()["access_token"]
    bl = (await client.post(
        "/api/auth/login", json={"username": "bob", "password": "bobpass123"}
    )).json()["access_token"]

    # After alice logs in, the loader has indexed her private dir under
    # her user.id — but we built the user_dir with a literal "9999" name.
    # Inspect what id alice actually got and rename if needed.
    from app.core.db import SessionLocal
    from app.models import User
    from sqlalchemy import select as _sel

    async with SessionLocal() as s:
        alice_row = (await s.execute(_sel(User).where(User.username == "alice"))).scalar_one()
        real_id = alice_row.id
    real_user_dir = tmp_path / "users" / str(real_id)
    if real_user_dir != user_dir:
        user_dir.rename(real_user_dir)
        loader._cache.clear()
        loader._last_full_scan = 0

    # Alice can see it (own private case).
    # Stub the subprocess — we don't want to depend on a real gimbal
    # binary being present in CI; the auth + 404 paths are what we're
    # actually testing.
    async def fake_capture(cmd_args, *, timeout):
        return (0, _fake_show_payload(step_count=2))

    from app.routers import cases as cases_router

    monkeypatch.setattr(cases_router, "_run_gimbal_capture", fake_capture)

    r = await client.get(
        "/api/cases/alice_private/show", headers={"Authorization": f"Bearer {al}"}
    )
    assert r.status_code == 200, r.text

    # Bob gets a 404 — the case exists but is hidden from him.
    r = await client.get(
        "/api/cases/alice_private/show", headers={"Authorization": f"Bearer {bl}"}
    )
    assert r.status_code == 404


# ── step_to argv construction (executor unit) ──────────────────
# These tests bypass the subprocess side entirely by stubbing the
# streaming helper at module level.  They verify the argv the executor
# would have passed to gimbal.


class _CapturedCmd:
    """Helper: replace ``_subprocess_run_streaming`` with one that records
    the cmd_args it was called with and returns a synthetic successful
    result.  Returns the captured cmd_args via a closure."""

    def __init__(self) -> None:
        self.captured: list[list[str]] = []

    def install(self, monkeypatch) -> None:
        from app.services import executor as ex

        def fake_stream(cmd_args, *, timeout, log_path, channel, loop):
            # NOTE: must be a sync function (not async).  The real helper
            # is invoked via ``await asyncio.to_thread(...)``; an async
            # function would just return a coroutine that the threadpool
            # never awaits, leaving ``result`` to be the bare coroutine
            # and the caller would then blow up at ``result.exit_code``.
            self.captured.append(list(cmd_args))
            return ex._StreamRunResult(exit_code=0, file_not_found=False)

        monkeypatch.setattr(ex, "_subprocess_run_streaming", fake_stream)


async def _seed_steps_case(tmp_path: Path, monkeypatch, n_steps: int = 3) -> str:
    """Same as ``seed_public_case`` but with ``n_steps`` real step entries."""
    pub_dir = tmp_path / "public"
    pub_dir.mkdir()
    case_id = "sc_steps"
    seed = pub_dir / f"{case_id}.json"
    seed.write_text(
        json.dumps(
            {
                "kind": "scenario",
                "scenarioId": case_id,
                "meta": {"name": "Steps Test"},
                "config": {
                    "services": {"svc": "http://x"},
                    "users": {},
                    "vars": {},
                },
                "steps": [
                    {"description": f"step {i}", "api": {}, "request": {"body": {}}}
                    for i in range(n_steps)
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", pub_dir)
    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    monkeypatch.setattr(cfg.settings, "DATA_DIR", tmp_path)
    (tmp_path / "users").mkdir()
    from app.services.case_loader import loader

    loader._cache.clear()
    loader._last_full_scan = 0
    return case_id


async def test_create_execution_persists_step_to(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """``step_to`` is persisted into ``config_json`` so rerun / show endpoints
    can honor the original halt intent."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=5)
    auth = await _login_alice(client)
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={
            "case_id": case_id,
            "n_runs": 1,
            "parallel": 1,
            "env": "dev",
            "step_to": 2,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["config"]["step_to"] == 2


async def test_create_execution_legacy_payload_omits_step_to(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """Payload without ``step_to`` → config_json does NOT have the key
    (preserves on-disk shape of legacy rows; ``run_execution`` falls back
    to ``cfg.get("step_to")`` → None)."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=3)
    auth = await _login_alice(client)
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={
            "case_id": case_id,
            "n_runs": 1,
            "parallel": 1,
            "env": "dev",
        },
    )
    assert r.status_code == 201, r.text
    assert "step_to" not in r.json()["config"]


async def test_create_execution_rejects_step_to_out_of_range(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """step_to >= len(steps) → 400 with descriptive detail (range info)."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=3)
    auth = await _login_alice(client)
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={
            "case_id": case_id,
            "n_runs": 1,
            "parallel": 1,
            "env": "dev",
            "step_to": 99,
        },
    )
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "step_to=99" in detail
    assert "indices 0..2" in detail


async def test_create_execution_rejects_step_to_on_stepless_case(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """step_to on a case with no steps → 400 (cannot halt nothing)."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=0)
    auth = await _login_alice(client)
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={
            "case_id": case_id,
            "n_runs": 1,
            "parallel": 1,
            "env": "dev",
            "step_to": 0,
        },
    )
    assert r.status_code == 400
    assert "no steps" in r.json()["detail"]


async def test_create_execution_rejects_negative_step_to_at_schema(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """``step_to=-1`` is rejected by the Pydantic ``ge=0`` validator
    BEFORE we hit the router — returns 422, not 400."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=3)
    auth = await _login_alice(client)
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={
            "case_id": case_id,
            "n_runs": 1,
            "parallel": 1,
            "env": "dev",
            "step_to": -1,
        },
    )
    assert r.status_code == 422


async def test_step_to_argv_appended_when_set(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """End-to-end: create with step_to, run, verify ``--step-to <N>``
    appears at the tail of the captured argv."""
    from app.services.executor import run_execution

    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=5)
    await _login_alice(client)  # ensures alice exists in DB
    # Insert the Execution + ExecRun rows directly so the test owns
    # the lifecycle (avoids the create_execution background task racing
    # with our explicit ``run_execution`` call below).
    eid = await _create_execution_directly(
        client, case_id=case_id, n_runs=1, parallel=1, step_to=3
    )

    cap = _CapturedCmd()
    cap.install(monkeypatch)
    await run_execution(eid)

    assert len(cap.captured) == 1, "expected exactly one subprocess spawn"
    argv = cap.captured[0]
    assert "--step-to" in argv
    # The index of "--step-to" is followed by the value as a string.
    idx = argv.index("--step-to")
    assert argv[idx + 1] == "3"


async def test_step_to_argv_omitted_when_none(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """Legacy payload: no step_to → argv has no --step-to flag (4 elements:
    gimbal + run + launch + yaml)."""
    from app.services.executor import run_execution

    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=5)
    await _login_alice(client)
    eid = await _create_execution_directly(
        client, case_id=case_id, n_runs=1, parallel=1, step_to=None
    )

    cap = _CapturedCmd()
    cap.install(monkeypatch)
    await run_execution(eid)

    argv = cap.captured[0]
    assert "--step-to" not in argv
    assert len(argv) == 4  # gimbal / run / launch / yaml


async def test_step_to_argv_skipped_on_admin_override(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """When ``command_line`` admin override is set, the executor must NOT
    silently append ``--step-to`` — admin argv is RCE-trust verbatim."""
    from app.services.executor import run_execution

    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=5)
    # Promote alice to admin so she can pass command_line.
    from app.core.db import SessionLocal
    from app.models import User
    from sqlalchemy import select as _sel

    await _login_alice(client)
    async with SessionLocal() as s:
        alice = (await s.execute(_sel(User).where(User.username == "alice"))).scalar_one()
        alice.is_admin = True
        await s.commit()

    eid = await _create_execution_directly(
        client,
        case_id=case_id,
        n_runs=1,
        parallel=1,
        step_to=3,
        command_line=["custom-gimbal", "run", "launch", "/tmp/x.yaml"],
    )

    cap = _CapturedCmd()
    cap.install(monkeypatch)
    await run_execution(eid)

    argv = cap.captured[0]
    # Admin override is preserved verbatim — no --step-to injection.
    assert argv == ["custom-gimbal", "run", "launch", "/tmp/x.yaml"]
    assert "--step-to" not in argv


async def _create_execution_directly(
    client: AsyncClient,
    *,
    case_id: str,
    n_runs: int,
    parallel: int,
    step_to: int | None = None,
    command_line: list[str] | None = None,
) -> int:
    """Insert an Execution + ExecRun rows directly, bypassing the router.

    The router's create_execution fires ``asyncio.create_task(_safe_run)``
    which races with any direct ``run_execution`` call the test makes.
    Tests that want to drive the orchestrator synchronously should use
    this helper instead of POST /executions.
    """
    from app.core.db import SessionLocal
    from app.models import ExecRun, Execution, User
    from sqlalchemy import select as _sel

    async with SessionLocal() as s:
        alice = (await s.execute(_sel(User).where(User.username == "alice"))).scalar_one()
        cfg: dict = {
            "n_runs": n_runs,
            "parallel": parallel,
            "env": "dev",
            "prefix": None,
            "exec_auth_alias": [],
            "merge_policy": "override",
            "inject_credentials": True,
        }
        if step_to is not None:
            cfg["step_to"] = step_to
        if command_line is not None:
            cfg["command_line"] = command_line
        ex = Execution(
            case_id=case_id,
            owner_id=alice.id,
            status="queued",
            total_runs=n_runs,
            config_json=cfg,
        )
        s.add(ex)
        await s.commit()
        await s.refresh(ex)
        for idx in range(1, n_runs + 1):
            s.add(ExecRun(execution_id=ex.id, idx=idx, status="pending"))
        await s.commit()
        return ex.id

# ── cross-user execution (security round) ──────────────────────
async def test_member_cannot_execute_other_users_private_case(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    """POST /executions previously had no case-visibility check: a member
    who knew another user's private case_id could execute it AND read the
    run output via /runs/{id}/log|report (those only check the Execution
    owner). Must 404 with the same existence-hiding policy as GET /cases."""
    case_id = await _seed_steps_case(tmp_path, monkeypatch, n_steps=1)
    a_auth = await _login_alice(client)
    # alice takes a private copy of the seeded public case
    a_copy = await client.post(f"/api/cases/{case_id}/copy", headers=a_auth)
    assert a_copy.status_code == 200
    private_id = a_copy.json()["case_id"]

    await client.post(
        "/api/auth/register", json={"username": "bob", "password": "bobpass456"}
    )
    b_login = await client.post(
        "/api/auth/login", json={"username": "bob", "password": "bobpass456"}
    )
    b_auth = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    r = await client.post(
        "/api/executions",
        headers=b_auth,
        json={"case_id": private_id, "n_runs": 1, "parallel": 1},
    )
    assert r.status_code == 404, r.text

    # Sanity: the owner may still execute it.
    r_owner = await client.post(
        "/api/executions",
        headers=a_auth,
        json={"case_id": private_id, "n_runs": 1, "parallel": 1},
    )
    assert r_owner.status_code == 201, r_owner.text
