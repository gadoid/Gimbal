"""Tests for the case edit-mode flow (Spec-2-4 §4.3 C).

Verifies that PATCH /api/cases/{id} round-trips:
- meta fields (name, priority, tags with new order)
- config.services / config.users / config.vars
- steps reordering (drag-drop persistence)
"""
from __future__ import annotations

import json

import pytest
import yaml
from httpx import AsyncClient


@pytest.fixture
async def seed_case_with_steps(tmp_path, monkeypatch) -> str:
    pub_dir = tmp_path / "public"
    pub_dir.mkdir()
    seed = pub_dir / "e2e.json"
    payload = {
        "kind": "scenario",
        "scenarioId": "e2e",
        "meta": {
            "name": "Original",
            "module": "test",
            "priority": 1,
            "author": "alice",
            "tags": ["smoke", "regression"],
        },
        "config": {
            "services": {"api": "https://old"},
            "users": {},
            "vars": {"k": "v"},
        },
        "steps": [
            {"description": "first", "api": {"service": "api", "method": "GET", "path": "/a"}},
            {"description": "second", "api": {"service": "api", "method": "GET", "path": "/b"}},
            {"description": "third", "api": {"service": "api", "method": "GET", "path": "/c"}},
        ],
    }
    seed.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    from app.core import config as cfg
    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", pub_dir)
    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    (tmp_path / "users").mkdir(exist_ok=True)
    from app.services.case_loader import loader
    loader._cache.clear()
    loader._last_full_scan = 0
    return "e2e"


async def _login_alice(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


# ── meta edits ────────────────────────────────────────────────
async def test_patch_meta_updates_name_and_priority(
    client: AsyncClient, seed_case_with_steps: str, tmp_path
) -> None:
    auth = await _login_alice(client)
    new_payload = {
        "kind": "scenario",
        "scenarioId": "e2e",
        "meta": {"name": "Updated", "module": "test", "priority": 2, "author": "alice"},
        "config": {"services": {"api": "https://old"}, "users": {}, "vars": {"k": "v"}},
        "steps": [
            {"description": "first", "api": {"service": "api", "method": "GET", "path": "/a"}},
        ],
    }
    r = await client.patch(
        f"/api/cases/{seed_case_with_steps}",
        headers=auth,
        json={"payload": new_payload},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Updated"
    assert r.json()["priority"] == 2

    # Verify on disk
    with (tmp_path / "public" / f"{seed_case_with_steps}.json").open("r", encoding="utf-8") as f:
        written = json.load(f)
    assert written["meta"]["name"] == "Updated"
    assert written["meta"]["priority"] == 2


async def test_patch_meta_reorders_tags(
    client: AsyncClient, seed_case_with_steps: str
) -> None:
    auth = await _login_alice(client)
    # Reorder tags: ["regression", "smoke", "e2e"]
    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    body = r.json()
    payload = body["payload"]
    payload["meta"]["tags"] = ["regression", "smoke", "e2e"]
    r = await client.patch(
        f"/api/cases/{seed_case_with_steps}",
        headers=auth,
        json={"payload": payload},
    )
    assert r.status_code == 200

    # Re-fetch and check order
    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    assert r.json()["payload"]["meta"]["tags"] == ["regression", "smoke", "e2e"]


# ── config edits ──────────────────────────────────────────────
async def test_patch_config_adds_service(
    client: AsyncClient, seed_case_with_steps: str
) -> None:
    auth = await _login_alice(client)
    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    payload = r.json()["payload"]
    payload["config"]["services"]["new_svc"] = "https://new"
    r = await client.patch(
        f"/api/cases/{seed_case_with_steps}",
        headers=auth,
        json={"payload": payload},
    )
    assert r.status_code == 200
    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    assert "new_svc" in r.json()["payload"]["config"]["services"]


async def test_patch_config_updates_vars(
    client: AsyncClient, seed_case_with_steps: str
) -> None:
    auth = await _login_alice(client)
    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    payload = r.json()["payload"]
    # Add a new var
    payload["config"]["vars"]["order_no_prefix"] = "BIZ2024"
    payload["config"]["vars"]["order_no"] = "${var.order_no_prefix}-${var.seq}"
    # Add seq generator (canonical kind; "sequence" still works as alias
    # at gimbal level, see generator/specs.py SeqSpec shim)
    payload["config"]["vars"]["seq"] = {"kind": "seq"}
    r = await client.patch(
        f"/api/cases/{seed_case_with_steps}",
        headers=auth,
        json={"payload": payload},
    )
    assert r.status_code == 200
    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    vars_ = r.json()["payload"]["config"]["vars"]
    assert vars_["order_no_prefix"] == "BIZ2024"
    assert vars_["seq"] == {"kind": "seq"}


# ── steps reorder ────────────────────────────────────────────
async def test_patch_reorders_steps(
    client: AsyncClient, seed_case_with_steps: str
) -> None:
    """User drag-drops steps in the UI; PATCH round-trips new order."""
    auth = await _login_alice(client)
    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    payload = r.json()["payload"]
    # Original: [first, second, third]
    # After drag: [third, first, second]
    payload["steps"] = [payload["steps"][2], payload["steps"][0], payload["steps"][1]]
    r = await client.patch(
        f"/api/cases/{seed_case_with_steps}",
        headers=auth,
        json={"payload": payload},
    )
    assert r.status_code == 200

    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    descriptions = [s["description"] for s in r.json()["payload"]["steps"]]
    assert descriptions == ["third", "first", "second"]


async def test_patch_adds_new_step(
    client: AsyncClient, seed_case_with_steps: str
) -> None:
    auth = await _login_alice(client)
    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    payload = r.json()["payload"]
    payload["steps"].append(
        {"description": "fourth", "api": {"service": "api", "method": "GET", "path": "/d"}}
    )
    r = await client.patch(
        f"/api/cases/{seed_case_with_steps}",
        headers=auth,
        json={"payload": payload},
    )
    assert r.status_code == 200
    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    assert len(r.json()["payload"]["steps"]) == 4


async def test_patch_deletes_step(
    client: AsyncClient, seed_case_with_steps: str
) -> None:
    auth = await _login_alice(client)
    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    payload = r.json()["payload"]
    payload["steps"].pop(1)  # remove "second"
    r = await client.patch(
        f"/api/cases/{seed_case_with_steps}",
        headers=auth,
        json={"payload": payload},
    )
    assert r.status_code == 200
    r = await client.get(f"/api/cases/{seed_case_with_steps}", headers=auth)
    assert len(r.json()["payload"]["steps"]) == 2
    assert r.json()["payload"]["steps"][0]["description"] == "first"
    assert r.json()["payload"]["steps"][1]["description"] == "third"