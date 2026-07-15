"""Tests for the /api/cases/{id}/hidden routes (Spec-2 §4.3 C2)."""
from __future__ import annotations

import json

import pytest
from httpx import AsyncClient


@pytest.fixture
async def seed_public_case(tmp_path, monkeypatch) -> str:
    pub_dir = tmp_path / "public"
    pub_dir.mkdir()
    seed = pub_dir / "sc_e2e.json"
    seed.write_text(
        json.dumps(
            {
                "kind": "scenario",
                "scenarioId": "sc_e2e",
                "meta": {"name": "E2E"},
                "config": {"services": {}, "users": {}, "vars": {}},
                "steps": [],
            }
        ),
        encoding="utf-8",
    )
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", pub_dir)
    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    (tmp_path / "users").mkdir(exist_ok=True)
    from app.services.case_loader import loader

    loader._cache.clear()
    loader._last_full_scan = 0
    return "sc_e2e"


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


# ── GET defaults ──────────────────────────────────────────────
async def test_get_hidden_returns_empty_when_no_profile(
    client: AsyncClient, seed_public_case: str
) -> None:
    auth = await _login_alice(client)
    r = await client.get(f"/api/cases/{seed_public_case}/hidden", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["case_id"] == seed_public_case
    assert body["hidden_paths"] == []
    assert body["scope"] == "case"


# ── PUT creates profile ──────────────────────────────────────
async def test_put_hidden_creates_profile(
    client: AsyncClient, seed_public_case: str
) -> None:
    auth = await _login_alice(client)
    paths = [
        "api.headers[\"sec-ch-ua-platform\"]",
        "api.headers[\"sec-ch-ua\"]",
        "meta.requirementRef",
    ]
    r = await client.put(
        f"/api/cases/{seed_public_case}/hidden",
        headers=auth,
        json={"hidden_paths": paths, "scope": "case"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["hidden_paths"] == paths
    assert body["scope"] == "case"


# ── PUT updates existing ─────────────────────────────────────
async def test_put_hidden_replaces_existing_paths(
    client: AsyncClient, seed_public_case: str
) -> None:
    auth = await _login_alice(client)
    # First save
    await client.put(
        f"/api/cases/{seed_public_case}/hidden",
        headers=auth,
        json={"hidden_paths": ["a", "b", "c"]},
    )
    # Second save REPLACES (not appends)
    r = await client.put(
        f"/api/cases/{seed_public_case}/hidden",
        headers=auth,
        json={"hidden_paths": ["d"]},
    )
    assert r.status_code == 200
    assert r.json()["hidden_paths"] == ["d"]

    # GET returns the latest
    r = await client.get(f"/api/cases/{seed_public_case}/hidden", headers=auth)
    assert r.json()["hidden_paths"] == ["d"]


# ── per-user isolation ────────────────────────────────────────
async def test_two_users_have_independent_profiles(
    client: AsyncClient, seed_public_case: str
) -> None:
    a_auth = await _login_alice(client)
    await client.post(
        "/api/auth/register", json={"username": "bob", "password": "bobpass456"}
    )
    b_login = await client.post(
        "/api/auth/login", json={"username": "bob", "password": "bobpass456"}
    )
    b_auth = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    # Alice saves A, B saves B
    await client.put(
        f"/api/cases/{seed_public_case}/hidden",
        headers=a_auth,
        json={"hidden_paths": ["alice-only"]},
    )
    await client.put(
        f"/api/cases/{seed_public_case}/hidden",
        headers=b_auth,
        json={"hidden_paths": ["bob-only"]},
    )

    # Each sees only their own
    a_get = await client.get(f"/api/cases/{seed_public_case}/hidden", headers=a_auth)
    b_get = await client.get(f"/api/cases/{seed_public_case}/hidden", headers=b_auth)
    assert a_get.json()["hidden_paths"] == ["alice-only"]
    assert b_get.json()["hidden_paths"] == ["bob-only"]


# ── case_id path-style ──────────────────────────────────────
async def test_case_id_with_chinese_works(
    client: AsyncClient, seed_public_case: str
) -> None:
    auth = await _login_alice(client)
    paths = ["api.headers[\"X-Test\"]"]
    r = await client.put(
        f"/api/cases/{seed_public_case}/hidden",
        headers=auth,
        json={"hidden_paths": paths},
    )
    assert r.status_code == 200
    r = await client.get(f"/api/cases/{seed_public_case}/hidden", headers=auth)
    assert r.json()["hidden_paths"] == paths


# ── unauthenticated ─────────────────────────────────────────
async def test_endpoints_require_auth(client: AsyncClient, seed_public_case: str) -> None:
    r = await client.get(f"/api/cases/{seed_public_case}/hidden")
    assert r.status_code == 401
    r = await client.put(
        f"/api/cases/{seed_public_case}/hidden",
        json={"hidden_paths": []},
    )
    assert r.status_code == 401


# ── empty list is valid ──────────────────────────────────────
async def test_empty_paths_list_is_accepted(
    client: AsyncClient, seed_public_case: str
) -> None:
    auth = await _login_alice(client)
    await client.put(
        f"/api/cases/{seed_public_case}/hidden",
        headers=auth,
        json={"hidden_paths": ["x"]},
    )
    r = await client.put(
        f"/api/cases/{seed_public_case}/hidden",
        headers=auth,
        json={"hidden_paths": []},
    )
    assert r.status_code == 200
    assert r.json()["hidden_paths"] == []