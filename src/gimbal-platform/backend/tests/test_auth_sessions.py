"""Tests for the /api/auths router (Spec-2 §4.4 D).

Covers:
- list/create/get/patch/delete lifecycle
- password is encrypted at rest (never plaintext in DB or response)
- alias uniqueness per owner (owner_id+alias UNIQUE constraint)
- cross-owner isolation: alice can't see/edit bob's auths
- /test endpoint: success + 4xx + network failure
"""
from __future__ import annotations

from httpx import AsyncClient

from .helpers import register_and_login


# ── lifecycle ────────────────────────────────────────────────────
async def test_list_initially_empty(client: AsyncClient) -> None:
    auth = await register_and_login(client)
    r = await client.get("/api/auths", headers=auth)
    assert r.status_code == 200
    assert r.json() == []


async def test_create_then_list_returns_one(client: AsyncClient) -> None:
    auth = await register_and_login(client)

    r = await client.post(
        "/api/auths",
        headers=auth,
        json={
            "alias": "qa1",
            "url": "https://example.com/auth/login",
            "username": "alice_user",
            "password": "s3cret",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["alias"] == "qa1"
    assert body["username"] == "alice_user"  # decrypted in response
    assert body["password_masked"] == "<REDACTED>"
    assert "password" not in body  # plaintext never leaks

    r = await client.get("/api/auths", headers=auth)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["alias"] == "qa1"


async def test_password_is_encrypted_at_rest(client: AsyncClient) -> None:
    """Direct DB introspection — the password column must NOT contain the plaintext."""
    auth = await register_and_login(client)

    await client.post(
        "/api/auths",
        headers=auth,
        json={
            "alias": "qa1",
            "url": "https://example.com/auth",
            "username": "alice_user",
            "password": "plaintext-pw-12345",
        },
    )

    # Query the DB directly to confirm password_enc is ciphertext.
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import AuthSession

    async with SessionLocal() as s:
        rows = (await s.execute(select(AuthSession))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert "plaintext-pw-12345" not in row.password_enc
    assert "plaintext-pw-12345" not in row.username_enc
    # Fernet ciphertext is a base64 token starting with 'gAAA' typically.
    assert len(row.password_enc) > 32


# ── alias uniqueness ─────────────────────────────────────────────
async def test_alias_must_be_unique_per_owner(client: AsyncClient) -> None:
    auth = await register_and_login(client)

    payload = {
        "alias": "qa1",
        "url": "https://example.com/auth",
        "username": "u",
        "password": "p",
    }
    r1 = await client.post("/api/auths", headers=auth, json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/auths", headers=auth, json=payload)
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"].lower()


async def test_same_alias_different_owners_is_ok(client: AsyncClient) -> None:
    """The UNIQUE constraint is (owner_id, alias), so two users can share aliases."""
    # alice
    a_auth = await register_and_login(client)

    # bob (registered by alice as admin — Spec-1 self-register is admin; we
    # need bob to NOT be admin to verify cross-owner isolation doesn't leak
    # admin-permission into the data model). Spec-1 task-6: non-first users
    # default to non-admin. But in Spec-1 register, EVERY user is admin
    # (intentional — Spec-2 admin/role split is deferred). So bob is also
    # admin but is a *different user* with a *different user_id*.
    b_auth = await register_and_login(client, "bob", "bobpass456")

    # Both create alias="qa1" — both must succeed (different owner_id).
    for headers in (a_auth, b_auth):
        r = await client.post(
            "/api/auths",
            headers=headers,
            json={
                "alias": "qa1",
                "url": "https://example.com/auth",
                "username": "u",
                "password": "p",
            },
        )
        assert r.status_code == 201, r.text

    # Each sees only their own one entry.
    a_list = await client.get("/api/auths", headers=a_auth)
    b_list = await client.get("/api/auths", headers=b_auth)
    assert len(a_list.json()) == 1
    assert len(b_list.json()) == 1


# ── cross-owner isolation ─────────────────────────────────────────
async def test_cannot_get_other_owners_auth(client: AsyncClient) -> None:
    a_auth = await register_and_login(client)

    r = await client.post(
        "/api/auths",
        headers=a_auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "p"},
    )
    alice_id = r.json()["id"]

    # Bob registers and tries to GET / PATCH / DELETE alice's auth.
    b_auth = await register_and_login(client, "bob", "bobpass456")

    r = await client.get(f"/api/auths/{alice_id}", headers=b_auth)
    assert r.status_code == 404, r.text
    r = await client.patch(
        f"/api/auths/{alice_id}", headers=b_auth, json={"url": "https://evil"}
    )
    assert r.status_code == 404
    r = await client.delete(f"/api/auths/{alice_id}", headers=b_auth)
    assert r.status_code == 404


# ── patch ────────────────────────────────────────────────────────
async def test_patch_updates_individual_fields(client: AsyncClient) -> None:
    auth = await register_and_login(client)

    r = await client.post(
        "/api/auths",
        headers=auth,
        json={"alias": "qa1", "url": "https://old", "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    # Update only URL
    r = await client.patch(f"/api/auths/{aid}", headers=auth, json={"url": "https://new"})
    assert r.status_code == 200
    body = r.json()
    assert body["url"] == "https://new"
    assert body["alias"] == "qa1"  # unchanged

    # Update password — must be re-encrypted
    r = await client.patch(
        f"/api/auths/{aid}", headers=auth, json={"password": "new-pw-999"}
    )
    assert r.status_code == 200


# ── delete ───────────────────────────────────────────────────────
async def test_delete_returns_204(client: AsyncClient) -> None:
    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "p"},
    )
    aid = r.json()["id"]
    r = await client.delete(f"/api/auths/{aid}", headers=auth)
    assert r.status_code == 204
    r = await client.get(f"/api/auths/{aid}", headers=auth)
    assert r.status_code == 404


# ── /test endpoint ──────────────────────────────────────────────
async def test_test_endpoint_returns_token_preview(
    client: AsyncClient, monkeypatch
) -> None:
    """Mock 同步 httpx.post(probe 经 to_thread 调认证器)验证 token 提取。"""
    import httpx

    req = httpx.Request("POST", "https://x")

    def fake_post(*a: object, **kw: object) -> httpx.Response:
        return httpx.Response(
            200, json={"access_token": "fake-token-abcdef123456"}, request=req
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    r = await client.post(f"/api/auths/{aid}/test", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["status_code"] == 200
    assert "fake-token" in body["message"]


async def test_test_endpoint_4xx_returns_failure(
    client: AsyncClient, monkeypatch
) -> None:
    """401 → raise_for_status 抛 HTTPStatusError → ok=False、status_code=None。

    迁移后 probe 失败路径不再透传 4xx 码(auth_probe.py 失败分支恒 None),
    前端弹框仅在 status_code 非空时显示 HTTP badge。
    """
    import httpx

    req = httpx.Request("POST", "https://x")

    def fake_post(*a: object, **kw: object) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad creds"}, request=req)

    monkeypatch.setattr(httpx, "post", fake_post)

    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    r = await client.post(f"/api/auths/{aid}/test", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["status_code"] is None
    assert "网络/认证错误" in body["message"]


# ── unauthenticated ─────────────────────────────────────────────
async def test_endpoints_require_auth(client: AsyncClient) -> None:
    """All endpoints (except via register) need a valid token."""
    r = await client.get("/api/auths")
    assert r.status_code == 401
    r = await client.post(
        "/api/auths",
        json={"alias": "x", "url": "x", "username": "x", "password": "x"},
    )
    assert r.status_code == 401


# ── GET detail + include_secrets(2026-08-25 认证改造设计)─────────
async def test_detail_without_secrets_keeps_password_masked(client: AsyncClient) -> None:
    """不带 include_secrets 的详情:行为与改造前一致,不泄露明文。"""
    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "s3cret"},
    )
    aid = r.json()["id"]

    r = await client.get(f"/api/auths/{aid}", headers=auth)
    assert r.status_code == 200
    assert "password" not in r.json()
    assert r.json()["password_masked"] == "<REDACTED>"


async def test_detail_with_secrets_returns_plaintext(client: AsyncClient) -> None:
    """include_secrets=true:附解密后的明文 password(内网测试环境策略)。"""
    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=auth,
        json={
            "alias": "qa1",
            "url": "https://x",
            "username": "alice_user",
            "password": "s3cret",
        },
    )
    aid = r.json()["id"]

    r = await client.get(f"/api/auths/{aid}?include_secrets=true", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == "alice_user"
    assert body["password"] == "s3cret"


async def test_detail_with_secrets_cross_owner_404(client: AsyncClient) -> None:
    a_auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=a_auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    b_auth = await register_and_login(client, "bob", "bobpass456")
    r = await client.get(f"/api/auths/{aid}?include_secrets=true", headers=b_auth)
    assert r.status_code == 404


async def test_detail_with_secrets_rotation_422(
    client: AsyncClient, monkeypatch
) -> None:
    """FERNET_KEY 轮换后的旧密文:严解密失败 → 422(带人话指引)。

    快照拷贝会把返回值当真值写进场景导出产物,所以这里不能像列表
    _safe_decrypt 那样降级为占位符 — 必须显式失败。
    """
    from app.routers import auth_sessions as router_mod

    def boom(_s: str) -> str:
        raise ValueError("key rotated")

    monkeypatch.setattr(router_mod, "fernet_decrypt", boom)

    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    r = await client.get(f"/api/auths/{aid}?include_secrets=true", headers=auth)
    assert r.status_code == 422
    assert "重新编辑保存" in r.json()["detail"]
