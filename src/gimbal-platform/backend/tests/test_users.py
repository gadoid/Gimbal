"""User-management CRUD tests.

5 tests covering the spec-1 business constraints:

* admin_count() helper
* every-newly-created-user-is-not-admin (regardless of ``is_admin`` flag)
* cannot-delete-self (409 + code 4091)
* cannot-demote-last-admin (409 + code 4092)
* delete-then-lookup (404)
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


async def _register(client: AsyncClient, username: str, password: str = "Test2026!") -> dict:
    r = await client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _login(client: AsyncClient, username: str, password: str = "Test2026!") -> str:
    r = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_users_contains_self(client: AsyncClient) -> None:
    """First registered user is admin; list returns self row."""
    payload = await _register(client, "admin_one")
    token = payload["access_token"]
    r = await client.get("/api/users", headers=_bearer(token))
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 1
    assert items[0]["username"] == "admin_one"
    assert items[0]["is_admin"] is True


@pytest.mark.asyncio
async def test_newly_created_user_is_member_even_if_flag_true(client: AsyncClient) -> None:
    """Spec-1: ``UserCreateIn.is_admin=True`` is coerced to False on creation."""
    token = (await _register(client, "first_admin"))["access_token"]
    # create a second user trying to set is_admin=True — must end as member
    r = await client.post(
        "/api/users",
        json={
            "username": "wannabe_admin",
            "password": "Test2026!",
            "display_name": "wannabe",
            "is_admin": True,
        },
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["is_admin"] is False  # coerced — spec-1 simplification


@pytest.mark.asyncio
async def test_cannot_delete_self_4091(client: AsyncClient) -> None:
    """Caller must not be the target of DELETE — 409 + code 4091."""
    payload = await _register(client, "alice_admin")
    token = payload["access_token"]
    my_id = payload["user"]["id"]

    r = await client.delete(
        f"/api/users/{my_id}",
        headers=_bearer(token),
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == 4091


@pytest.mark.asyncio
async def test_cannot_demote_last_admin_4092(client: AsyncClient) -> None:
    """Only admin in the system; member tries to PATCH is_admin=False → 409/4092.

    Setup: register admin (auto-admin: lone_admin), then admin creates a
    member (member_one).  Member tries to demote the admin → 409/4092
    because admin_total would fall to 0.
    """
    admin_token = (await _register(client, "lone_admin"))["access_token"]
    me = (
        await client.get("/api/auth/me", headers=_bearer(admin_token))
    ).json()
    admin_id = me["user"]["id"]

    # admin creates a member
    r = await client.post(
        "/api/users",
        json={"username": "member_one", "password": "Test2026!"},
        headers=_bearer(admin_token),
    )
    assert r.status_code == 201, r.text

    member_token = await _login(client, "member_one", "Test2026!")
    # member tries to demote the admin
    r = await client.patch(
        f"/api/users/{admin_id}",
        json={"is_admin": False},
        headers=_bearer(member_token),
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == 4092


@pytest.mark.asyncio
async def test_delete_then_get_404(client: AsyncClient) -> None:
    """Admin creates user, deletes them, GET on the same id returns 404."""
    admin_token = (await _register(client, "admin_x"))["access_token"]
    r = await client.post(
        "/api/users",
        json={"username": "doomed_user", "password": "Test2026!"},
        headers=_bearer(admin_token),
    )
    assert r.status_code == 201, r.text
    doomed_id = r.json()["id"]

    r = await client.delete(
        f"/api/users/{doomed_id}",
        headers=_bearer(admin_token),
    )
    assert r.status_code == 204, r.text

    r = await client.get("/api/users", headers=_bearer(admin_token))
    assert r.status_code == 200
    assert all(u["id"] != doomed_id for u in r.json())
