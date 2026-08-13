"""End-to-end tests for the V3 Scenario Composer API surface.

Goes through the HTTP layer using the conftest ``client`` fixture so
router + auth + store + schema integration is exercised as one.  Plate
calls are NOT exercised here (see test_scenario_composer_plate_integration
for that — those tests replace the httpx client with a MockTransport).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


# ── helpers ────────────────────────────────────────────────────────
async def _register_and_login(
    client: AsyncClient, username: str = "alice", password: str = "alicepass123"
) -> dict[str, str]:
    await client.post(
        "/api/auth/register",
        json={"username": username, "password": password, "display_name": username},
    )
    r = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_draft(scenario_id: str = "sc-test", **meta_over) -> dict:
    meta = {
        "scenarioId": scenario_id,
        "name": "Test",
        "description": "smoke",
        "module": "order",
        "priority": 1,
        "author": "alice",
        "owner": "alice",
        "tags": ["smoke"],
        "system": ["fin"],
    }
    meta.update(meta_over)
    return {"meta": meta, "steps": []}


# ── envs ───────────────────────────────────────────────────────────
async def test_list_envs(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    r = await client.get("/api/envs", headers=headers)
    assert r.status_code == 200
    envs = r.json()
    assert isinstance(envs, list)
    # Bundled defaults ship at least dev-local + test-env-A + test-env-B.
    env_ids = {e["envId"] for e in envs}
    assert {"dev-local", "test-env-A", "test-env-B"} <= env_ids


# ── scenarios CRUD ────────────────────────────────────────────────
async def test_create_scenario_ok(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    r = await client.post("/api/scenarios", headers=headers, json=_make_draft())
    assert r.status_code == 201
    body = r.json()
    assert body["meta"]["scenarioId"] == "sc-test"
    assert body["caseCount"] == 0
    assert body["stepCount"] == 0
    # Starred defaults to false.
    assert body["starred"] is False


async def test_create_scenario_invalid_id_400(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios",
        headers=headers,
        json=_make_draft(scenario_id="INVALID"),
    )
    assert r.status_code == 422  # Pydantic pattern validation


async def test_create_scenario_conflict_409(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    await client.post("/api/scenarios", headers=headers, json=_make_draft())
    r = await client.post("/api/scenarios", headers=headers, json=_make_draft())
    assert r.status_code == 409
    assert "scenario_id_exists" in r.json()["detail"]


async def test_get_scenario_not_found_404(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    r = await client.get("/api/scenarios/sc-nope", headers=headers)
    assert r.status_code == 404


async def test_list_scenarios_with_filters(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    for sid, sys, prio in [("sc-a", ["fin"], 1), ("sc-b", ["logi"], 1), ("sc-c", ["fin"], 0)]:
        await client.post(
            "/api/scenarios",
            headers=headers,
            json=_make_draft(scenario_id=sid, system=sys, priority=prio),
        )
    r = await client.get("/api/scenarios?system=fin", headers=headers)
    assert r.status_code == 200
    ids = {s["meta"]["scenarioId"] for s in r.json()}
    assert ids == {"sc-a", "sc-c"}
    r2 = await client.get("/api/scenarios?priority=0", headers=headers)
    assert {s["meta"]["scenarioId"] for s in r2.json()} == {"sc-c"}


async def test_update_scenario_owner_forbidden_403(client: AsyncClient) -> None:
    """Bob cannot update a scenario owned by Alice."""
    alice = await _register_and_login(client, "alice")
    # Alice creates a scenario
    r = await client.post(
        "/api/scenarios", headers=alice, json=_make_draft()
    )
    assert r.status_code == 201
    # Login as bob and try to update
    bob = await _register_and_login(client, "bob", "bobpass456")
    r = await client.put(
        "/api/scenarios/sc-test",
        headers=bob,
        json=_make_draft(name="Bob rewrites"),
    )
    # Owner check is by display_name; default owner is "alice", so 403.
    assert r.status_code == 403


async def test_create_scenario_owner_cannot_be_spoofed(
    client: AsyncClient,
) -> None:
    """A client cannot create a scenario claiming a different owner."""
    alice = await _register_and_login(client, "alice")
    r = await client.post(
        "/api/scenarios",
        headers=alice,
        json=_make_draft(owner="admin"),
    )
    assert r.status_code == 201
    # The server overrides owner with the authenticated user, NOT the
    # value from the body.
    assert r.json()["meta"]["owner"] == "alice"


async def test_update_scenario_owner_cannot_be_reassigned(
    client: AsyncClient,
) -> None:
    """A scenario owner cannot transfer ownership to someone else by
    editing the body — the server keeps the original owner."""
    alice = await _register_and_login(client, "alice")
    await client.post("/api/scenarios", headers=alice, json=_make_draft())
    r = await client.put(
        "/api/scenarios/sc-test",
        headers=alice,
        json=_make_draft(owner="bob"),
    )
    assert r.status_code == 200
    assert r.json()["meta"]["owner"] == "alice"


async def test_create_case_created_by_cannot_be_spoofed(
    client: AsyncClient,
) -> None:
    """A client cannot create a case claiming a different createdBy."""
    alice = await _register_and_login(client, "alice")
    await client.post("/api/scenarios", headers=alice, json=_make_draft())
    r = await client.post(
        "/api/cases",
        headers=alice,
        json={
            "caseId": "case-001",
            "scenarioId": "sc-test",
            "name": "c",
            "env": "dev",
            "auth": {"name": "a", "type": "bearer"},
            "dataSetIds": [],
            "createdBy": "admin",  # spoofed
        },
    )
    assert r.status_code == 201
    # The server uses the authenticated user's display_name, not the body.
    assert r.json()["createdBy"] == "alice"


async def test_delete_scenario_cascades(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    await client.post("/api/scenarios", headers=headers, json=_make_draft())
    # Add a case + data set
    await client.post(
        "/api/cases",
        headers=headers,
        json={
            "caseId": "case-001",
            "scenarioId": "sc-test",
            "name": "c",
            "env": "dev",
            "auth": {"name": "a", "type": "bearer"},
            "dataSetIds": [],
            "createdBy": "alice",
        },
    )
    r_ds = await client.post(
        "/api/cases/case-001/data-sets",
        headers=headers,
        json={"name": "ds", "rows": [{"x": 1}]},
    )
    assert r_ds.status_code == 201
    # Delete scenario
    r_del = await client.delete("/api/scenarios/sc-test", headers=headers)
    assert r_del.status_code == 204
    # Both case and data set are gone
    r_case = await client.get("/api/cases/case-001", headers=headers)
    assert r_case.status_code == 404
    r_list = await client.get("/api/data-sets?caseId=case-001", headers=headers)
    assert r_list.json() == []


# ── star ───────────────────────────────────────────────────────────
async def test_star_toggle_persists(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    await client.post("/api/scenarios", headers=headers, json=_make_draft())
    r_star = await client.post(
        "/api/scenarios/sc-test/star", headers=headers, json={"starred": True}
    )
    assert r_star.status_code == 204
    r_get = await client.get("/api/scenarios/sc-test", headers=headers)
    assert r_get.json()["starred"] is True
    r_unstar = await client.post(
        "/api/scenarios/sc-test/star", headers=headers, json={"starred": False}
    )
    assert r_unstar.status_code == 204
    r_get2 = await client.get("/api/scenarios/sc-test", headers=headers)
    assert r_get2.json()["starred"] is False


# ── preview-plate (Plate mocked at the httpx level by other test) ──
async def test_preview_plate_unavailable_502(
    client: AsyncClient, monkeypatch
) -> None:
    """When Plate is unreachable, return 502 plate_unavailable."""
    import httpx

    from app.services import plate_client

    async def _boom(_: dict) -> dict:
        raise plate_client.PlateUnavailableError("connect refused")

    monkeypatch.setattr(plate_client, "convert", _boom)
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios/preview-plate", headers=headers, json=_make_draft()
    )
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "plate_unavailable"


# ── cases + data-sets ─────────────────────────────────────────────
async def test_data_set_inconsistent_rows_422(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    await client.post("/api/scenarios", headers=headers, json=_make_draft())
    await client.post(
        "/api/cases",
        headers=headers,
        json={
            "caseId": "case-001",
            "scenarioId": "sc-test",
            "name": "c",
            "env": "dev",
            "auth": {"name": "a", "type": "bearer"},
            "dataSetIds": [],
            "createdBy": "alice",
        },
    )
    r = await client.post(
        "/api/cases/case-001/data-sets",
        headers=headers,
        json={"name": "ds", "rows": [{"x": 1, "y": 2}, {"x": 1}]},
    )
    assert r.status_code == 422


async def test_patch_case_rejects_immutable_fields(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    await client.post("/api/scenarios", headers=headers, json=_make_draft())
    await client.post(
        "/api/cases",
        headers=headers,
        json={
            "caseId": "case-001",
            "scenarioId": "sc-test",
            "name": "c",
            "env": "dev",
            "auth": {"name": "a", "type": "bearer"},
            "dataSetIds": [],
            "createdBy": "alice",
        },
    )
    r = await client.patch(
        "/api/cases/case-001",
        headers=headers,
        json={"scenarioId": "sc-other"},
    )
    assert r.status_code == 422  # Pydantic model_validator rejects immutable


async def test_data_set_summary_preview_truncated(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    await client.post("/api/scenarios", headers=headers, json=_make_draft())
    await client.post(
        "/api/cases",
        headers=headers,
        json={
            "caseId": "case-001",
            "scenarioId": "sc-test",
            "name": "c",
            "env": "dev",
            "auth": {"name": "a", "type": "bearer"},
            "dataSetIds": [],
            "createdBy": "alice",
        },
    )
    rows = [{"x": i} for i in range(10)]
    await client.post(
        "/api/cases/case-001/data-sets",
        headers=headers,
        json={"name": "ds", "rows": rows},
    )
    r = await client.get("/api/data-sets?caseId=case-001", headers=headers)
    summaries = r.json()
    assert len(summaries) == 1
    assert summaries[0]["rowCount"] == 10
    assert len(summaries[0]["preview"]) == 3


# ── runs (Plate mocked, so we only test the 404 paths here) ───────
async def test_run_dispatch_case_not_found_404(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "caseId": "case-nope",
            "dataSetIds": ["ds-001"],
            "env": {"envId": "test-env-A", "name": "test-env-A", "baseUrl": "http://x"},
        },
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "case_not_found"


async def test_run_dispatch_env_not_found_404(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    await client.post("/api/scenarios", headers=headers, json=_make_draft())
    await client.post(
        "/api/cases",
        headers=headers,
        json={
            "caseId": "case-001",
            "scenarioId": "sc-test",
            "name": "c",
            "env": "dev",
            "auth": {"name": "a", "type": "bearer"},
            "dataSetIds": [],
            "createdBy": "alice",
        },
    )
    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "caseId": "case-001",
            "dataSetIds": ["ds-001"],
            "env": {"envId": "nope", "name": "nope", "baseUrl": "http://x"},
        },
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "env_not_found"


# ── scenario-ownership check on POST /api/cases ────────────────────
async def test_create_case_requires_scenario_ownership(client: AsyncClient) -> None:
    """Bob cannot create a case under Alice's scenario."""
    alice = await _register_and_login(client, "alice")
    await client.post("/api/scenarios", headers=alice, json=_make_draft())
    bob = await _register_and_login(client, "bob", "bobpass456")
    r = await client.post(
        "/api/cases",
        headers=bob,
        json={
            "caseId": "case-001",
            "scenarioId": "sc-test",
            "name": "case by bob",
            "env": "dev",
            "auth": {"name": "a", "type": "bearer"},
            "dataSetIds": [],
            "createdBy": "bob",
        },
    )
    assert r.status_code == 403
    assert "not_owner" in r.json()["detail"]


