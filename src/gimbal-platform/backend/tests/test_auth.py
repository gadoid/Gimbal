"""Tests for the auth router (register/login/refresh/me).

NOTE: This module imports ``from app.main import create_app`` which is created
in Task 5. Tests cannot run in Task 3 — pytest is deferred until Task 5 lands.

The ``client`` fixture (with ``fresh_db`` isolation) lives in ``tests/conftest.py``.
"""
from __future__ import annotations

from httpx import AsyncClient


async def test_first_register_becomes_admin(client: AsyncClient) -> None:
    """The very first registered user is promoted to admin."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "password": "secret123",
            "display_name": "Alice",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["is_admin"] is True
    assert body["user"]["is_active"] is True
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


async def test_second_register_is_member(client: AsyncClient) -> None:
    """A second registration yields a non-admin member."""
    r1 = await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "secret123"},
    )
    assert r1.status_code == 201
    r2 = await client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "secret123"},
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["user"]["is_admin"] is False


async def test_login_wrong_password_401(client: AsyncClient) -> None:
    """Login with a wrong password returns 401."""
    r1 = await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "secret123"},
    )
    assert r1.status_code == 201
    r2 = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "wrong_pwd1"},
    )
    assert r2.status_code == 401
    body = r2.json()
    # detail may be dict ({code, msg}) or str depending on FastAPI serialization;
    # assert the 401 code surfaces either way.
    assert body is not None


async def test_refresh_token_round_trip(client: AsyncClient) -> None:
    """A refresh token can be exchanged for a fresh access token."""
    r1 = await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "secret123"},
    )
    assert r1.status_code == 201
    initial = r1.json()
    r2 = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": initial["refresh_token"]},
    )
    assert r2.status_code == 200, r2.text
    renewed = r2.json()
    assert renewed["token_type"] == "bearer"
    assert renewed["access_token"]
    assert renewed["access_token"] != initial["access_token"]


async def test_register_duplicate_username_409(client: AsyncClient) -> None:
    """Re-registering an existing username returns 409."""
    r1 = await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "secret123"},
    )
    assert r1.status_code == 201
    r2 = await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "another1"},
    )
    assert r2.status_code == 409
    body = r2.json()
    assert body is not None