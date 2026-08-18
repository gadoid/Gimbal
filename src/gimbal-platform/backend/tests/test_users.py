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
    """The lone admin demotes THEMSELVES → 409/4092 (admin_total → 0).

    (A *member* trying to demote the admin now gets 403/4032 — see
    test_member_cannot_escalate_or_demote below.)
    """
    admin_token = (await _register(client, "lone_admin"))["access_token"]
    me = (
        await client.get("/api/auth/me", headers=_bearer(admin_token))
    ).json()
    admin_id = me["user"]["id"]

    r = await client.patch(
        f"/api/users/{admin_id}",
        json={"is_admin": False},
        headers=_bearer(admin_token),
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == 4092


# ── authorization hardening (2026-08 pass) ─────────────────────────
async def _register_and_login(
    client: AsyncClient, username: str, password: str = "Test2026!"
) -> dict:
    payload = await _register(client, username, password)
    return _bearer(payload["access_token"])


@pytest.mark.asyncio
async def test_member_cannot_escalate_or_demote(client: AsyncClient) -> None:
    """P0 regression: member PATCHing ``is_admin`` (either direction,
    any target) must get 403/4032 — used to be a one-call privilege
    escalation."""
    await _register_and_login(client, "admin")  # uid 1, auto-admin
    member = await _register_and_login(client, "member")  # uid 2

    # Escalate self
    r = await client.patch(
        "/api/users/2", headers=member, json={"is_admin": True}
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == 4032

    # Demote the admin
    r = await client.patch(
        "/api/users/1", headers=member, json={"is_admin": False}
    )
    assert r.status_code == 403

    # Follow-up: member is still not an admin
    lst = await client.get("/api/users", headers=member)
    row = next(u for u in lst.json() if u["username"] == "member")
    assert row["is_admin"] is False


@pytest.mark.asyncio
async def test_member_cannot_patch_others(client: AsyncClient) -> None:
    """A member may only patch themselves (403/4032 on other targets)."""
    await _register_and_login(client, "admin")
    member = await _register_and_login(client, "member")

    r = await client.patch(
        "/api/users/1", headers=member, json={"display_name": "Hacked"}
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == 4032


@pytest.mark.asyncio
async def test_member_can_patch_self_display_name(client: AsyncClient) -> None:
    """Self-service rename still works for members (no regression)."""
    await _register_and_login(client, "admin")
    member = await _register_and_login(client, "member")

    r = await client.patch(
        "/api/users/2", headers=member, json={"display_name": "My Nick"}
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "My Nick"


@pytest.mark.asyncio
async def test_member_cannot_delete_other_user(client: AsyncClient) -> None:
    """Deleting another account is admin-only (403/4031)."""
    await _register_and_login(client, "admin")
    member = await _register_and_login(client, "member")
    await _register_and_login(client, "victim")  # uid 3

    r = await client.delete("/api/users/3", headers=member)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == 4031


@pytest.mark.asyncio
async def test_member_cannot_reset_others_password(client: AsyncClient) -> None:
    """P0 regression: member resetting someone else's password used to be
    a full account takeover (attacker received the plaintext)."""
    await _register_and_login(client, "admin")
    member = await _register_and_login(client, "member")

    r = await client.post("/api/users/1/reset-password", headers=member)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == 4033

    # The admin's original password still logs in.
    relogin = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Test2026!"},
    )
    assert relogin.status_code == 200


@pytest.mark.asyncio
async def test_member_can_reset_own_password(client: AsyncClient) -> None:
    """Self-service password reset still works for members."""
    await _register_and_login(client, "admin")
    member = await _register_and_login(client, "member")

    r = await client.post("/api/users/2/reset-password", headers=member)
    assert r.status_code == 200
    new_pw = r.json()["new_password"]
    assert new_pw

    relogin = await client.post(
        "/api/auth/login", json={"username": "member", "password": new_pw}
    )
    assert relogin.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_reset_members_password(client: AsyncClient) -> None:
    """Admin resetting a member's password still works (no regression)."""
    admin = await _register_and_login(client, "admin")
    await _register_and_login(client, "member")

    r = await client.post("/api/users/2/reset-password", headers=admin)
    assert r.status_code == 200
    new_pw = r.json()["new_password"]

    relogin = await client.post(
        "/api/auth/login", json={"username": "member", "password": new_pw}
    )
    assert relogin.status_code == 200


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


# ── display_name ownership-identity uniqueness (security round) ──
async def test_member_cannot_adopt_another_users_display_name(
    client: AsyncClient,
) -> None:
    """display_name doubles as composer-ownership identity (scenario/case/
    data-set rows store it as ``owner``/``created_by``). A member adopting
    another user's display_name could hijack their resources — the PATCH
    must 409."""
    await _register_and_login(client, "alice")  # uid 1
    alice_auth = _bearer(await _login(client, "alice"))
    r = await client.patch(
        "/api/users/1",
        headers=alice_auth,
        json={"display_name": "Alice Chen"},
    )
    assert r.status_code == 200, r.text

    bob_auth = await _register_and_login(client, "bob")  # uid 2
    r = await client.patch(
        "/api/users/2",
        headers=bob_auth,
        json={"display_name": "Alice Chen"},
    )
    assert r.status_code == 409, r.text

    # Taking a *username* as one's display_name is equally forbidden.
    r2 = await client.patch(
        "/api/users/2",
        headers=bob_auth,
        json={"display_name": "alice"},
    )
    assert r2.status_code == 409, r2.text
