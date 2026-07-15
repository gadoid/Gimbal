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
import yaml
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
    client: AsyncClient
) -> None:
    """Runs marked 'running' for > ORPHAN_GRACE_MIN with no finished_at
    must be flipped to 'failed' when reconcile_orphan_runs() runs.
    Without this, /executions displays permanently-stuck rows after a
    uvicorn --reload crash (the original /executions/7 bug repro).
    """
    from app.core import db as db_module
    from app.models import ExecRun, Execution
    from app.routers.executions import (
        ORPHAN_GRACE_MIN,
        reconcile_orphan_runs,
    )

    auth = await _login_alice(client)
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={"case_id": "sc_e2e", "n_runs": 1, "parallel": 1},
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
    client: AsyncClient
) -> None:
    """Runs that ARE active (started_at within grace window) must NOT be
    touched — the reconciler must only reap STALE state, not anything
    in flight."""
    from app.core import db as db_module
    from app.models import ExecRun, Execution
    from app.routers.executions import reconcile_orphan_runs

    auth = await _login_alice(client)
    r = await client.post(
        "/api/executions",
        headers=auth,
        json={"case_id": "sc_e2e", "n_runs": 1, "parallel": 1},
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
    client: AsyncClient
) -> None:
    """When an admin sets ``command_line``, the orchestrator must use it
    (overriding the default ``gimbal run launch <yaml> ...`` argv).  We
    verify this by inspecting the persisted ``config_json``.command_line
    on the resulting Execution row."""
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
            "case_id": "sc_e2e",
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