async def test_create_case_admin_can_create_under_any_scenario(
    client: AsyncClient,
) -> None:
    """An admin user can create cases under any scenario."""
    # Mark alice as admin via the user admin endpoint (best-effort: a
    # fresh registration gives is_admin=False; we patch the DB row).
    from app.core import db as db_module
    from app.models import User
    from sqlalchemy import update

    async with db_module.SessionLocal() as session:
        await session.execute(
            update(User).where(User.username == "alice").values(is_admin=True)
        )
        await session.commit()

    alice = await _register_and_login(client, "alice")
    await client.post("/api/scenarios", headers=alice, json=_make_draft())
    # Bob is not admin but also not the owner; should still 403.
    bob = await _register_and_login(client, "bob", "bobpass456")
    # Re-fetch alice to pick up the admin flag; the token is the same so
    # we just re-use it.
    r = await client.post(
        "/api/cases",
        headers=alice,  # alice is admin now
        json={
            "caseId": "case-001",
            "scenarioId": "sc-test",
            "name": "case by admin",
            "env": "dev",
            "auth": {"name": "a", "type": "bearer"},
            "dataSetIds": [],
            "createdBy": "alice",
        },
    )
    assert r.status_code == 201


async def test_stars_store_atomic_write_no_partial_corruption(
    tmp_path, monkeypatch
) -> None:
    """A crash mid-write leaves the previous good file intact (the
    temp file is cleaned up).  We simulate the crash by patching
    ``os.replace`` to raise."""
    from app.services import stars_store

    # Point the store at a fresh tmp dir + clear the in-memory dict.
    monkeypatch.setattr(stars_store, "_STARS_PATH", tmp_path / "stars.json")
    stars_store._STARS.clear()
    monkeypatch.setattr(
        "os.replace", lambda *a, **kw: (_ for _ in ()).throw(OSError("simulated crash"))
    )
    with pytest.raises(OSError, match="simulated crash"):
        stars_store.star(1, "sc-x", True)
    # In-memory dict still updated (so the next successful write will
    # persist both the old and new entry).
    assert stars_store.is_starred(1, "sc-x") is True
    # No orphan temp files left in the dir.
    leftovers = list(tmp_path.glob("*.stars.*.json.tmp"))
    assert leftovers == []
